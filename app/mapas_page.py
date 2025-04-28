import streamlit as st
import pandas as pd
from database import carregar_pedidos, carregar_endereco_partida
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import random
import time # Necessário para o sleep

# Função para gerar cores aleatórias
def gerar_cor_aleatoria():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

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
    align-items: center,
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

def show():
    st.header("Mapas de Rotas", divider="rainbow")
    st.write("Visualize no mapa os pontos dos pedidos e as rotas por veículo.")
    st.divider()

    # Carrega dados básicos
    pedidos_todos = carregar_pedidos()
    endereco_partida_salvo, lat_partida_salva, lon_partida_salva = carregar_endereco_partida()
    default_depot_location = [lat_partida_salva, lon_partida_salva] if lat_partida_salva and lon_partida_salva else [-23.5505, -46.6333]

    # --- Seletor de Visualização ---
    cenarios_disponiveis = st.session_state.get('cenarios_roteirizacao', [])
    opcoes_visualizacao = ["Mostrar apenas pedidos"] + [
        f"{i}: {c.get('data', '')} - {c.get('tipo', '')} ({c.get('qtd_pedidos_roteirizados', '?')} pedidos)"
        for i, c in enumerate(cenarios_disponiveis)
    ]

    selecao = st.selectbox(
        "Selecione o que deseja visualizar no mapa:",
        options=opcoes_visualizacao,
        index=0 # Padrão é "Mostrar apenas pedidos"
    )

    # Inicializa variáveis do mapa
    map_location = default_depot_location
    zoom_start = 11 # Mantém zoom aumentado
    rotas_df = None
    pedidos_mapa = pd.DataFrame()
    depot_lat = default_depot_location[0]
    depot_lon = default_depot_location[1]
    map_bounds = None

    # --- Processa a Seleção ---
    if selecao == "Mostrar apenas pedidos":
        st.info("Exibindo localizações dos pedidos carregados.")
        if pedidos_todos is not None:
            pedidos_mapa = pedidos_todos.dropna(subset=['Latitude', 'Longitude']).copy()
            if not pedidos_mapa.empty:
                 # Calcula bounds para centralizar
                 try:
                     lat_min = pedidos_mapa['Latitude'].min()
                     lon_min = pedidos_mapa['Longitude'].min()
                     lat_max = pedidos_mapa['Latitude'].max()
                     lon_max = pedidos_mapa['Longitude'].max()

                     map_bounds = [[lat_min, lon_min], [lat_max, lon_max]]

                     # Adiciona depósito aos bounds se tiver coordenadas válidas
                     if lat_partida_salva and lon_partida_salva:
                          map_bounds[0][0] = min(map_bounds[0][0], lat_partida_salva)
                          map_bounds[0][1] = min(map_bounds[0][1], lon_partida_salva)
                          map_bounds[1][0] = max(map_bounds[1][0], lat_partida_salva)
                          map_bounds[1][1] = max(map_bounds[1][1], lon_partida_salva)

                     # VERIFICAÇÃO DO TAMANHO DOS BOUNDS
                     max_lat_span = 10.0
                     max_lon_span = 10.0
                     lat_span = map_bounds[1][0] - map_bounds[0][0]
                     lon_span = map_bounds[1][1] - map_bounds[0][1]

                     if lat_span > max_lat_span or lon_span > max_lon_span:
                          st.warning(f"Bounds muito amplos ({lat_span:.2f} lat, {lon_span:.2f} lon). Possíveis outliers. Usando zoom padrão.")
                          map_bounds = None
                 except Exception as bound_calc_err:
                      st.error(f"Erro ao calcular bounds: {bound_calc_err}")
                      map_bounds = None
            else:
                 st.warning("Nenhum pedido com coordenadas válidas encontrado.")
                 map_bounds = None

    else: # Um cenário foi selecionado
        try:
            idx_cenario = int(selecao.split(":")[0])
            cenario_selecionado = cenarios_disponiveis[idx_cenario]
            rotas_df = cenario_selecionado.get('rotas')
            depot_lat = cenario_selecionado.get('lat_partida', default_depot_location[0])
            depot_lon = cenario_selecionado.get('lon_partida', default_depot_location[1])
            map_location = [depot_lat, depot_lon]

            if rotas_df is not None and not rotas_df.empty and 'Latitude' in rotas_df.columns and 'Longitude' in rotas_df.columns:
                st.info(f"Exibindo rotas do cenário: {cenario_selecionado.get('data', '')} ({cenario_selecionado.get('tipo', '')})")
                # Calcula bounds para centralizar rotas e depósito
                try:
                    lat_min = rotas_df['Latitude'].min()
                    lon_min = rotas_df['Longitude'].min()
                    lat_max = rotas_df['Latitude'].max()
                    lon_max = rotas_df['Longitude'].max()
                    map_bounds = [[lat_min, lon_min], [lat_max, lon_max]]
                    # Adiciona depósito
                    map_bounds[0][0] = min(map_bounds[0][0], depot_lat)
                    map_bounds[0][1] = min(map_bounds[0][1], depot_lon)
                    map_bounds[1][0] = max(map_bounds[1][0], depot_lat)
                    map_bounds[1][1] = max(map_bounds[1][1], depot_lon)

                    # Verifica span também para rotas
                    max_lat_span = 10.0
                    max_lon_span = 10.0
                    lat_span = map_bounds[1][0] - map_bounds[0][0]
                    lon_span = map_bounds[1][1] - map_bounds[0][1]
                    if lat_span > max_lat_span or lon_span > max_lon_span:
                         st.warning(f"Bounds das rotas muito amplos ({lat_span:.2f} lat, {lon_span:.2f} lon). Usando zoom padrão.")
                         map_bounds = None

                except Exception as bound_calc_err_rota:
                    st.error(f"Erro ao calcular bounds das rotas: {bound_calc_err_rota}")
                    map_bounds = None

            else:
                st.warning("Dados de rotas ou coordenadas ausentes no cenário selecionado. Exibindo apenas depósito.")
                rotas_df = None
                pedidos_mapa = pd.DataFrame()

        except (ValueError, IndexError):
            st.error("Erro ao selecionar o cenário.")
            selecao = "Mostrar apenas pedidos"
            if pedidos_todos is not None:
                 pedidos_mapa = pedidos_todos.dropna(subset=['Latitude', 'Longitude']).copy()


    # --- Cria e Plota o Mapa ---
    m = folium.Map(location=map_location, zoom_start=zoom_start, tiles='OpenStreetMap')

    # Plota Depósito (sempre que tiver coordenadas válidas)
    if depot_lat and depot_lon:
        folium.Marker(
            location=[depot_lat, depot_lon],
            tooltip=f"Depósito: {endereco_partida_salvo or 'Local Padrão'}",
            icon=folium.Icon(color='blue', icon='industry', prefix='fa')
        ).add_to(m)

    # Plota Pedidos (se selecionado "Mostrar apenas pedidos")
    if selecao == "Mostrar apenas pedidos" and not pedidos_mapa.empty:
        marker_cluster = MarkerCluster().add_to(m)
        total_markers_added = 0
        batch_size = 50
        delay_between_batches = 0.1

        # Adicionar marcadores em lotes
        num_pedidos = len(pedidos_mapa)
        for i in range(0, num_pedidos, batch_size):
            batch_df = pedidos_mapa.iloc[i:min(i + batch_size, num_pedidos)]

            for idx, row in batch_df.iterrows():
                num_pedido = str(row.get('Nº Pedido', 'N/A'))
                tooltip_text = f"Pedido: {num_pedido}"

                try:
                    lat = float(row['Latitude'])
                    lon = float(row['Longitude'])
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=5, color='red', fill=True, fill_color='red', fill_opacity=0.7,
                        tooltip=tooltip_text
                    ).add_to(marker_cluster)
                    total_markers_added += 1
                except Exception as marker_err:
                     st.error(f"Erro ao adicionar marcador para pedido {row.get('Nº Pedido', idx)} no lote: {marker_err}")

            time.sleep(delay_between_batches)

    # Plota Rotas (se um cenário válido foi selecionado)
    elif rotas_df is not None and not rotas_df.empty:
        cores_veiculos = {veiculo: gerar_cor_aleatoria() for veiculo in rotas_df['Veículo'].unique()}
        for idx, row in rotas_df.iterrows():
            cor_veiculo = cores_veiculos.get(row['Veículo'], 'gray')
            num_pedido = str(row.get('Nº Pedido', row.get('Pedido_Index_DF', 'N/A')))
            tooltip_rota = (
                f"Veículo: {row.get('Veículo', 'N/A')}<br>"
                f"Sequência: {row.get('Sequencia', 'N/A')}<br>"
                f"Pedido: {num_pedido}<br>"
                f"Cliente: {row.get('Cliente', 'N/A')}<br>"
                f"Chegada: {pd.to_timedelta(row.get('Chegada_Estimada_Sec', 0), unit='s') if 'Chegada_Estimada_Sec' in row else 'N/A'}<br>"
                f"Saída: {pd.to_timedelta(row.get('Saida_Estimada_Sec', 0), unit='s') if 'Saida_Estimada_Sec' in row else 'N/A'}"
            )
            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=5, color=cor_veiculo, fill=True, fill_color=cor_veiculo, fill_opacity=0.8,
                tooltip=tooltip_rota
            ).add_to(m)
        depot_coords = [depot_lat, depot_lon]
        for veiculo, rota in rotas_df.groupby('Veículo'):
            cor_veiculo = cores_veiculos.get(veiculo, 'gray')
            rota_ordenada = rota.sort_values(by='Sequencia') if 'Sequencia' in rota.columns else rota
            route_coords = [depot_coords] + rota_ordenada[['Latitude', 'Longitude']].values.tolist() + [depot_coords]
            folium.PolyLine(
                locations=route_coords,
                color=cor_veiculo,
                weight=3,
                opacity=0.7,
                tooltip=f"Rota Veículo: {veiculo}"
            ).add_to(m)


    # Ajusta o zoom do mapa SOMENTE se bounds foram calculados E SÃO VÁLIDOS
    if map_bounds:
        try:
            m.fit_bounds(map_bounds, padding=(0.01, 0.01))
        except Exception as fit_bounds_err:
            st.error(f"Erro ao ajustar bounds do mapa: {fit_bounds_err}")


    # Exibe o mapa
    try:
        # <<< Ajustar tamanho do mapa >>>
        st_folium(m, key="mapa_pedidos_cluster", use_container_width=True, height=1200, returned_objects=[]) # Usa largura do container e altura 600
    except Exception as st_folium_err:
        st.error(f"Erro ao exibir mapa com st_folium: {st_folium_err}")

    # try/except principal
    # except Exception as e:
    #     st.error(f"Ocorreu um erro inesperado ao gerar o mapa: {str(e)}")
    #     import traceback
    #     traceback.print_exc()

# Comentar execução direta se a navegação for centralizada
# if __name__ == "__main__":
#     show()
