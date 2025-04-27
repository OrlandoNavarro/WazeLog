import streamlit as st
import pandas as pd
from database import carregar_pedidos, carregar_frota, salvar_endereco_partida, carregar_endereco_partida
from routing.ortools_solver import solver_vrp, solver_cvrp, solver_vrptw, solver_tsp
from routing.distancias import calcular_matriz_distancias
from pedidos import obter_coordenadas

DEFAULT_ENDERECO_PARTIDA = "Avenida Antonio Ortega, 3604 - Pinhal, Cabreúva - SP, 13315-000"
DEFAULT_LAT_PARTIDA = -23.2515006
DEFAULT_LON_PARTIDA = -47.0845599

def show():
    if 'cenarios_roteirizacao' not in st.session_state:
        st.session_state.cenarios_roteirizacao = []
    st.header("Roteirizador de Entregas", divider="rainbow")
    st.write("Selecione os dados e o tipo de roteirização para gerar as rotas otimizadas.")
    st.divider()
    pedidos = carregar_pedidos()
    frota = carregar_frota()
    # Remove colunas duplicadas mantendo a primeira ocorrência
    frota = frota.loc[:, ~frota.columns.duplicated()]
    # Filtrar apenas veículos disponíveis
    if 'Disponível' in frota.columns:
        frota = frota[frota['Disponível'] == True].reset_index(drop=True)
    if pedidos.empty or frota.empty:
        st.warning("Importe pedidos e frota antes de roteirizar.")
        return
        
    # Seção de endereço de partida
    with st.expander("Configuração do endereço de partida", expanded=True):
        endereco_partida_salvo, lat_partida_salva, lon_partida_salva = carregar_endereco_partida()
        endereco_partida = st.text_input("Endereço de partida", endereco_partida_salvo or DEFAULT_ENDERECO_PARTIDA)
        col1, col2 = st.columns(2)
        with col1:
            lat_partida_manual = st.text_input("Latitude de partida", str(lat_partida_salva) if lat_partida_salva else str(DEFAULT_LAT_PARTIDA))
        with col2:
            lon_partida_manual = st.text_input("Longitude de partida", str(lon_partida_salva) if lon_partida_salva else str(DEFAULT_LON_PARTIDA))
        usar_coord_manual = st.checkbox("Usar coordenadas manualmente", value=False)
        if endereco_partida:
            if usar_coord_manual and lat_partida_manual and lon_partida_manual:
                try:
                    lat_partida = float(lat_partida_manual)
                    lon_partida = float(lon_partida_manual)
                except ValueError:
                    st.error("Latitude e longitude devem ser números válidos.")
                    return
            else:
                # Busca coordenadas salvas no banco antes de consultar API externa
                if lat_partida_salva is not None and lon_partida_salva is not None and endereco_partida == endereco_partida_salvo:
                    lat_partida = lat_partida_salva
                    lon_partida = lon_partida_salva
                else:
                    lat_partida, lon_partida = obter_coordenadas(endereco_partida)
            if lat_partida is None or lon_partida is None:
                st.error("Não foi possível obter as coordenadas do endereço de partida. Preencha manualmente ou corrija o endereço.")
                st.info(f"Endereço: {endereco_partida}")
                st.info(f"Coordenadas atuais: {lat_partida_manual}, {lon_partida_manual}")
                return
            if (endereco_partida != endereco_partida_salvo or lat_partida != lat_partida_salva or lon_partida != lon_partida_salva):
                salvar_endereco_partida(endereco_partida, lat_partida, lon_partida)
        st.info(f"Endereço de partida atual: {endereco_partida}")
        st.info(f"Coordenadas atuais: {lat_partida}, {lon_partida}")
    st.divider()
    # Seção de seleção de tipo de roteirização
    st.markdown("### Tipo de Roteirização")
    tipo = st.selectbox("Selecione o tipo de roteirização", ["VRP", "CVRP", "VRPTW", "TSP"], key="tipo_roteirizacao")
    explicacoes = {
        "VRP": "VRP (Vehicle Routing Problem): Roteirização clássica para múltiplos veículos, minimizando a distância total percorrida.",
        "CVRP": "CVRP (Capacitated VRP): Considera a capacidade máxima de carga dos veículos além da roteirização.",
        "VRPTW": "VRPTW (VRP with Time Windows): Adiciona restrições de janelas de tempo para entregas em cada parada.",
        "TSP": "TSP (Traveling Salesman Problem): Roteirização para um único veículo visitando todos os pontos uma única vez."
    }
    st.info(explicacoes.get(tipo, ""))
    st.divider()
    # Resumo dos dados
    with st.container():
        st.markdown("#### Resumo dos Dados Importados")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Pedidos Importados", len(pedidos))
            st.metric("Regiões Distintas", pedidos['Região'].nunique() if 'Região' in pedidos.columns else 0)
        with col2:
            st.metric("Veículos na Frota", len(frota))
            st.metric("Peso Total a Entregar (Kg)", f"{pedidos['Peso dos Itens'].sum():,.0f} Kg" if 'Peso dos Itens' in pedidos.columns else "0 Kg")
    st.divider()
    # Botão de cálculo
    if st.button("Calcular rotas", use_container_width=True):
        st.write("Colunas de pedidos:", pedidos.columns.tolist())
        if 'Latitude' in pedidos.columns and 'Longitude' in pedidos.columns:
            st.write("Latitude/Longitude dos pedidos:")
            st.write(pedidos[['Latitude', 'Longitude']])
        else:
            st.warning("Pedidos não possuem colunas 'Latitude' e 'Longitude'.")
        # Diagnóstico: mostrar quantos pedidos têm coordenadas válidas
        pedidos_com_coord = pedidos.dropna(subset=['Latitude', 'Longitude'])
        pedidos_nao_alocados = pedidos[pedidos['Latitude'].isna() | pedidos['Longitude'].isna()]
        st.info(f"Pedidos com coordenadas válidas: {len(pedidos_com_coord)} de {len(pedidos)}")
        if pedidos_com_coord.empty:
            st.error("Nenhum pedido possui coordenadas válidas para roteirização.")
            if not pedidos_nao_alocados.empty:
                st.warning("Pedidos não alocados (sem coordenadas):")
                st.dataframe(pedidos_nao_alocados, use_container_width=True)
            return
        matriz = calcular_matriz_distancias(pedidos_com_coord[['Latitude', 'Longitude']].values.tolist())
        if matriz is None:
            st.error("Erro ao calcular a matriz de distâncias. Verifique se há pedidos com coordenadas válidas.")
            return
        st.write("Pedidos head:")
        st.dataframe(pedidos.head())
        st.write("Frota head:")
        st.dataframe(frota.head())
        st.write("Matriz de distâncias (shape):", getattr(matriz, 'shape', 'Não possui atributo shape'))
        st.write("Matriz de distâncias (amostra):", matriz[:5, :5] if hasattr(matriz, '__getitem__') else matriz)
        if tipo == "VRP":
            rotas = solver_vrp(pedidos, frota, matriz)
        elif tipo == "CVRP":
            rotas = solver_cvrp(pedidos, frota, matriz)
        elif tipo == "VRPTW":
            # Coleta as janelas de tempo da frota (veículos)
            if 'Janela Início' in frota.columns and 'Janela Fim' in frota.columns:
                janelas_tempo = list(zip(frota['Janela Início'], frota['Janela Fim']))
            else:
                janelas_tempo = [("05:00", "17:00")] * len(frota)
            # Coleta o tempo de descarga dos pedidos
            if 'Janela de Descarga' in pedidos.columns:
                tempos_descarga = pedidos['Janela de Descarga'].tolist()
            else:
                tempos_descarga = [30] * len(pedidos)
            rotas = solver_vrptw(pedidos, frota, matriz, janelas_tempo=janelas_tempo, tempos_descarga=tempos_descarga)
        elif tipo == "TSP":
            rotas = solver_tsp(pedidos[['Latitude', 'Longitude']].values, matriz)
        else:
            rotas = None
        st.write("Rotas retornadas:", rotas)
        if rotas is not None:
            st.success("Rotas otimizadas!")
            with st.expander("Visualizar Rotas Geradas", expanded=True):
                st.dataframe(rotas, use_container_width=True)
            cenario = {
                'data': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tipo': tipo,
                'rotas': rotas,
                'qtd_pedidos': len(pedidos),
                'qtd_veiculos': len(frota),
                'distancia_total': rotas['distancia'].sum() if 'distancia' in rotas.columns else None
            }
            st.session_state.cenarios_roteirizacao.append(cenario)
        else:
            st.error("Não foi possível gerar as rotas.")
            with st.expander("Detalhes do Erro", expanded=False):
                st.write("Pedidos vazio?", pedidos.empty)
                st.write("Frota vazio?", frota.empty)
                st.write("Coluna 'ID Veículo' na frota?", 'ID Veículo' in frota.columns)
                st.write("Pedidos head:")
                st.dataframe(pedidos.head())
                st.write("Frota head:")
                st.dataframe(frota.head())
    # Alerta para pedidos sem coordenadas válidas
        if not pedidos_nao_alocados.empty:
            st.error(f"Atenção: {len(pedidos_nao_alocados)} pedidos não possuem coordenadas válidas e não serão roteirizados. Corrija as coordenadas na tela de pedidos.")
            st.dataframe(pedidos_nao_alocados, use_container_width=True)
    # Histórico de cenários
    if st.session_state.cenarios_roteirizacao:
        st.subheader("Cenários de Roteirização Salvos")
        df_cenarios = pd.DataFrame([
            {
                'Data': c['data'],
                'Tipo': c['tipo'],
                'Pedidos': c['qtd_pedidos'],
                'Veículos': c['qtd_veiculos'],
                'Distância Total': c['distancia_total']
            }
            for c in st.session_state.cenarios_roteirizacao
        ])
        st.dataframe(df_cenarios, use_container_width=True)
        idx = st.selectbox("Visualizar rotas do cenário", range(len(st.session_state.cenarios_roteirizacao)), format_func=lambda i: f"{df_cenarios.iloc[i]['Data']} - {df_cenarios.iloc[i]['Tipo']}")
        st.write("Rotas do cenário selecionado:")
        st.dataframe(st.session_state.cenarios_roteirizacao[idx]['rotas'], use_container_width=True)
        if st.button("Visualizar rotas no mapa do cenário selecionado", use_container_width=True):
            rotas_sel = st.session_state.cenarios_roteirizacao[idx]['rotas']
            if 'Latitude' in rotas_sel.columns and 'Longitude' in rotas_sel.columns:
                st.map(rotas_sel.rename(columns={'Latitude': 'latitude', 'Longitude': 'longitude'}).dropna(subset=['latitude', 'longitude']))
            else:
                st.warning("Não há coordenadas suficientes para exibir no mapa.")
st.markdown("""
<style>
.kpi-card {
    background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
    display: flex;
    align-items: center;
    gap: 1.2rem;
}
.kpi-icon {
    font-size: 2.2rem;
    margin-right: 1rem;
}
.section-title {
    font-size: 1.3rem;
    font-weight: 700;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
    color: #1976d2;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.alert-info {
    background: #e3f2fd;
    color: #1565c0;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.alert-success {
    background: #e8f5e9;
    color: #388e3c;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.alert-warning {
    background: #fffde7;
    color: #fbc02d;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
.alert-error {
    background: #ffebee;
    color: #c62828;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 0.7rem;
}
</style>
""", unsafe_allow_html=True)
