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
from routing.cvrp import solver_cvrp
from routing.cvrp_flex import solver_cvrp_flex
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
                  # Filtra disponíveis
                  frota = frota[frota['Disponível'] == True]
             else:
                 st.warning("Coluna 'Disponível' não encontrada na frota. Considerando todos os veículos.")
             # Garante colunas essenciais e tipos corretos
             if 'Capacidade (Kg)' not in frota.columns:
                 frota['Capacidade (Kg)'] = 0
             else:
                 frota['Capacidade (Kg)'] = pd.to_numeric(frota['Capacidade (Kg)'], errors='coerce').fillna(0)
             if 'Janela Início' not in frota.columns:
                 frota['Janela Início'] = '00:00'
             if 'Janela Fim' not in frota.columns:
                 frota['Janela Fim'] = '23:59'
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
            # Garante colunas essenciais e tipos corretos
            if 'Janela de Descarga' not in pedidos.columns:
                pedidos['Janela de Descarga'] = 30
            if 'Latitude' not in pedidos.columns:
                pedidos['Latitude'] = None
            if 'Longitude' not in pedidos.columns:
                pedidos['Longitude'] = None
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
            ["CVRP", "CVRP Flex"],
            key="tipo_roteirizacao_select",
            help="Escolha o algoritmo de roteirização baseado nas restrições do seu problema."
        )
        explicacoes = {
            "CVRP": "CVRP (Capacitated VRP): Considera a capacidade máxima (Kg ou Cx) dos veículos.",
            "CVRP Flex": "CVRP Flex: Permite ajustar a capacidade dos veículos de 0% a 120% para simular sobrecarga controlada."
        }
        st.info(explicacoes.get(tipo, ""))

        ajuste_capacidade_pct = 100
        if tipo in ["CVRP", "CVRP Flex"]:
            ajuste_capacidade_pct = st.slider(
                "Ajuste de Capacidade dos Veículos (%)",
                min_value=80, max_value=120, value=100, step=1,
                help="Permite simular veículos carregando menos ou até 20% a mais que a capacidade cadastrada."
            )

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
            elif frota.empty:
                 st.error(f"Erro: A frota está vazia, não é possível calcular rotas para {tipo}.")
            else:
                # --- Validações adicionais antes de calcular matrizes ---
                if tipo == "CVRP":
                    # 1. Demanda maior que qualquer veículo
                    if 'Peso dos Itens' in pedidos_validos.columns and 'Capacidade (Kg)' in frota.columns:
                        demandas_pedidos = pedidos_validos['Peso dos Itens'].fillna(0).astype(float)
                        capacidades_veic = frota['Capacidade (Kg)'].fillna(0).astype(float)
                        max_capacidade = capacidades_veic.max() if not capacidades_veic.empty else 0
                        pedidos_excedentes = pedidos_validos[demandas_pedidos > max_capacidade]
                        if not pedidos_excedentes.empty:
                            st.error(f"Existem pedidos cuja demanda excede a capacidade máxima dos veículos ({max_capacidade:.1f} Kg). Corrija antes de prosseguir.")
                            st.dataframe(pedidos_excedentes, use_container_width=True)
                            return
                # Preparar dados comuns para todos os solvers
                depot_coord = (lat_partida, lon_partida)
                customer_coords = pedidos_validos[['Latitude', 'Longitude']].values.tolist()
                all_locations = [depot_coord] + customer_coords
                # pedidos_nao_alocados já foi definido acima
                depot_index = 0 # Índice do depósito na lista all_locations

                matriz_distancias = None

                # Calcular Matriz de Distâncias (necessária para VRP, CVRP, TSP e cálculo final de distância)
                with st.spinner("Calculando matriz de distâncias..."):
                    try:
                        matriz_distancias = calcular_matriz_distancias(all_locations, metrica='distance')
                        if matriz_distancias is None or len(matriz_distancias) != len(all_locations):
                             st.error("Falha ao calcular a matriz de distâncias completa.")
                             matriz_distancias = None # Garante que não prossiga se falhar
                        elif np.any(np.array(matriz_distancias) >= 1e7):
                             st.error("A matriz de distâncias contém valores infinitos ou impossíveis. Verifique as coordenadas dos pedidos e do depósito.")
                             return
                        else:
                             st.success(f"Matriz de distâncias ({matriz_distancias.shape}) calculada.")
                    except Exception as e:
                        st.error(f"Erro no cálculo da matriz de distâncias: {e}")
                        matriz_distancias = None

                # Prosseguir apenas se as matrizes necessárias estiverem prontas
                matriz_ok = (matriz_distancias is not None)

                if matriz_ok:
                    rotas = None
                    rotas_df = pd.DataFrame() # Inicializa dataframe vazio
                    resultado_solver = None # Para armazenar o dict do VRPTW ou o DataFrame dos outros
                    status_solver = "Não executado"

                    with st.spinner(f"Executando o solver {tipo}..."):
                        try:
                            if tipo == "CVRP":
                                # CVRP também minimiza distância, mas considera capacidade
                                if 'Peso dos Itens' not in pedidos_validos.columns:
                                    st.error("Coluna 'Peso dos Itens' necessária para CVRP não encontrada nos pedidos.")
                                    raise ValueError("Faltando 'Peso dos Itens'")
                                elif 'Capacidade (Kg)' not in frota.columns:
                                     st.error("Coluna 'Capacidade (Kg)' necessária para CVRP não encontrada na frota.")
                                     raise ValueError("Faltando 'Capacidade (Kg)'")
                                else:
                                     # Passa a matriz de distâncias - CORRIGIDO: Removidos argumentos extras
                                     rotas = solver_cvrp(pedidos_validos, frota, matriz_distancias)
                                     rotas_df = rotas # Resultado já é DataFrame
                                     status_solver = "OK" if rotas_df is not None and not rotas_df.empty else "Falha ou Sem Solução"
                            elif tipo == "CVRP Flex":
                                rotas = solver_cvrp_flex(pedidos_validos, frota, matriz_distancias, depot_index=depot_index, ajuste_capacidade_pct=ajuste_capacidade_pct)
                                # Se o solver retornar dict, tenta extrair o DataFrame
                                if isinstance(rotas, dict):
                                    # Tenta extrair a chave 'rotas' ou 'routes' ou converter o maior DataFrame do dict
                                    if 'rotas' in rotas:
                                        rotas_df = rotas['rotas']
                                    elif 'routes' in rotas:
                                        rotas_df = rotas['routes']
                                    else:
                                        # Procura o maior DataFrame no dict
                                        dfs = [v for v in rotas.values() if isinstance(v, pd.DataFrame)]
                                        rotas_df = dfs[0] if dfs else pd.DataFrame()
                                else:
                                    rotas_df = rotas
                                status_solver = "OK" if rotas_df is not None and isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty else "Falha ou Sem Solução"

                        except ValueError as ve:
                             st.error(f"Erro de dados ao preparar para {tipo}: {ve}")
                             status_solver = f"Erro de Dados: {ve}"
                             rotas_df = None
                             st.session_state['rotas_calculadas'] = None
                             st.session_state['mapa_necessario'] = False
                        except Exception as solver_error:
                             st.error(f"Erro durante a execução do solver {tipo}: {solver_error}")
                             st.exception(solver_error)
                             status_solver = f"Erro Solver: {solver_error}"
                             rotas_df = None
                             st.session_state['rotas_calculadas'] = None
                             st.session_state['mapa_necessario'] = False

                        # Relatório automático de causas para inviabilidade
                        if status_solver and ("INFEASIBLE" in str(status_solver).upper() or "NENHUMA SOLUÇÃO" in str(status_solver).upper() or "Falha" in str(status_solver)):
                            st.warning("\n**Diagnóstico automático para problema inviável:**\n\n- Verifique se algum pedido tem demanda maior que a capacidade máxima dos veículos.\n- Revise as janelas de tempo dos veículos e pedidos (se existirem).\n- Confira se todos os pedidos possuem coordenadas válidas e não há outliers muito distantes.\n- Certifique-se de que a frota é suficiente para atender todos os pedidos.\n- Tente relaxar restrições (aumentar janelas, frota, capacidade) e rode novamente.\n\nSe o problema persistir, revise os dados de entrada e tente com um conjunto menor de pedidos.")

                    if rotas_df is not None:
                        if not rotas_df.empty:
                            if 'Pedido_Index_DF' in rotas_df.columns and not pedidos_validos.empty:
                                try:
                                    coords_to_merge = pedidos_validos.reset_index(drop=True).reset_index()[['index', 'Latitude', 'Longitude']].copy()
                                    coords_to_merge = coords_to_merge.rename(columns={'index': 'Pedido_Index_DF'})
                                    rotas_df = pd.merge(
                                        rotas_df,
                                        coords_to_merge,
                                        on='Pedido_Index_DF',
                                        how='left',
                                        suffixes=(None, '_pedido')
                                    )
                                    st.info("Coordenadas adicionadas ao DataFrame de rotas.")
                                except Exception as merge_err:
                                    st.warning(f"Não foi possível adicionar coordenadas ao DataFrame de rotas: {merge_err}")
                            else:
                                 st.warning("Não foi possível adicionar coordenadas ao DataFrame de rotas (coluna 'Pedido_Index_DF' ou 'pedidos_validos' ausente/vazio).")

                            with st.expander("Visualizar Tabela de Rotas Geradas (com Coordenadas)", expanded=True):
                                st.dataframe(rotas_df, use_container_width=True)

                            # <<< ADICIONAR CÓDIGO PARA SALVAR O CSV AQUI >>>
                            try:
                                csv_path = "/workspaces/WazeLog/data/Roteirizacao.csv"
                                rotas_df.to_csv(csv_path, index=False, encoding='utf-8')
                                st.success(f"Rotas salvas com sucesso em {csv_path}")
                            except Exception as save_err:
                                st.error(f"Erro ao salvar o arquivo CSV: {save_err}")
                            # <<< FIM DO CÓDIGO ADICIONADO >>>

                            # <<< DEBUGGING >>>
                            st.write("--- Debug Info para Cálculo de Distância ---")
                            st.write(f"Tipo de matriz_distancias: {type(matriz_distancias)}")
                            if isinstance(matriz_distancias, (list, np.ndarray)):
                                try:
                                    st.write(f"Shape/Len de matriz_distancias: {np.array(matriz_distancias).shape}")
                                except Exception as e:
                                    st.write(f"Erro ao obter shape da matriz: {e}")
                            else:
                                st.write("matriz_distancias não é lista ou array numpy.")
                            st.write(f"Tipo de rotas_df: {type(rotas_df)}")
                            if isinstance(rotas_df, pd.DataFrame):
                                st.write(f"rotas_df está vazio: {rotas_df.empty}")
                                st.write(f"Colunas em rotas_df: {rotas_df.columns.tolist()}")
                                st.write(f"\'Veículo\' nas colunas: {'Veículo' in rotas_df.columns}")
                                st.write(f"\'Node_Index_OR\' nas colunas: {'Node_Index_OR' in rotas_df.columns}")
                            else:
                                st.write("rotas_df não é um DataFrame.")
                            st.write("--- Fim Debug Info ---")
                            # <<< END DEBUGGING >>>

                            distancia_total_real_m = 0
                            # Adicionado isinstance(rotas_df, pd.DataFrame) e not rotas_df.empty para segurança
                            if matriz_distancias is not None and isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty and 'Veículo' in rotas_df.columns and 'Node_Index_OR' in rotas_df.columns:
                                try:
                                    for veiculo, rota_veiculo in rotas_df.groupby('Veículo'):
                                        rota_veiculo = rota_veiculo.sort_values('Sequencia')
                                        node_indices = [depot_index] + rota_veiculo['Node_Index_OR'].tolist() + [depot_index]
                                        distancia_rota = 0
                                        for i in range(len(node_indices) - 1):
                                            idx_from = node_indices[i]
                                            idx_to = node_indices[i+1]
                                            if 0 <= idx_from < len(matriz_distancias) and 0 <= idx_to < len(matriz_distancias[idx_from]):
                                                distancia_rota += matriz_distancias[idx_from][idx_to]
                                            else:
                                                st.warning(f"Índice fora dos limites da matriz de distâncias ao calcular distância real: {idx_from} -> {idx_to}")
                                        distancia_total_real_m += distancia_rota
                                    st.metric("Distância Total Real (Calculada)", f"{distancia_total_real_m / 1000:,.1f} km")
                                except Exception as calc_dist_e:
                                    st.warning(f"Não foi possível calcular a distância total real a partir das rotas: {calc_dist_e}")
                                    distancia_total_real_m = None
                            else:
                                 # Mensagem de aviso movida para cá e ajustada
                                 if isinstance(rotas_df, pd.DataFrame) and rotas_df.empty:
                                     st.info("Nenhuma rota foi gerada pelo solver, portanto a distância total não pode ser calculada.")
                                 else:
                                     st.warning("Matriz de distâncias ou colunas necessárias não disponíveis para calcular a distância total real.")
                                 distancia_total_real_m = None # Garante que seja None se não calculado

                            # --- Calcular e Exibir Resumo por Veículo ---
                            peso_total_empenhado_kg = 0
                            if isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty and 'Veículo' in rotas_df.columns and 'Demanda' in rotas_df.columns:
                                resumo_veiculos = rotas_df.groupby('Veículo')['Demanda'].sum().reset_index()
                                resumo_veiculos = resumo_veiculos.rename(columns={'Demanda': 'Peso Empenhado (Kg)'})
                                peso_total_empenhado_kg = resumo_veiculos['Peso Empenhado (Kg)'].sum()

                                # Tentar merge com frota para obter capacidade
                                try:
                                    # Identificar a coluna de ID correta na frota (prioriza 'ID Veículo')
                                    id_col_frota = 'ID Veículo' if 'ID Veículo' in frota.columns else 'Placa'
                                    if id_col_frota in frota.columns and 'Capacidade (Kg)' in frota.columns:
                                        frota_capacidade = frota[[id_col_frota, 'Capacidade (Kg)']].copy()
                                        # Renomear a coluna de ID da frota para corresponder à coluna 'Veículo' do resumo
                                        frota_capacidade = frota_capacidade.rename(columns={id_col_frota: 'Veículo'})
                                        resumo_veiculos = pd.merge(resumo_veiculos, frota_capacidade, on='Veículo', how='left')
                                        # Calcular % de Ocupação
                                        resumo_veiculos['Ocupação (%)'] = (
                                            (resumo_veiculos['Peso Empenhado (Kg)'] / resumo_veiculos['Capacidade (Kg)'] * 100)
                                            .fillna(0)
                                            .round(1)
                                        )
                                    else:
                                        st.warning("Não foi possível encontrar 'ID Veículo'/'Placa' ou 'Capacidade (Kg)' na frota para adicionar ao resumo.")
                                        resumo_veiculos['Capacidade (Kg)'] = None
                                        resumo_veiculos['Ocupação (%)'] = None

                                    with st.expander("Resumo de Carga por Veículo", expanded=False):
                                        st.dataframe(resumo_veiculos, use_container_width=True, hide_index=True)
                                except Exception as resumo_err:
                                    st.warning(f"Erro ao gerar resumo por veículo: {resumo_err}")
                            # --- Fim Resumo por Veículo ---

                            cenario = {
                                'data': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'tipo': tipo,
                                'rotas': rotas_df,
                                'qtd_pedidos_roteirizados': len(pedidos_validos),
                                'qtd_veiculos_utilizados': rotas_df['Veículo'].nunique() if isinstance(rotas_df, pd.DataFrame) and not rotas_df.empty else 0,
                                'qtd_veiculos_disponiveis': len(frota),
                                'peso_total_empenhado_kg': peso_total_empenhado_kg, # Adicionado
                                'distancia_total_real_m': distancia_total_real_m,
                                'custo_solver_sec': None, # Placeholder
                                'tempo_operacao_sec': None, # Placeholder
                                'status_solver': status_solver,
                                'endereco_partida': endereco_partida,
                                'lat_partida': lat_partida,
                                'lon_partida': lon_partida,
                                'pedidos_nao_alocados': pedidos_nao_alocados
                            }
                            st.session_state.cenarios_roteirizacao.insert(0, cenario)
                        else:
                            st.info(f"Nenhuma rota gerada para {tipo}. Status: {status_solver}")

                            # Diagnóstico detalhado para solver sem solução
                            st.warning("""
**Diagnóstico detalhado: Nenhuma rota foi gerada. Possíveis causas:**

- **Pedidos com demanda maior que a capacidade máxima dos veículos:**
    - Verifique se algum pedido tem 'Peso dos Itens' maior que a maior 'Capacidade (Kg)' da frota.
- **Frota vazia ou sem veículos disponíveis:**
    - Confirme se há veículos cadastrados e disponíveis, e se todos têm capacidade maior que zero.
- **Pedidos sem coordenadas válidas:**
    - Todos os pedidos devem ter 'Latitude' e 'Longitude' válidas.
- **Dados inconsistentes ou restrições muito rígidas:**
    - Janelas de tempo, capacidades ou outros parâmetros podem estar impossibilitando a solução.
- **Todos os pedidos já estão alocados ou não há pedidos válidos:**
    - Verifique se há pedidos realmente roteirizáveis.

Se necessário, revise os dados de entrada, relaxe restrições ou tente com um conjunto menor de pedidos.
""")

                    else:
                         st.error(f"Não foi possível executar a roteirização ({tipo}) devido a erros anteriores. Status: {status_solver}")

                else:
                     st.error("Não foi possível calcular as matrizes necessárias (distâncias e/ou tempos). Verifique os erros acima.")

        if not pedidos_nao_alocados.empty:
            st.warning(f"Atenção: {len(pedidos_nao_alocados)} pedidos não possuem coordenadas válidas e não foram incluídos na roteirização.")
            with st.expander("Ver Pedidos Não Roteirizados"):
                 st.dataframe(pedidos_nao_alocados, use_container_width=True)

        st.divider()

        if st.session_state.cenarios_roteirizacao:
            st.subheader("Histórico de Cenários Calculados")
            df_cenarios_display = pd.DataFrame([
                {
                    'Data': c.get('data', ''),
                    'Tipo': c.get('tipo', ''),
                    'Pedidos': c.get('qtd_pedidos_roteirizados', ''),
                    'Veículos': c.get('qtd_veiculos_disponiveis', ''),
                    'Distância Real': f"{c.get('distancia_total_real_m', 0) / 1000:,.1f} km" if c.get('distancia_total_real_m') is not None else "N/A",
                    'Custo Solver (s)': f"{c.get('custo_solver_sec', 0):,.0f}" if c.get('custo_solver_sec') is not None else "N/A",
                    'Tempo Operação (s)': f"{c.get('tempo_operacao_sec', 0):,.0f}" if c.get('tempo_operacao_sec') is not None else "N/A",
                    'Status': c.get('status_solver', 'N/A'),
                }
                for c in st.session_state.cenarios_roteirizacao
            ])
            st.dataframe(df_cenarios_display, use_container_width=True, hide_index=True)

            cenario_indices = range(len(st.session_state.cenarios_roteirizacao))
            selected_idx = st.selectbox(
                "Visualizar detalhes e mapa do cenário:",
                options=cenario_indices,
                format_func=lambda i: f"{df_cenarios_display.iloc[i]['Data']} - {df_cenarios_display.iloc[i]['Tipo']} ({df_cenarios_display.iloc[i]['Pedidos']} pedidos)",
                index=None,
                key="select_cenario_historico"
            )

            if selected_idx is not None:
                cenario_selecionado = st.session_state.cenarios_roteirizacao[selected_idx]
                st.markdown(f"#### Detalhes do Cenário: {cenario_selecionado['data']} ({cenario_selecionado['tipo']})")

                st.write("**Rotas Geradas:**")
                df_rotas_cenario = cenario_selecionado.get('rotas', pd.DataFrame())
                st.dataframe(df_rotas_cenario, use_container_width=True)

                df_nao_alocados_cenario = cenario_selecionado.get('pedidos_nao_alocados', pd.DataFrame())
                if not df_nao_alocados_cenario.empty:
                    st.write("**Pedidos Não Roteirizados neste Cenário:**")
                    st.dataframe(df_nao_alocados_cenario, use_container_width=True)

                if not df_rotas_cenario.empty:
                    st.write("**Mapa da Rota:**")
                    if 'Latitude' in df_rotas_cenario.columns and 'Longitude' in df_rotas_cenario.columns:
                        df_map = df_rotas_cenario.dropna(subset=["Latitude", "Longitude"]).rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
                        st.map(df_map)
                    else:
                        st.info("Não há coordenadas válidas para exibir o mapa da rota.")

        # Diagnóstico automático de inviabilidade
        if tipo == "CVRP" and not pedidos_validos.empty and not frota.empty:
            # 1. Pedidos com demanda maior que a capacidade máxima
            if 'Peso dos Itens' in pedidos_validos.columns and 'Capacidade (Kg)' in frota.columns:
                demandas_pedidos = pedidos_validos['Peso dos Itens'].fillna(0).astype(float)
                max_capacidade = frota['Capacidade (Kg)'].max()
                pedidos_excedentes = pedidos_validos[demandas_pedidos > max_capacidade]
                if not pedidos_excedentes.empty:
                    st.warning(f"Pedidos com demanda maior que a capacidade máxima dos veículos ({max_capacidade:.1f} Kg):")
                    st.dataframe(pedidos_excedentes, use_container_width=True)
            # 2. Veículos com capacidade zero ou nula
            if 'Capacidade (Kg)' in frota.columns:
                veiculos_sem_capacidade = frota[frota['Capacidade (Kg)'] <= 0]
                if not veiculos_sem_capacidade.empty:
                    st.warning("Veículos com capacidade zero ou nula:")
                    st.dataframe(veiculos_sem_capacidade, use_container_width=True)
            # 3. Pedidos sem coordenadas
            pedidos_sem_coord = pedidos_validos[pedidos_validos['Latitude'].isna() | pedidos_validos['Longitude'].isna()]
            if not pedidos_sem_coord.empty:
                st.warning("Pedidos sem coordenadas válidas:")
                st.dataframe(pedidos_sem_coord, use_container_width=True)

    except FileNotFoundError as e:
         st.error(f"Erro: Arquivo não encontrado. Verifique se os arquivos de dados ({e.filename}) estão na pasta correta.")
    except ImportError as e:
         st.error(f"Erro de importação: {e}. Verifique se todas as dependências estão instaladas corretamente (`pip install -r requirements.txt`).")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado na página de roteirização: {e}")
        st.exception(e)