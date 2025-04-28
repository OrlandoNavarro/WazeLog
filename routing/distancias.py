"""
Cálculo de matriz de distâncias/tempos entre pontos usando OSRM, Mapbox, Google, etc.
"""
import requests
import numpy as np
import logging
import os # Adicionado para variáveis de ambiente

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL do servidor OSRM - busca variável de ambiente ou usa default público
OSRM_SERVER_URL = os.environ.get("OSRM_URL", "http://router.project-osrm.org")

# Constante para valor grande representando infinito para OR-Tools
# Usar np.inf pode ser problemático se o solver não o suportar diretamente em todas as situações.
# Um valor inteiro grande é frequentemente mais seguro.
INFINITE_VALUE = 9999999 # Ajuste conforme necessário

def _validar_coordenadas(pontos):
    """Verifica se a lista de pontos contém coordenadas válidas."""
    if not isinstance(pontos, list):
        logging.error("Entrada 'pontos' não é uma lista.")
        return False
    for i, ponto in enumerate(pontos):
        if not isinstance(ponto, (tuple, list)) or len(ponto) != 2:
            logging.error(f"Ponto inválido na posição {i}: {ponto}. Deve ser tupla/lista de 2 elementos.")
            return False
        lat, lon = ponto
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            logging.error(f"Coordenadas inválidas na posição {i}: {ponto}. Devem ser numéricas.")
            return False
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            logging.warning(f"Coordenadas fora do intervalo padrão na posição {i}: ({lat}, {lon}).")
            # Não retorna False aqui, apenas avisa, pois podem existir sistemas de coordenadas diferentes
            # Mas para OSRM padrão, isso pode indicar um erro.
    return True

def calcular_matriz_distancias(pontos, provider="osrm", metrica="duration"):
    """
    Calcula a matriz de distâncias ou tempos entre uma lista de pontos.

    Args:
        pontos (list): Lista de tuplas (latitude, longitude).
        provider (str): Provedor de roteamento (atualmente suporta apenas "osrm").
        metrica (str): 'duration' (tempo em segundos) ou 'distance' (distância em metros).

    Returns:
        np.ndarray: Matriz NxN com os valores da métrica solicitada, ou None em caso de erro.
                    Retorna matriz de zeros se n <= 1.
    """
    n = len(pontos)
    if not _validar_coordenadas(pontos):
        # Erro já logado em _validar_coordenadas
        return None # Retorna None se a validação falhar

    if n <= 1:
        logging.info(f"Número de pontos ({n}) insuficiente para calcular matriz. Retornando matriz de zeros.")
        return np.zeros((n, n))

    if provider.lower() != "osrm":
        logging.error(f"Provedor '{provider}' não suportado.")
        raise NotImplementedError(f"Provedor '{provider}' não suportado.")

    # Formata os pontos para a URL do OSRM: longitude,latitude;longitude,latitude;...
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in pontos])
    # Monta a URL para o serviço 'table'
    url = f"{OSRM_SERVER_URL}/table/v1/driving/{coords_str}"
    params = {
        "annotations": metrica # Pede durations ou distances
    }

    try:
        logging.info(f"Consultando OSRM Table API: {url} com params: {params}")
        response = requests.get(url, params=params, timeout=60) # Timeout de 60s
        response.raise_for_status()  # Lança exceção para erros HTTP (4xx ou 5xx)
        data = response.json()

        if data['code'] != 'Ok':
            logging.error(f"Erro na resposta da API OSRM: {data.get('message', 'Mensagem não disponível')}")
            return None

        matriz_key = f"{metrica}s" # 'durations' ou 'distances'
        if matriz_key not in data:
            logging.error(f"Resposta da API OSRM não contém '{matriz_key}'.")
            return None

        # Converte para numpy array, tratando Nones
        matriz_raw = data[matriz_key]
        matriz = np.array(matriz_raw, dtype=float) # Usa float para acomodar np.inf

        # Substitui None (ou valores inválidos que o OSRM possa retornar) por INFINITE_VALUE
        # O OSRM geralmente retorna valores numéricos grandes, mas garantimos a substituição
        # A API table pode retornar null se não houver rota
        if None in matriz_raw: # Verifica se houve algum None na resposta original
             matriz[np.isnan(matriz)] = INFINITE_VALUE # Substitui Nones (que viram NaN) por infinito
             logging.warning(f"Valores None encontrados na matriz OSRM, substituídos por {INFINITE_VALUE}")

        # Verifica se a matriz tem a forma esperada
        if matriz.shape != (n, n):
            logging.error(f"Erro: Matriz OSRM retornada com forma inesperada {matriz.shape}, esperado ({n},{n})")
            return None

        # Garante que a diagonal principal seja 0
        np.fill_diagonal(matriz, 0)

        logging.info(f"Matriz de {metrica} ({n}x{n}) calculada com sucesso via OSRM.")
        # Retorna como inteiro se não houver infinitos, para compatibilidade com OR-Tools
        if np.all(np.isfinite(matriz)):
             return matriz.astype(int)
        else:
             # Se houver infinitos, pode ser necessário tratar no solver
             # Por segurança, retornamos como float, mas convertendo infinitos para o valor grande
             matriz[np.isinf(matriz)] = INFINITE_VALUE
             return matriz.astype(int)

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de conexão/requisição ao servidor OSRM: {e}")
        return None
    except Exception as e:
        logging.error(f"Erro inesperado ao calcular matriz de distâncias: {e}")
        return None


def calcular_distancia(ponto_a, ponto_b, provider="osrm", metrica="duration"):
    """
    Calcula a distância ou tempo entre dois pontos específicos.
    Nota: Menos eficiente que calcular a matriz inteira se precisar de muitos pares.

    Args:
        ponto_a (tuple): Tupla (latitude, longitude) do ponto de origem.
        ponto_b (tuple): Tupla (latitude, longitude) do ponto de destino.
        provider (str): Provedor de roteamento (atualmente suporta apenas "osrm").
        metrica (str): 'duration' (tempo em segundos) ou 'distance' (distância em metros).

    Returns:
        float: Valor da métrica solicitada, ou None em caso de erro.
    """
    if not _validar_coordenadas([ponto_a, ponto_b]):
        return INFINITE_VALUE # Retorna infinito se a validação falhar

    if provider.lower() != "osrm":
        logging.error(f"Provedor '{provider}' não suportado.")
        raise NotImplementedError(f"Provedor '{provider}' não suportado.")

    lat_a, lon_a = ponto_a
    lat_b, lon_b = ponto_b

    # Formata os pontos para a URL do OSRM: longitude,latitude;longitude,latitude
    coords_str = f"{lon_a},{lat_a};{lon_b},{lat_b}"
    # Monta a URL para o serviço 'route'
    url = f"{OSRM_SERVER_URL}/route/v1/driving/{coords_str}"
    params = {
        "overview": "false", # Não precisamos da geometria da rota
        "annotations": "false" # Não precisamos de anotações detalhadas
    }

    try:
        logging.info(f"Consultando OSRM Route API: {url}")
        response = requests.get(url, params=params, timeout=30) # Timeout de 30s
        response.raise_for_status()
        data = response.json()

        if data['code'] != 'Ok' or not data.get('routes'):
            logging.warning(f"Rota não encontrada ou erro na API OSRM entre {ponto_a} e {ponto_b}: {data.get('message', 'Sem rota')}")
            return INFINITE_VALUE # Retorna infinito se não houver rota

        # Extrai a métrica da primeira rota encontrada
        route_data = data['routes'][0]
        if metrica == "duration":
            valor = route_data.get('duration')
        elif metrica == "distance":
            valor = route_data.get('distance')
        else:
            logging.error(f"Métrica '{metrica}' não reconhecida pela implementação.")
            return None

        if valor is None:
             logging.warning(f"API OSRM não retornou valor para a métrica '{metrica}' entre {ponto_a} e {ponto_b}.")
             return INFINITE_VALUE # Retorna infinito se valor for None

        logging.info(f"{metrica.capitalize()} entre {ponto_a} e {ponto_b}: {valor}")
        return int(valor) # Retorna como inteiro

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de conexão/requisição ao servidor OSRM: {e}")
        return INFINITE_VALUE # Retorna infinito em caso de erro de conexão
    except Exception as e:
        logging.error(f"Erro inesperado ao calcular {metrica}: {e}")
        return INFINITE_VALUE # Retorna infinito em caso de erro inesperado

# Exemplo de uso (pode ser removido ou comentado)
if __name__ == '__main__':
    # Pontos de exemplo (latitude, longitude) - São Paulo
    pontos_exemplo = [
        (-23.5505, -46.6333), # Centro SP
        (-23.5614, -46.6559), # Av. Paulista
        (-23.6825, -46.6994), # Aeroporto Congonhas
        (-23.5475, -46.6361)  # Próximo ao centro
    ]

    print("\\n--- Teste calcular_matriz_distancias (Duração) ---")
    matriz_duracao = calcular_matriz_distancias(pontos_exemplo, metrica="duration")
    if matriz_duracao is not None:
        print(matriz_duracao)

    print("\\n--- Teste calcular_matriz_distancias (Distância) ---")
    matriz_distancia = calcular_matriz_distancias(pontos_exemplo, metrica="distance")
    if matriz_distancia is not None:
        print(matriz_distancia)

    print("\\n--- Teste calcular_distancia (Duração) ---")
    duracao_0_1 = calcular_distancia(pontos_exemplo[0], pontos_exemplo[1], metrica="duration")
    if duracao_0_1 is not None:
        print(f"Duração entre ponto 0 e 1: {duracao_0_1:.2f} segundos")

    print("\\n--- Teste calcular_distancia (Distância) ---")
    distancia_0_1 = calcular_distancia(pontos_exemplo[0], pontos_exemplo[1], metrica="distance")
    if distancia_0_1 is not None:
        print(f"Distância entre ponto 0 e 1: {distancia_0_1:.2f} metros")

    print("\\n--- Teste com poucos pontos ---")
    matriz_um_ponto = calcular_matriz_distancias([pontos_exemplo[0]])
    print("Matriz com 1 ponto:")
    print(matriz_um_ponto)

    matriz_zero_pontos = calcular_matriz_distancias([])
    print("Matriz com 0 pontos:")
    print(matriz_zero_pontos)
