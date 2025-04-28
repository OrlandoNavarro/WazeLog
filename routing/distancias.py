"""
Cálculo de matriz de distâncias/tempos entre pontos usando OSRM, Mapbox, Google, etc.
"""
import requests
import numpy as np
import logging
import os
import traceback
import time

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL do servidor OSRM - busca variável de ambiente ou usa default público
OSRM_SERVER_URL = os.environ.get("OSRM_URL", "http://router.project-osrm.org")

# Constante para valor grande representando infinito para OR-Tools
INFINITE_VALUE = 9999999 # Ajuste conforme necessário

# Limite máximo de pontos por requisição GET (ajuste conforme necessário)
MAX_POINTS_PER_GET = 50 # Definir um limite seguro para GET

def _validar_coordenadas(pontos):
    """Verifica se a lista de pontos contém coordenadas válidas."""
    if not isinstance(pontos, list):
        logging.error("Entrada 'pontos' não é uma lista.")
        return False
    if not pontos: # Adiciona verificação para lista vazia
        logging.warning("Lista de pontos está vazia.")
        return True # Lista vazia é "válida" para evitar erro, mas resultará em matriz 0x0
    for i, ponto in enumerate(pontos):
        if not isinstance(ponto, (tuple, list)) or len(ponto) != 2:
            logging.error(f"Ponto inválido na posição {i}: {ponto}. Deve ser tupla/lista de 2 elementos.")
            return False
        try:
            lat, lon = ponto
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                logging.error(f"Coordenadas inválidas na posição {i}: {ponto}. Devem ser numéricas.")
                return False
            # Relaxando a validação estrita de range, pois OSRM pode lidar com pequenas imprecisões
            # if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            #     logging.warning(f"Coordenadas fora do intervalo padrão na posição {i}: ({lat}, {lon}).")
        except (TypeError, ValueError) as e:
             logging.error(f"Erro ao desempacotar ou validar coordenadas na posição {i}: {ponto} - {e}")
             return False
    return True

# <<< Modificar _get_osrm_table_batch para incluir retentativas >>>
def _get_osrm_table_batch(url_base, batch_coords_str, metrica, timeout=120, max_retries=3, retry_delay=5):
    """
    Faz a requisição GET para a OSRM Table API, com retentativas para erros 5xx.
    """
    matriz_key = 'distances' if metrica == 'distance' else 'durations'
    params = {'annotations': metrica}
    url = url_base + batch_coords_str

    for attempt in range(max_retries):
        try:
            logging.info(f"Consultando OSRM Table API via GET (Batch - Tentativa {attempt + 1}/{max_retries}): {url_base}... (params: {params}, timeout={timeout}s)")
            response = requests.get(url, params=params, timeout=timeout)
            logging.info(f"OSRM Status Code (Batch): {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 'Ok' and matriz_key in data:
                    return data[matriz_key]
                else:
                    logging.error(f"Resposta OSRM OK, mas dados inválidos ou chave '{matriz_key}' ausente. Resposta: {data}")
                    return None # Retorna None se a resposta não for válida

            # <<< Lógica de Retentativa para erros 5xx >>>
            elif response.status_code >= 500:
                logging.warning(f"Erro HTTP {response.status_code} do OSRM API (Tentativa {attempt + 1}/{max_retries}). Tentando novamente em {retry_delay}s...")
                if attempt < max_retries - 1: # Não espera na última tentativa
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Máximo de retentativas ({max_retries}) atingido para erro {response.status_code}.")
                    logging.error(f"Corpo da resposta OSRM (erro lote): {response.text}")
                    return None # Falhou após retentativas
            else: # Outros erros HTTP (ex: 4xx) - não tenta novamente
                logging.error(f"Erro HTTP {response.status_code} inesperado do OSRM API: {response.text}")
                return None

        except requests.exceptions.Timeout:
            logging.warning(f"Timeout ({timeout}s) ao conectar com OSRM API (Tentativa {attempt + 1}/{max_retries}). Tentando novamente em {retry_delay}s...")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logging.error(f"Máximo de retentativas ({max_retries}) atingido devido a timeouts.")
                return None # Falhou após retentativas
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de requisição ao OSRM API (Tentativa {attempt + 1}/{max_retries}): {e}")
            # Pode ser um erro de conexão, etc. Tenta novamente.
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logging.error(f"Máximo de retentativas ({max_retries}) atingido devido a erros de requisição.")
                return None # Falhou após retentativas

    return None # Caso algo inesperado ocorra no loop

def calcular_matriz_distancias(pontos, provider="osrm", metrica="duration", progress_callback=None):
    """
    Calcula a matriz de distâncias ou tempos entre uma lista de pontos.
    Usa GET em lotes se o número de pontos for muito grande.
    """
    if not _validar_coordenadas(pontos):
        return None

    n = len(pontos)
    if n <= 1:
        logging.info(f"Número de pontos ({n}) insuficiente. Retornando matriz ({n},{n}).")
        return np.zeros((n, n), dtype=int)

    if provider.lower() != "osrm":
        logging.error(f"Provedor '{provider}' não suportado.")
        return None

    # Inicializa a matriz final com valores infinitos (ou zero na diagonal)
    final_matrix = np.full((n, n), INFINITE_VALUE, dtype=int)
    np.fill_diagonal(final_matrix, 0)

    url_base = f"{OSRM_SERVER_URL}/table/v1/driving/"
    delay_between_requests = 0.5 # <<< Adicionar delay de 0.5 segundos

    try:
        # Divide os índices dos pontos em lotes
        indices = list(range(n))
        batches = [indices[i:i + MAX_POINTS_PER_GET] for i in range(0, n, MAX_POINTS_PER_GET)]
        num_batches = len(batches)
        total_requests = num_batches * num_batches
        request_count = 0
        logging.info(f"Dividindo {n} pontos em {num_batches} lotes. Total de {total_requests} requisições OSRM.")

        # Itera sobre todas as combinações de lotes de origem e destino
        for r_idx, batch_origem in enumerate(batches):
            for c_idx, batch_destino in enumerate(batches):
                request_count += 1
                logging.info(f"Calculando submatriz Lote {r_idx+1}/{num_batches} -> Lote {c_idx+1}/{num_batches} (Req {request_count}/{total_requests})")

                # Combina os índices dos dois lotes e remove duplicatas para a chamada API
                combined_indices = sorted(list(set(batch_origem + batch_destino)))
                if not combined_indices: continue # Pula se lote combinado for vazio

                # Mapeia índice original para índice dentro do lote combinado
                original_to_combined = {orig_idx: i for i, orig_idx in enumerate(combined_indices)}

                # Formata coordenadas para o lote combinado
                batch_points = [pontos[i] for i in combined_indices]
                batch_coords_str = ";".join([f"{lon},{lat}" for lat, lon in batch_points])

                # <<< Chama a função _get_osrm_table_batch modificada (com retentativas) >>>
                partial_matrix_raw = _get_osrm_table_batch(url_base, batch_coords_str, metrica)

                # <<< Adiciona verificação se partial_matrix_raw é None >>>
                if partial_matrix_raw is None:
                    logging.error(f"Falha ao obter dados do OSRM para o lote (Req {request_count}/{total_requests}) após retentativas. Abortando cálculo da matriz.")
                    return None # Aborta o cálculo se uma requisição falhar permanentemente

                # Preenche a matriz final com os resultados da matriz parcial
                for i_orig in batch_origem:
                    for j_dest in batch_destino:
                        # Encontra os índices correspondentes na matriz parcial
                        try:
                            idx_partial_orig = original_to_combined[i_orig]
                            idx_partial_dest = original_to_combined[j_dest]

                            value = partial_matrix_raw[idx_partial_orig][idx_partial_dest]

                            if value is None:
                                final_matrix[i_orig, j_dest] = INFINITE_VALUE
                            elif isinstance(value, (int, float)):
                                final_matrix[i_orig, j_dest] = int(round(value))
                            else:
                                logging.warning(f"Valor inesperado {value} na submatriz para ({i_orig},{j_dest}). Usando {INFINITE_VALUE}.")
                                final_matrix[i_orig, j_dest] = INFINITE_VALUE
                        except (KeyError, IndexError) as e:
                             logging.error(f"Erro ao mapear/acessar índices ({i_orig},{j_dest}) -> ({idx_partial_orig},{idx_partial_dest}) na submatriz: {e}")
                             final_matrix[i_orig, j_dest] = INFINITE_VALUE # Marca como infinito em caso de erro

                # Chama o callback
                if progress_callback:
                    try:
                        progress_callback(request_count, total_requests)
                    except Exception as e:
                        logging.error(f"Erro no callback de progresso: {e}")

                # Adiciona o delay (pode ser removido ou ajustado se as retentativas tiverem delay)
                # logging.debug(f"Aguardando {delay_between_requests}s antes da próxima requisição...")
                # time.sleep(delay_between_requests) # Comentado pois já há delay nas retentativas

        # Verifica se algum valor permaneceu infinito (exceto diagonal) - pode indicar falha parcial
        if np.any(final_matrix[~np.eye(n, dtype=bool)] == INFINITE_VALUE):
             logging.warning(f"Matriz final contém valores infinitos ({INFINITE_VALUE}), indicando possíveis falhas em rotas individuais ou lotes.")

        logging.info(f"Matriz de '{metrica}' ({final_matrix.shape}) calculada com sucesso usando lotes.")
        return final_matrix

    except requests.exceptions.Timeout:
        logging.error(f"Timeout (120s) ao conectar com OSRM API durante processamento em lote (Req {request_count}/{total_requests}).")
        return None
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Erro de conexão com OSRM API durante processamento em lote (Req {request_count}/{total_requests}). Erro: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 'N/A'
        reason = e.response.reason if e.response is not None else 'N/A'
        logging.error(f"Erro HTTP do OSRM API durante processamento em lote (Req {request_count}/{total_requests}): {status_code} - {reason}.")
        try:
            if e.response is not None:
                 logging.error(f"Corpo da resposta OSRM (erro lote): {e.response.text[:500]}")
        except Exception:
            pass
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro genérico de requisição ao OSRM API durante processamento em lote (Req {request_count}/{total_requests}): {e}.")
        return None
    except ValueError as e: # Erro JSON ou erro levantado por _get_osrm_table_batch
        logging.error(f"Erro ao processar resposta OSRM em lote (Req {request_count}/{total_requests}): {e}")
        return None
    except Exception as e:
        logging.error(f"Erro inesperado durante cálculo da matriz OSRM em lote (Req {request_count}/{total_requests}): {e}")
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
