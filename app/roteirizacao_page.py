import streamlit as st
import pandas as pd
import numpy as np # Adicionado para uso potencial
import time # Adicionado para uso potencial

# Importações adicionadas para funcionalidade completa
from database import (
    carregar_pedidos,
    carregar_frota,
    salvar_endereco_partida,
    carregar_endereco_partida
)
# Ajuste na importação dos solvers para pegar do módulo correto
from routing.vrp import solver_vrp
from routing.cvrp import solver_cvrp
from routing.vrptw import solver_vrptw
from routing.tsp import solver_tsp
# from routing.ortools_solver import solver_vrp, solver_cvrp, solver_vrptw, solver_tsp # Comentado - Usar imports diretos
from routing.distancias import calcular_matriz_distancias
from pedidos import obter_coordenadas # Para geocodificação do endereço de partida

# Constantes para endereço de partida padrão
DEFAULT_ENDERECO_PARTIDA = "Avenida Antonio Ortega, 3604 - Pinhal, Cabreúva - SP, 13315-000"
DEFAULT_LAT_PARTIDA = -23.251501
DEFAULT_LON_PARTIDA = -47.084560

def show():
    # Inicializa o estado da sessão para cenários, se necessário
    if 'cenarios_roteirizacao' not in st.session_state:
        st.session_state.cenarios_roteirizacao = []

    st.header("Roteirizador de Entregas", divider="rainbow") # Usando header como no original
    st.write("Carregue os dados, configure a partida, selecione o tipo de roteirização e calcule as rotas.")
    st.divider()

    # Variáveis para armazenar dados carregados e coordenadas de partida
    pedidos = None
    frota = None
    lat_partida = None
    lon_partida = None
    endereco_partida = None
    pedidos_nao_alocados = pd.DataFrame() # Inicializa vazio

    try:
        # Carrega os dataframes usando as funções do database
        pedidos = carregar_pedidos()
        frota = carregar_frota()

        # Processamento da Frota
        if frota is not None and not frota.empty:
             frota = frota.loc[:, ~frota.columns.duplicated()] # Remove colunas duplicadas
             if 'Disponível' in frota.columns:
                  # Filtra disponíveis (se necessário, aplicar filtro aqui)
                  # frota = frota[frota['Disponível'] == True] # Exemplo
                  pass # Por enquanto, não filtra
             else:
                 st.warning("Coluna 'Disponível' não encontrada na frota. Considerando todos os veículos.")
        else:
             st.warning("Não foi possível carregar dados da frota ou a frota está vazia.")
             frota = pd.DataFrame() # Dataframe vazio para evitar erros

        # Processamento dos Pedidos
        if pedidos is not None and not pedidos.empty:
            if 'Região' in pedidos.columns:
                pedidos_sorted = pedidos.sort_values(by='Região').reset_index(drop=True)
            else:
                st.warning("Coluna 'Região' não encontrada nos pedidos. Exibindo sem ordenação por região.")
                pedidos_sorted = pedidos
            # Separa pedidos não alocados (sem coordenadas) ANTES de filtrar
            pedidos_nao_alocados = pedidos[pedidos['Latitude'].isna() | pedidos['Longitude'].isna()].copy()
            pedidos_validos = pedidos.dropna(subset=['Latitude', 'Longitude']).copy()
        else:
            st.warning("Não foi possível carregar dados dos pedidos ou não há pedidos.")
            pedidos = pd.DataFrame() # Dataframe vazio
            pedidos_sorted = pd.DataFrame()
            pedidos_validos = pd.DataFrame()


        # Exibição lado a lado dos dados carregados
        st.subheader("Dados Carregados")
        col1_data, col2_data = st.columns(2)
        with col1_data:
            st.caption(f"Pedidos ({len(pedidos_sorted)})")
            st.dataframe(pedidos_sorted, height=200, use_container_width=True) # Ajuste de altura e largura
        with col2_data:
            st.caption(f"Frota Disponível ({len(frota)})")
            st.dataframe(frota, height=200, use_container_width=True) # Ajuste de altura e largura

        st.divider()

        # --- Configuração do Endereço de Partida ---
        st.subheader("Endereço de Partida (Depósito)")
        with st.expander("Configurar Endereço e Coordenadas", expanded=True):
            endereco_partida_salvo, lat_partida_salva, lon_partida_salva = carregar_endereco_partida()
            endereco_partida = st.text_input(
                "Endereço de partida",
                endereco_partida_salvo or DEFAULT_ENDERECO_PARTIDA,
                key="endereco_partida_input"
            )
            col1_addr, col2_addr = st.columns(2)
            with col1_addr:
                lat_partida_manual = st.text_input(
                    "Latitude",
                    f"{lat_partida_salva:.6f}" if lat_partida_salva is not None else str(DEFAULT_LAT_PARTIDA),
                    key="lat_partida_input"
                )
            with col2_addr:
                lon_partida_manual = st.text_input(
                    "Longitude",
                    f"{lon_partida_salva:.6f}" if lon_partida_salva is not None else str(DEFAULT_LON_PARTIDA),
                    key="lon_partida_input"
                )

            usar_coord_manual = st.checkbox("Usar coordenadas manuais", value=False, key="usar_coord_manual_cb")

            if endereco_partida:
                if usar_coord_manual:
                    try:
                        lat_partida = float(lat_partida_manual.replace(',', '.')) # Trata vírgula decimal
                        lon_partida = float(lon_partida_manual.replace(',', '.'))
                        st.info(f"Usando coordenadas manuais: {lat_partida:.6f}, {lon_partida:.6f}")
                        # Salva as coordenadas manuais junto com o endereço atual
                        salvar_endereco_partida(endereco_partida, lat_partida, lon_partida)
                    except (ValueError, TypeError):
                        st.error("Coordenadas manuais inválidas. Insira números válidos.")
                        lat_partida, lon_partida = None, None # Invalida
                else:
                    # Verifica se o endereço mudou ou se não há coordenadas salvas para ele
                    if endereco_partida != endereco_partida_salvo or lat_partida_salva is None or lon_partida_salva is None:
                        with st.spinner(f"Buscando coordenadas para {endereco_partida}..."):
                            coords = obter_coordenadas(endereco_partida)
                            if coords:
                                lat_partida, lon_partida = coords
                                st.success(f"Coordenadas encontradas: {lat_partida:.6f}, {lon_partida:.6f}")
                                salvar_endereco_partida(endereco_partida, lat_partida, lon_partida)
                            else:
                                st.error(f"Não foi possível encontrar coordenadas para o endereço: {endereco_partida}. Tente inserir manualmente.")
                                lat_partida, lon_partida = None, None # Invalida
                    else:
                        # Usa as coordenadas salvas
                        lat_partida, lon_partida = lat_partida_salva, lon_partida_salva
                        st.info(f"Usando coordenadas salvas para o endereço: {lat_partida:.6f}, {lon_partida:.6f}")

                # Exibe o status final das coordenadas de partida
                if lat_partida is None or lon_partida is None:
                     st.warning("Coordenadas de partida inválidas ou não definidas.")
                # else: # Info já exibida acima
                #      st.info(f"Coordenadas de partida definidas: {lat_partida:.6f}, {lon_partida:.6f}")

            else:
                st.warning("Endereço de partida não pode estar vazio.")
                lat_partida, lon_partida = None, None # Invalida

        st.divider()

        # --- Seleção do Tipo de Roteirização ---
        st.subheader("Configuração da Roteirização")
        tipo = st.selectbox(
            "Selecione o tipo de problema de roteirização",
            ["CVRP", "VRP", "VRPTW", "TSP"], # CVRP como padrão
            key="tipo_roteirizacao_select",
            help="Escolha o algoritmo de roteirização baseado nas restrições do seu problema."
        )
        explicacoes = {
            "VRP": "VRP (Vehicle Routing Problem): Minimiza a distância total com múltiplos veículos, sem restrição de capacidade.",
            "CVRP": "CVRP (Capacitated VRP): Considera a capacidade máxima (Kg ou Cx) dos veículos.",
            "VRPTW": "VRPTW (VRP with Time Windows): Considera janelas de tempo para entrega nos clientes e operação dos veículos.",
            "TSP": "TSP (Traveling Salesman Problem): Roteirização para um único 'veículo' visitando todos os pontos."
        }
        st.info(explicacoes.get(tipo, ""))

        # --- Resumo dos Dados para Roteirização ---
        with st.container(border=True): # Adiciona borda ao container
            st.markdown("##### Resumo para Cálculo")
            # Primeira linha: Pedidos com Coordenadas | Peso Total (Kg)
            col1_sum, col2_sum = st.columns(2)
            # pedidos_validos já foi definido acima
            with col1_sum:
                st.metric("Pedidos com Coordenadas", len(pedidos_validos))
            with col2_sum:
                peso_total = pedidos_validos['Peso dos Itens'].sum() if 'Peso dos Itens' in pedidos_validos.columns else 0
                st.metric("Peso Total (Kg)", f"{peso_total:,.1f}")
            # Segunda linha: Veículos Disponíveis | Capacidade Total (Kg)
            col3_sum, col4_sum = st.columns(2)
            with col3_sum:
                st.metric("Veículos Disponíveis", len(frota))
            with col4_sum:
                capacidade_total_kg = frota['Capacidade (Kg)'].sum() if 'Capacidade (Kg)' in frota.columns and not frota.empty else 0
                st.metric("Capacidade Total (Kg)", f"{capacidade_total_kg:,.1f}")
            # Adicionar outras métricas relevantes se necessário (e.g., Volume Total)

        st.divider()

        # --- Botão de Cálculo e Execução ---
        if st.button("Calcular Rotas Otimizadas", type="primary", use_container_width=True, key="calcular_rotas_btn"):
            # Validações antes de prosseguir
            if lat_partida is None or lon_partida is None:
                st.error("Erro: Coordenadas de partida inválidas. Verifique a configuração do endereço de partida.")
            elif pedidos_validos.empty:
                st.error("Erro: Nenhum pedido com coordenadas válidas encontrado para roteirizar.")
            elif frota.empty and tipo != "TSP": # TSP pode não precisar de frota definida
                 st.error(f"Erro: A frota está vazia, não é possível calcular rotas para {tipo}.")
            else:
                # Preparar dados comuns para todos os solvers
                depot_coord = (lat_partida, lon_partida)
                customer_coords = pedidos_validos[['Latitude', 'Longitude']].values.tolist()
                all_locations = [depot_coord] + customer_coords
                # pedidos_nao_alocados já foi definido acima
                depot_index = 0 # Índice do depósito na lista all_locations

                matriz_distancias = None
                matriz_tempos = None

                # Calcular Matriz de Distâncias (necessária para VRP, CVRP, TSP e cálculo final de distância)
                with st.spinner("Calculando matriz de distâncias..."):
                    try:
                        # CORREÇÃO: Usar 'metrica' em vez de 'metric'
                        matriz_distancias = calcular_matriz_distancias(all_locations, metrica='distance')
                        if matriz_distancias is None or len(matriz_distancias) != len(all_locations):
                             st.error("Falha ao calcular a matriz de distâncias completa.")
                             matriz_distancias = None # Garante que não prossiga se falhar
                        else:
                             st.success(f"Matriz de distâncias ({matriz_distancias.shape}) calculada.")
                    except Exception as e:
                        st.error(f"Erro no cálculo da matriz de distâncias: {e}")
                        matriz_distancias = None

                # Calcular Matriz de Tempos (essencial para VRPTW)
                if tipo == "VRPTW":
                    with st.spinner("Calculando matriz de tempos..."):
                        try:
                            # CORREÇÃO: Usar 'metrica' em vez de 'metric'
                            # Usar 'duration' para obter tempos em segundos
                            matriz_tempos = calcular_matriz_distancias(all_locations, metrica='duration')
                            if matriz_tempos is None or len(matriz_tempos) != len(all_locations):
                                st.error("Falha ao calcular a matriz de tempos completa.")
                                matriz_tempos = None
                            else:
                                # OSRM retorna segundos, converter para minutos se o solver esperar minutos
                                # matriz_tempos = (matriz_tempos / 60).round().astype(int)
                                # Vamos assumir que o solver lida com segundos por enquanto.
                                st.success(f"Matriz de tempos ({matriz_tempos.shape}) calculada (em segundos).")
                        except Exception as e:
                            st.error(f"Erro no cálculo da matriz de tempos: {e}")
                            matriz_tempos = None

                # Prosseguir apenas se as matrizes necessárias estiverem prontas
                # VRPTW precisa de matriz_tempos E matriz_distancias (para cálculo final)
                # Outros precisam apenas de matriz_distancias
                matriz_ok = (matriz_distancias is not None) if tipo != "VRPTW" else (matriz_tempos is not None and matriz_distancias is not None)

                if matriz_ok:
                    rotas = None
                    rotas_df = pd.DataFrame() # Inicializa dataframe vazio
                    resultado_solver = None # Para armazenar o dict do VRPTW ou o DataFrame dos outros
                    status_solver = "Não executado"

                    with st.spinner(f"Executando o solver {tipo}..."):
                        try:
                            # Chama o solver apropriado
                            if tipo == "VRP":
                                # VRP geralmente minimiza distância, usa matriz_distancias
                                rotas = solver_vrp(pedidos_validos, frota, matriz_distancias, depot_index=depot_index)
                                rotas_df = rotas # Resultado já é DataFrame
                                status_solver = "OK" if rotas_df is not None and not rotas_df.empty else "Falha ou Sem Solução"
                            elif tipo == "CVRP":
                                # CVRP também minimiza distância, mas considera capacidade
                                if 'Peso dos Itens' not in pedidos_validos.columns:
                                    st.error("Coluna 'Peso dos Itens' necessária para CVRP não encontrada nos pedidos.")
                                    raise ValueError("Faltando 'Peso dos Itens'")
                                elif 'Capacidade (Kg)' not in frota.columns:
                                     st.error("Coluna 'Capacidade (Kg)' necessária para CVRP não encontrada na frota.")
                                     raise ValueError("Faltando 'Capacidade (Kg)'")
                                else:
                                     # Passa a matriz de distâncias
                                     rotas = solver_cvrp(pedidos_validos, frota, matriz_distancias, depot_index=depot_index)
                                     rotas_df = rotas # Resultado já é DataFrame
                                     status_solver = "OK" if rotas_df is not None and not rotas_df.empty else "Falha ou Sem Solução"
                            elif tipo == "VRPTW":
                                st.info("Preparando dados específicos para VRPTW...")

                                # --- Preparação de Dados para VRPTW ---

                                # 1. Demanda (Peso)
                                if 'Peso dos Itens' not in pedidos_validos.columns:
                                    st.error("Coluna 'Peso dos Itens' necessária para VRPTW não encontrada.")
                                    raise ValueError("Faltando 'Peso dos Itens'")
                                demands = [0] + pedidos_validos['Peso dos Itens'].fillna(0).astype(int).tolist()

                                # 2. Capacidade dos Veículos
                                if 'Capacidade (Kg)' not in frota.columns:
                                    st.error("Coluna 'Capacidade (Kg)' necessária para VRPTW não encontrada.")
                                    raise ValueError("Faltando 'Capacidade (Kg)'")
                                vehicle_capacities = frota['Capacidade (Kg)'].fillna(0).astype(int).tolist()
                                num_vehicles = len(frota)

                                # Função auxiliar para converter HH:MM para segundos a partir da meia-noite
                                def time_str_to_seconds(time_str):
                                    try:
                                        hours, minutes = map(int, str(time_str).split(':'))
                                        return hours * 3600 + minutes * 60
                                    except:
                                        return None # Retorna None se a conversão falhar

                                # 3. Janelas de Tempo do Depósito/Veículos
                                depot_start_times = frota['Janela Início'].apply(time_str_to_seconds).tolist()
                                depot_end_times = frota['Janela Fim'].apply(time_str_to_seconds).tolist()

                                if any(t is None for t in depot_start_times) or any(t is None for t in depot_end_times):
                                     st.warning("Algumas janelas de tempo dos veículos ('Janela Início'/'Janela Fim') estão em formato inválido ou ausentes. Verifique 'frota.csv'. Usando 0-86400 (dia inteiro) como fallback.")
                                     # Usar um padrão amplo se houver erro, ou parar? Por enquanto, padrão amplo.
                                     default_window = (0, 86400) # 24 horas em segundos
                                     vehicle_time_windows = [default_window] * num_vehicles
                                else:
                                     vehicle_time_windows = list(zip(depot_start_times, depot_end_times))

                                # 4. Janelas de Tempo dos Clientes (Assumindo que NÃO existem colunas específicas)
                                # PRECISA DE AJUSTE SE HOUVER COLUNAS COMO 'Cliente Janela Inicio', 'Cliente Janela Fim'
                                st.warning("Dados de janela de tempo dos clientes não encontrados em 'pedidos.csv'. Usando a janela do primeiro veículo como padrão para todos os clientes.")
                                if vehicle_time_windows:
                                    default_customer_window = vehicle_time_windows[0] # Usa a janela do primeiro veículo
                                else:
                                    default_customer_window = (0, 86400) # Fallback se janelas dos veículos falharam

                                customer_time_windows = [default_customer_window] * len(customer_coords)
                                # A janela do depósito é a primeira na lista geral
                                # A janela do depósito em si é definida pelas janelas dos veículos no solver
                                time_windows = [default_customer_window] + customer_time_windows # Janela padrão para depósito, será sobrescrita no solver

                                # 5. Tempo de Serviço nos Clientes
                                service_times_seconds = []
                                if 'Janela de Descarga' in pedidos_validos.columns:
                                    st.info("Usando 'Janela de Descarga' (em minutos) como tempo de serviço. Convertendo para segundos.")
                                    try:
                                        # Multiplica por 60 para converter minutos para segundos
                                        service_times_seconds = (pedidos_validos['Janela de Descarga'].fillna(0).astype(int) * 60).tolist()
                                    except ValueError:
                                        st.warning("Não foi possível converter 'Janela de Descarga' para números. Assumindo 0 tempo de serviço.")
                                        service_times_seconds = [0] * len(customer_coords)
                                else:
                                    st.warning("Coluna 'Janela de Descarga' não encontrada. Assumindo 0 tempo de serviço.")
                                    service_times_seconds = [0] * len(customer_coords)
                                # Tempo de serviço no depósito é 0
                                service_times = [0] + service_times_seconds

                                # 6. Montar o dicionário de dados para o solver
                                data_vrptw = {
                                    'time_matrix': matriz_tempos.tolist(),
                                    'time_windows': time_windows,
                                    'num_vehicles': num_vehicles,
                                    'depot': depot_index,
                                    'demands': demands,
                                    'vehicle_capacities': vehicle_capacities,
                                    'service_times': service_times,
                                    'vehicle_time_windows': vehicle_time_windows, # Passando janelas dos veículos
                                    'pedidos_df': pedidos_validos.reset_index(drop=True), # Passa DF para referência
                                    'frota_df': frota.reset_index(drop=True) # Passa DF para referência
                                }

                                # Chamar o solver VRPTW com os dados estruturados
                                resultado_solver = solver_vrptw(data_vrptw) # solver_vrptw retorna um dicionário
                                rotas_df = resultado_solver.get('rotas') if resultado_solver else pd.DataFrame()
                                status_solver = resultado_solver.get('status', 'Status Desconhecido') if resultado_solver else 'Falha na execução'

                            elif tipo == "TSP":
                                # TSP geralmente usa matriz de distâncias
                                rotas = solver_tsp(matriz_distancias) # Ajustar chamada conforme a implementação
                                rotas_df = rotas # Assumindo que retorna DataFrame
                                status_solver = "OK" if rotas_df is not None and not rotas_df.empty else "Falha ou Sem Solução"

                        except ValueError as ve: # Captura erros de dados faltantes levantados acima
                             st.error(f"Erro de dados ao preparar para {tipo}: {ve}")
                             status_solver = f"Erro de Dados: {ve}"
                        except Exception as solver_error:
                             st.error(f"Erro durante a execução do solver {tipo}: {solver_error}")
                             st.exception(solver_error) # Mostra traceback para depuração
                             status_solver = f"Erro Solver: {solver_error}"

                    # Processamento dos resultados (fora do spinner)
                    if rotas_df is not None and not rotas_df.empty:
                        st.success(f"Rotas calculadas com sucesso usando {tipo}! Status: {status_solver}")

                        # <<< ADICIONAR COORDENADAS AO rotas_df ANTES DE EXIBIR/SALVAR >>>
                        if 'Pedido_Index_DF' in rotas_df.columns and not pedidos_validos.empty:
                            try:
                                # Garante que o índice de pedidos_validos seja o padrão para merge
                                pedidos_coords = pedidos_validos.reset_index().rename(columns={'index': 'Original_Index'})
                                # Seleciona apenas as colunas necessárias para o merge
                                coords_to_merge = pedidos_coords[['Original_Index', 'Latitude', 'Longitude']].copy()
                                # Renomeia a coluna de índice para corresponder a 'Pedido_Index_DF'
                                coords_to_merge = coords_to_merge.rename(columns={'Original_Index': 'Pedido_Index_DF'})

                                # Faz o merge para adicionar Lat/Lon ao df_rotas
                                rotas_df = pd.merge(
                                    rotas_df,
                                    coords_to_merge,
                                    on='Pedido_Index_DF',
                                    how='left' # Mantém todas as rotas, mesmo se o merge falhar para alguma
                                )
                                st.info("Coordenadas adicionadas ao DataFrame de rotas.")
                            except Exception as merge_err:
                                st.warning(f"Não foi possível adicionar coordenadas ao DataFrame de rotas: {merge_err}")
                        else:
                             st.warning("Não foi possível adicionar coordenadas ao DataFrame de rotas (coluna 'Pedido_Index_DF' ou 'pedidos_validos' ausente/vazio).")


                        with st.expander("Visualizar Tabela de Rotas Geradas (com Coordenadas)", expanded=True):
                            st.dataframe(rotas_df, use_container_width=True)

                        # --- Calcular Distância Total Real ---
                        distancia_total_real = 0
                        # Usa matriz_distancias que foi calculada para todos os casos (se ok)
                        if matriz_distancias is not None and 'Veículo' in rotas_df.columns and 'Node_Index_OR' in rotas_df.columns:
                            try:
                                for veiculo, rota_veiculo in rotas_df.groupby('Veículo'):
                                    # Ordenar pela sequência, se existir, senão pela ordem que veio
                                    if 'Sequencia' in rota_veiculo.columns:
                                        rota_veiculo = rota_veiculo.sort_values('Sequencia')

                                    node_indices = [depot_index] + rota_veiculo['Node_Index_OR'].tolist() + [depot_index]
                                    distancia_rota = 0
                                    for i in range(len(node_indices) - 1):
                                        idx_from = node_indices[i]
                                        idx_to = node_indices[i+1]
                                        # Verifica limites da matriz
                                        if 0 <= idx_from < len(matriz_distancias) and 0 <= idx_to < len(matriz_distancias[idx_from]):
                                            distancia_rota += matriz_distancias[idx_from][idx_to]
                                        else:
                                            st.warning(f"Índice fora dos limites da matriz de distâncias ao calcular distância real: {idx_from} -> {idx_to}")
                                    distancia_total_real += distancia_rota
                                st.info(f"Distância total real calculada: {distancia_total_real:,.0f} metros.")
                            except Exception as calc_dist_e:
                                st.warning(f"Não foi possível calcular a distância total real a partir das rotas: {calc_dist_e}")
                                distancia_total_real = None # Falha no cálculo
                        elif 'distancia' in rotas_df.columns: # Fallback se o solver já calculou (menos provável para VRPTW)
                             distancia_total_real = rotas_df['distancia'].sum()
                             st.info(f"Usando distância pré-calculada pelo solver: {distancia_total_real:,.0f} metros.")
                        else:
                             st.warning("Matriz de distâncias ou colunas necessárias não disponíveis para calcular a distância total real.")
                             distancia_total_real = None # Não foi possível calcular

                        # Salvar cenário no histórico (agora rotas_df tem Lat/Lon se o merge funcionou)
                        cenario = {
                            'data': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'tipo': tipo,
                            'rotas': rotas_df, # Dataframe completo das rotas com coordenadas
                            'qtd_pedidos_roteirizados': len(pedidos_validos),
                            'qtd_veiculos_disponiveis': len(frota),
                            'distancia_total': distancia_total_real,
                            'custo_solver': resultado_solver.get('total_distance') if tipo == "VRPTW" and resultado_solver else None,
                            'tempo_solver': resultado_solver.get('total_time') if tipo == "VRPTW" and resultado_solver else None,
                            'status_solver': status_solver,
                            'endereco_partida': endereco_partida,
                            'lat_partida': lat_partida,
                            'lon_partida': lon_partida,
                            'pedidos_nao_alocados': pedidos_nao_alocados
                        }
                        st.session_state.cenarios_roteirizacao.insert(0, cenario) # Adiciona no início
                    # ... (restante do código) ...
                    else: # Fim do if matriz_ok
                     st.error("Não foi possível calcular as matrizes necessárias (distâncias e/ou tempos). Verifique os erros acima.")


        # Exibe aviso sobre pedidos não alocados (fora do botão de cálculo, mostra sempre se houver)
        if not pedidos_nao_alocados.empty:
            st.warning(f"Atenção: {len(pedidos_nao_alocados)} pedidos não possuem coordenadas válidas e não foram incluídos na roteirização.")
            with st.expander("Ver Pedidos Não Roteirizados"):
                 st.dataframe(pedidos_nao_alocados, use_container_width=True)

        st.divider() # <<<< ESTE É O DIVIDER QUE ESTAVA CAUSANDO O ERRO >>>>

        # --- Histórico de Cenários ---
        if st.session_state.cenarios_roteirizacao:
            st.subheader("Histórico de Cenários Calculados")
            # Cria DataFrame para exibição resumida
            df_cenarios_display = pd.DataFrame([
                {
                    'Data': c.get('data', ''),
                    'Tipo': c.get('tipo', ''),
                    'Pedidos Roteirizados': c.get('qtd_pedidos_roteirizados', ''),
                    'Veículos Disponíveis': c.get('qtd_veiculos_disponiveis', ''),
                    'Distância Total (m)': f"{c.get('distancia_total', 0):,.0f}" if c.get('distancia_total') is not None else "N/A",
                    'Status Solver': c.get('status_solver', 'N/A'),
                    'Endereço Partida': c.get('endereco_partida', '')
                }
                for c in st.session_state.cenarios_roteirizacao
            ])
            st.dataframe(df_cenarios_display, use_container_width=True)

            # Seleção para visualização detalhada
            cenario_indices = range(len(st.session_state.cenarios_roteirizacao))
            selected_idx = st.selectbox(
                "Visualizar detalhes e mapa do cenário:",
                options=cenario_indices,
                format_func=lambda i: f"{df_cenarios_display.iloc[i]['Data']} - {df_cenarios_display.iloc[i]['Tipo']} ({df_cenarios_display.iloc[i]['Pedidos Roteirizados']} pedidos)",
                index=None, # Nenhum selecionado por padrão
                key="select_cenario_historico"
            )

            if selected_idx is not None:
                cenario_selecionado = st.session_state.cenarios_roteirizacao[selected_idx]
                st.markdown(f"#### Detalhes do Cenário: {cenario_selecionado['data']} ({cenario_selecionado['tipo']})")

                # Mostrar tabela de rotas do cenário selecionado
                st.write("**Rotas Geradas:**")
                st.dataframe(cenario_selecionado.get('rotas', pd.DataFrame()), use_container_width=True)
                # Adicionar aqui a lógica para exibir o mapa se necessário

    # <<<< FIM CORRETO DO BLOCO TRY >>>>

    except FileNotFoundError as e:
         st.error(f"Erro: Arquivo não encontrado. Verifique se os arquivos de dados ({e.filename}) estão na pasta correta.")
    except ImportError as e:
         st.error(f"Erro de importação: {e}. Verifique se todas as dependências estão instaladas corretamente (`pip install -r requirements.txt`).")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado na página de roteirização: {e}")
        st.exception(e) # Mostra o traceback completo para depuração

# Comentar execução direta se a navegação for centralizada
# if __name__ == "__main__":
#     show()