import streamlit as st
import pandas as pd
# Importações adicionadas para funcionalidade completa
from database import (
    carregar_pedidos,
    carregar_frota,
    salvar_endereco_partida,
    carregar_endereco_partida
)
from routing.ortools_solver import solver_vrp, solver_cvrp, solver_vrptw, solver_tsp
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

    try:
        # Carrega os dataframes usando as funções do database
        pedidos = carregar_pedidos()
        frota = carregar_frota()

        # Processamento da Frota
        if frota is not None and not frota.empty:
             frota = frota.loc[:, ~frota.columns.duplicated()] # Remove colunas duplicadas
             if 'Disponível' in frota.columns:
                 frota = frota[frota['Disponível'] == True].reset_index(drop=True) # Filtra disponíveis
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
        else:
            st.warning("Não foi possível carregar dados dos pedidos ou não há pedidos.")
            pedidos = pd.DataFrame() # Dataframe vazio
            pedidos_sorted = pd.DataFrame()

        # Exibição lado a lado dos dados carregados
        st.subheader("Dados Carregados")
        col1_data, col2_data = st.columns(2)
        with col1_data:
            st.caption(f"Pedidos ({len(pedidos_sorted)})")
            st.dataframe(pedidos_sorted, height=200) # Ajuste de altura
        with col2_data:
            st.caption(f"Frota Disponível ({len(frota)})")
            st.dataframe(frota, height=200) # Ajuste de altura

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
                    f"{lat_partida_salva:.6f}" if lat_partida_salva else str(DEFAULT_LAT_PARTIDA),
                    key="lat_partida_input"
                )
            with col2_addr:
                lon_partida_manual = st.text_input(
                    "Longitude",
                    f"{lon_partida_salva:.6f}" if lon_partida_salva else str(DEFAULT_LON_PARTIDA),
                    key="lon_partida_input"
                )

            usar_coord_manual = st.checkbox("Usar coordenadas manuais", value=False, key="usar_coord_manual_cb")

            if endereco_partida:
                if usar_coord_manual:
                    try:
                        lat_partida = float(lat_partida_manual)
                        lon_partida = float(lon_partida_manual)
                        st.info(f"Usando coordenadas manuais: {lat_partida}, {lon_partida}")
                    except (ValueError, TypeError):
                        st.error("Latitude e Longitude manuais devem ser números válidos.")
                        lat_partida, lon_partida = None, None # Invalida para impedir cálculo
                else:
                    # Verifica se o endereço mudou ou se não há coordenadas salvas para ele
                    if endereco_partida != endereco_partida_salvo or lat_partida_salva is None or lon_partida_salva is None:
                        with st.spinner(f"Buscando coordenadas para {endereco_partida}..."):
                            lat_partida, lon_partida = obter_coordenadas(endereco_partida)
                        if lat_partida is not None and lon_partida is not None:
                            salvar_endereco_partida(endereco_partida, lat_partida, lon_partida)
                            st.success(f"Coordenadas encontradas e salvas: {lat_partida:.6f}, {lon_partida:.6f}")
                        else:
                            st.error("Não foi possível obter coordenadas para o endereço. Verifique o endereço ou insira manualmente.")
                            # Mantém as coordenadas salvas/padrão se a busca falhar? Ou invalida? Vamos invalidar.
                            lat_partida, lon_partida = None, None
                    else:
                        # Usa as coordenadas salvas
                        lat_partida = lat_partida_salva
                        lon_partida = lon_partida_salva
                        st.info(f"Usando coordenadas salvas: {lat_partida:.6f}, {lon_partida:.6f}")

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
            pedidos_validos = pedidos.dropna(subset=['Latitude', 'Longitude']) if pedidos is not None else pd.DataFrame()
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
                # Preparar dados para o solver
                depot_coord = (lat_partida, lon_partida)
                customer_coords = pedidos_validos[['Latitude', 'Longitude']].values.tolist()
                all_locations = [depot_coord] + customer_coords
                pedidos_nao_alocados = pedidos[pedidos['Latitude'].isna() | pedidos['Longitude'].isna()] if pedidos is not None else pd.DataFrame()

                matriz = None
                with st.spinner("Calculando matriz de distâncias..."):
                    try:
                        matriz = calcular_matriz_distancias(all_locations)
                        if matriz is None or len(matriz) != len(all_locations):
                             st.error("Falha ao calcular a matriz de distâncias completa.")
                             matriz = None # Garante que não prossiga
                        else:
                             st.success(f"Matriz de distâncias ({matriz.shape}) calculada.")
                    except Exception as e:
                        st.error(f"Erro no cálculo da matriz de distâncias: {e}")
                        matriz = None

                if matriz is not None:
                    rotas = None
                    with st.spinner(f"Executando o solver {tipo}..."):
                        try:
                            # Chama o solver apropriado
                            if tipo == "VRP":
                                rotas = solver_vrp(pedidos_validos, frota, matriz, depot_index=0)
                            elif tipo == "CVRP":
                                if 'Peso dos Itens' not in pedidos_validos.columns:
                                    st.error("Coluna 'Peso dos Itens' necessária para CVRP não encontrada nos pedidos.")
                                elif 'Capacidade (Kg)' not in frota.columns: # Ou Capacidade (Cx) dependendo da lógica do solver
                                     st.error("Coluna 'Capacidade (Kg)' necessária para CVRP não encontrada na frota.")
                                else:
                                     rotas = solver_cvrp(pedidos_validos, frota, matriz, depot_index=0)
                            elif tipo == "VRPTW":
                                # Implementar coleta de janelas de tempo e tempos de descarga (como no código original)
                                st.info("VRPTW: Verifique se as colunas de Janelas de Tempo e Tempo de Descarga estão presentes e corretas.")
                                rotas = solver_vrptw(pedidos_validos, frota, matriz)  # Removido depot_index
                            elif tipo == "TSP":
                                # O solver TSP pode precisar apenas da matriz ou de mais dados
                                rotas = solver_tsp(matriz) # Ajustar chamada conforme a implementação do solver_tsp

                        except Exception as solver_error:
                             st.error(f"Erro durante a execução do solver {tipo}: {solver_error}")

                    # Processamento dos resultados
                    if rotas is not None and not rotas.empty:
                        st.success(f"Rotas calculadas com sucesso usando {tipo}!")
                        with st.expander("Visualizar Tabela de Rotas Geradas", expanded=True):
                            st.dataframe(rotas, use_container_width=True)

                        # Salvar cenário no histórico
                        dist_total = rotas['distancia'].sum() if 'distancia' in rotas.columns else None
                        cenario = {
                            'data': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'tipo': tipo,
                            'rotas': rotas, # Dataframe completo das rotas
                            'qtd_pedidos_roteirizados': len(pedidos_validos),
                            'qtd_veiculos_disponiveis': len(frota),
                            'distancia_total': dist_total,
                            'endereco_partida': endereco_partida,
                            'lat_partida': lat_partida,
                            'lon_partida': lon_partida,
                            'pedidos_nao_alocados': pedidos_nao_alocados # Dataframe dos não alocados
                        }
                        st.session_state.cenarios_roteirizacao.insert(0, cenario) # Adiciona no início
                    else:
                        st.error(f"Não foi possível gerar rotas válidas com o solver {tipo}. Verifique os dados de entrada e as configurações.")

            # Exibe aviso sobre pedidos não alocados (após tentativa de cálculo)
            if not pedidos_nao_alocados.empty:
                st.warning(f"Atenção: {len(pedidos_nao_alocados)} pedidos não possuem coordenadas válidas e não foram incluídos na roteirização.")
                with st.expander("Ver Pedidos Não Roteirizados"):
                     st.dataframe(pedidos_nao_alocados, use_container_width=True)

        st.divider()

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
                st.dataframe(cenario_selecionado['rotas'], use_container_width=True)

                # Mostrar não alocados do cenário selecionado
                pedidos_nao_alocados = cenario_selecionado.get('pedidos_nao_alocados', pd.DataFrame())
                if isinstance(pedidos_nao_alocados, pd.DataFrame) and not pedidos_nao_alocados.empty:
                     st.write("**Pedidos Não Roteirizados (sem coordenadas):**")
                     st.dataframe(pedidos_nao_alocados, use_container_width=True)

                # Botão para visualizar mapa do cenário selecionado
                if st.button(f"Visualizar Mapa do Cenário {cenario_selecionado['data']}", key=f"map_btn_{selected_idx}", use_container_width=True):
                    rotas_sel = cenario_selecionado['rotas']
                    # Assumindo que 'rotas' contém Latitude/Longitude ou lat/lon
                    lat_col = 'lat' if 'lat' in rotas_sel.columns else 'Latitude'
                    lon_col = 'lon' if 'lon' in rotas_sel.columns else 'Longitude'

                    if lat_col in rotas_sel.columns and lon_col in rotas_sel.columns:
                        map_data = rotas_sel[[lat_col, lon_col]].copy()
                        map_data.rename(columns={lat_col: 'lat', lon_col: 'lon'}, inplace=True)
                        map_data = map_data.dropna(subset=['lat', 'lon'])

                        # Adicionar o ponto de partida ao mapa
                        depot_df = pd.DataFrame([{
                            'lat': cenario_selecionado['lat_partida'],
                            'lon': cenario_selecionado['lon_partida']
                            # Adicionar coluna de cor/tamanho se quiser diferenciar
                        }])
                        map_data = pd.concat([depot_df, map_data], ignore_index=True)


                        if not map_data.empty:
                             st.map(map_data)
                        else:
                             st.warning("Não há coordenadas válidas nas rotas para exibir no mapa.")
                    else:
                        st.warning(f"As rotas geradas não contêm colunas '{lat_col}' e '{lon_col}' necessárias para o mapa.")

    except FileNotFoundError as e:
         st.error(f"Erro crítico: Arquivo de dados não encontrado. Verifique se 'pedidos.csv' e 'frota.csv' existem em /data. Detalhes: {e}")
    except ImportError as e:
         st.error(f"Erro crítico: Falha ao importar módulos necessários. Verifique as dependências. Detalhes: {e}")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado na página de roteirização: {e}")
        st.exception(e) # Mostra traceback para depuração

# Comentar execução direta se a navegação for centralizada
# if __name__ == "__main__":
#     show()
