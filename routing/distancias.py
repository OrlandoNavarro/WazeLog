"""
Cálculo de matriz de distâncias/tempos entre pontos usando OSRM, Mapbox, Google, etc.
"""
import requests
import numpy as np
import logging
import os
import traceback
import time
import json

# Constantes
OSRM_SERVER_URL = os.environ.get("OSRM_SERVER_URL", "http://router.project-osrm.org")
INFINITE_VALUE = 9999999  # Valor alto para representar infinito

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _get_osrm_table_batch(url_base, batch_coords_str, metrica, timeout=120, max_retries=3, retry_delay=5):
    """
    Faz a requisição GET para a OSRM Table API, com retentativas para erros 5xx e log detalhado.
    """
    matriz_key = 'distances' if metrica == 'distance' else 'durations'
    params = {'annotations': metrica}
    url = url_base + batch_coords_str # A URL completa

    logging.debug(f"OSRM Request URL (sem params): {url_base}") # Log base
    logging.debug(f"OSRM Request Coords String: {batch_coords_str}") # Log coordenadas
    logging.debug(f"OSRM Request Params: {params}") # Log parâmetros

    for attempt in range(max_retries):
        try:
            # Log da tentativa incluindo a URL completa para facilitar a depuração
            logging.info(f"Consultando OSRM Table API via GET (Batch - Tentativa {attempt + 1}/{max_retries}): {url}?annotations={metrica} (timeout={timeout}s)")
            response = requests.get(url, params=params, timeout=timeout)
            logging.info(f"OSRM Status Code (Batch): {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('code') == 'Ok' and matriz_key in data:
                        return data[matriz_key]
                    else:
                        logging.error(f"Resposta OSRM OK, mas dados inválidos ou chave '{matriz_key}' ausente. Resposta: {data}")
                        return None
                except json.JSONDecodeError:
                    logging.error(f"Resposta OSRM 200, mas não é um JSON válido. Resposta: {response.text}")
                    return None

            elif response.status_code >= 500:
                logging.warning(f"Erro HTTP {response.status_code} do OSRM API (Tentativa {attempt + 1}/{max_retries}). Coords: {batch_coords_str}. Tentando novamente em {retry_delay}s...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Máximo de retentativas ({max_retries}) atingido para erro {response.status_code}. Coords: {batch_coords_str}")
                    logging.error(f"Corpo da resposta OSRM (erro lote): {response.text}")
                    return None
            # <<< Log específico para erro 400 >>>
            elif response.status_code == 400:
                 logging.error(f"Erro HTTP 400 (Bad Request) do OSRM API. Verifique a string de coordenadas e a URL.")
                 logging.error(f"URL Completa Enviada: {response.request.url}") # Loga a URL exata que foi enviada
                 logging.error(f"Coordenadas Enviadas: {batch_coords_str}")
                 logging.error(f"Corpo da Resposta (Erro 400): {response.text}")
                 return None # Não tenta novamente para erro 400
            else:
                logging.error(f"Erro HTTP {response.status_code} inesperado do OSRM API: {response.text}. Coords: {batch_coords_str}")
                return None # Não tenta novamente para outros erros

        except requests.exceptions.Timeout:
            logging.warning(f"Timeout ({timeout}s) ao conectar com OSRM API (Tentativa {attempt + 1}/{max_retries}). Coords: {batch_coords_str}. Tentando novamente em {retry_delay}s...")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logging.error(f"Máximo de retentativas ({max_retries}) atingido devido a timeouts. Coords: {batch_coords_str}")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de requisição ao OSRM API (Tentativa {attempt + 1}/{max_retries}): {e}. Coords: {batch_coords_str}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logging.error(f"Máximo de retentativas ({max_retries}) atingido devido a erros de requisição. Coords: {batch_coords_str}")
                return None

    return None

# --- Funções de Validação Adicionadas ---
def _is_valid_coord(value):
    """Verifica se um valor de coordenada é um float válido."""
    if value is None: return False
    try:
        float(value) # Tenta converter para float
        return True
    except (ValueError, TypeError):
        return False

def _is_valid_lat_lon(lat, lon):
    """Verifica se lat e lon são números válidos dentro da faixa padrão."""
    if not _is_valid_coord(lat) or not _is_valid_coord(lon): return False
    try:
        lat_f, lon_f = float(lat), float(lon)
        if not (-90 <= lat_f <= 90): return False
        if not (-180 <= lon_f <= 180): return False
        return True
    except (ValueError, TypeError): # Captura erro se a conversão float falhar aqui também
        return False
# -----------------------------------------

def _validar_coordenadas(lista_pontos):
    """Valida uma lista de pontos (lat, lon). Usado principalmente em calcular_distancia."""
    if not lista_pontos:
        return True # Lista vazia é válida
    for i, ponto in enumerate(lista_pontos):
        if not isinstance(ponto, (list, tuple)) or len(ponto) != 2:
            logging.error(f"Formato inválido para ponto no índice {i}: {ponto}. Esperado (latitude, longitude).")
            return False
        lat, lon = ponto
        if not _is_valid_lat_lon(lat, lon):
             # Log de erro já acontece em _is_valid_lat_lon se chamado de lá
             # Adicionamos um log aqui para o contexto da lista
             logging.error(f"Coordenadas inválidas encontradas na validação da lista no índice {i}: ({lat}, {lon}).")
             return False
    return True

def calcular_matriz_distancias(pontos, provider="osrm", metrica="duration", progress_callback=None):
    """
    Calcula a matriz de distâncias ou tempos usando OSRM Table API em lotes,
    validando coordenadas antes de cada requisição.
    """
    n = len(pontos)
    if n == 0:
        logging.info("Lista de pontos vazia, retornando matriz vazia.")
        return np.array([]).reshape(0, 0)

    if provider.lower() != "osrm":
        logging.error(f"Provedor '{provider}' não suportado.")
        raise NotImplementedError(f"Provedor '{provider}' não suportado.")

    url_base = f"{OSRM_SERVER_URL}/table/v1/driving/"
    final_matrix = np.full((n, n), INFINITE_VALUE, dtype=int)
    np.fill_diagonal(final_matrix, 0)

    # --- AJUSTE AQUI ---
    max_coords_per_request = 50 # Reduzido de 100 para 50
    # -------------------
    num_batches = (n + max_coords_per_request - 1) // max_coords_per_request
    batches = [list(range(i * max_coords_per_request, min((i + 1) * max_coords_per_request, n))) for i in range(num_batches)]
    total_requests = num_batches * num_batches

    logging.info(f"Dividindo {n} pontos em {num_batches} lotes (máx {max_coords_per_request} por lote). Total de {total_requests} requisições OSRM.")
    request_count = 0

    try:
        for r_idx, batch_origem_indices in enumerate(batches):
            for c_idx, batch_destino_indices in enumerate(batches):
                request_count += 1
                logging.info(f"Calculando submatriz Lote {r_idx+1}/{num_batches} -> Lote {c_idx+1}/{num_batches} (Req {request_count}/{total_requests})")

                combined_indices_list = sorted(list(set(batch_origem_indices + batch_destino_indices)))
                if not combined_indices_list: continue

                # --- Validação e Preparação dos Pontos para OSRM ---
                osrm_points_coords = []   # Lista de (lat, lon) válidos para OSRM
                osrm_indices_map = {}     # Mapeia índice original -> índice na lista osrm_points_coords
                invalid_original_indices = set() # Guarda índices originais inválidos neste lote

                for orig_idx in combined_indices_list:
                    # Pega lat/lon do ponto original
                    try:
                        lat, lon = pontos[orig_idx]
                    except IndexError:
                         logging.error(f"Índice original {orig_idx} fora dos limites da lista de pontos (tamanho {n}). Abortando.")
                         return None # Erro crítico

                    # Valida as coordenadas
                    if _is_valid_lat_lon(lat, lon):
                        # Adiciona à lista para OSRM (convertendo para float aqui) e mapeia
                        osrm_points_coords.append((float(lat), float(lon)))
                        osrm_indices_map[orig_idx] = len(osrm_points_coords) - 1
                    else:
                        logging.warning(f"Coordenadas inválidas detectadas para ponto índice {orig_idx}: ({lat}, {lon}). Será tratado como inalcançável nesta requisição (Req {request_count}).")
                        invalid_original_indices.add(orig_idx)
                # -------------------------------------------------

                if not osrm_points_coords:
                    logging.warning(f"Nenhum ponto válido encontrado no lote combinado (Req {request_count}). Pulando requisição OSRM.")
                    continue # Pula para o próximo par de lotes

                # --- Requisição OSRM com Pontos Válidos ---
                # Verifica se há pelo menos 2 pontos válidos para a requisição
                if len(osrm_points_coords) < 2:
                     logging.warning(f"Menos de 2 pontos válidos ({len(osrm_points_coords)}) no lote combinado (Req {request_count}). Pulando requisição OSRM.")
                     # A matriz já está inicializada com INFINITE_VALUE, então pular está ok.
                     continue

                # Formata a string apenas com coordenadas válidas
                batch_coords_str = ";".join([f"{lon},{lat}" for lat, lon in osrm_points_coords])
                partial_matrix_raw = _get_osrm_table_batch(url_base, batch_coords_str, metrica)

                if partial_matrix_raw is None:
                    logging.error(f"Falha ao obter dados do OSRM para o lote (Req {request_count}/{total_requests}). Abortando cálculo da matriz.")
                    return None # Aborta se a requisição falhar

                # --- Preenchimento da Matriz Final ---
                partial_matrix = np.array(partial_matrix_raw)
                num_osrm_points = len(osrm_points_coords)
                if partial_matrix.shape != (num_osrm_points, num_osrm_points):
                     logging.error(f"Dimensão inesperada da matriz OSRM recebida ({partial_matrix.shape}) para {num_osrm_points} pontos válidos. Abortando.")
                     return None

                # Itera sobre os pares de índices ORIGINAIS dos lotes combinados
                for orig_idx_src in combined_indices_list:
                    for orig_idx_dst in combined_indices_list:
                        # Só atualiza se o par pertence aos lotes atuais
                        if orig_idx_src in batch_origem_indices and orig_idx_dst in batch_destino_indices:

                            # Verifica se ambos os pontos eram válidos para esta requisição OSRM
                            if orig_idx_src in invalid_original_indices or orig_idx_dst in invalid_original_indices:
                                if orig_idx_src != orig_idx_dst:
                                     final_matrix[orig_idx_src, orig_idx_dst] = INFINITE_VALUE
                                # else: diagonal já é 0
                            else:
                                # Ambos válidos, busca os índices na matriz parcial
                                osrm_i = osrm_indices_map[orig_idx_src]
                                osrm_j = osrm_indices_map[orig_idx_dst]
                                value = partial_matrix[osrm_i, osrm_j]

                                if orig_idx_src == orig_idx_dst:
                                    final_matrix[orig_idx_src, orig_idx_dst] = 0
                                else:
                                    final_matrix[orig_idx_src, orig_idx_dst] = int(value) if value is not None else INFINITE_VALUE

                if progress_callback:
                    try:
                        progress_callback(request_count / total_requests)
                    except Exception as e_cb:
                        logging.warning(f"Erro ao chamar progress_callback: {e_cb}")

        logging.info(f"Matriz de '{metrica}' ({final_matrix.shape}) calculada com sucesso usando lotes.")
        return final_matrix

    except Exception as e:
        logging.error(f"Erro inesperado durante cálculo da matriz OSRM em lote: {e}")
        logging.error(traceback.format_exc())
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
