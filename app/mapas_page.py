import streamlit as st
import pandas as pd
from database import carregar_pedidos, carregar_endereco_partida
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import random
import time # Necessário para o sleep
import os # <<< ADICIONADO para verificar existência do arquivo

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
st.header("Mapas de Pedidos", divider="rainbow")
st.write("Visualize todos os pedidos e rotas no mapa de forma simples e rápida.")
st.divider()

# <<< ADICIONADO: Caminho para o arquivo CSV >>>
ROTEIRIZACAO_CSV_PATH = "/workspaces/WazeLog/data/Roteirizacao.csv"

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
    opcoes_visualizacao = ["Mostrar apenas pedidos"]
    # <<< ADICIONADO: Opção para carregar do CSV >>>
    if os.path.exists(ROTEIRIZACAO_CSV_PATH):
        opcoes_visualizacao.append("Carregar última rota salva (CSV)")
    # Adiciona cenários da sessão
    opcoes_visualizacao.extend([
        f"{i}: {c.get('data', '')} - {c.get('tipo', '')} ({c.get('qtd_pedidos_roteirizados', '?')} pedidos)"
        for i, c in enumerate(cenarios_disponiveis)
    ])

    selecao = st.selectbox(
        "Selecione o que deseja visualizar no mapa:",
        options=opcoes_visualizacao,
        index=0 # Padrão é "Mostrar apenas pedidos"
    )

    # Inicializa variáveis do mapa
    map_location = default_depot_location
    rotas_df = None
    pedidos_mapa = pd.DataFrame()
    depot_lat = default_depot_location[0]
    depot_lon = default_depot_location[1]

    # --- Processa a Seleção ---
    if selecao == "Mostrar apenas pedidos":
        st.info("Exibindo localizações dos pedidos carregados.")
        if pedidos_todos is not None:
            pedidos_mapa = pedidos_todos.dropna(subset=['Latitude', 'Longitude']).copy()
            if not pedidos_mapa.empty:
                df_map = pedidos_mapa.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
                st.map(df_map)
            else:
                st.warning("Nenhum pedido com coordenadas válidas encontrado.")
    # <<< ADICIONADO: Lógica para carregar do CSV >>>
    elif selecao == "Carregar última rota salva (CSV)":
        st.info(f"Tentando carregar a última rota salva de {ROTEIRIZACAO_CSV_PATH}")
        try:
            rotas_df = pd.read_csv(ROTEIRIZACAO_CSV_PATH, encoding='utf-8')
            if not rotas_df.empty and 'Latitude' in rotas_df.columns and 'Longitude' in rotas_df.columns:
                st.success(f"Rota carregada com sucesso do arquivo CSV ({len(rotas_df)} pontos).")
                # Usa as coordenadas do depósito salvas
                depot_lat = default_depot_location[0]
                depot_lon = default_depot_location[1]
                map_location = [depot_lat, depot_lon]
            else:
                st.error("O arquivo CSV está vazio ou não contém as colunas 'Latitude' e 'Longitude'.")
                rotas_df = None # Garante que não prossiga
        except FileNotFoundError:
            st.error(f"Arquivo {ROTEIRIZACAO_CSV_PATH} não encontrado.")
            rotas_df = None
        except Exception as e:
            st.error(f"Erro ao ler o arquivo CSV: {e}")
            rotas_df = None

    # <<< MODIFICADO: Condição para cenários da sessão >>>
    elif ":" in selecao: # Identifica cenários da sessão pelo formato "índice: descrição"
        try:
            idx_cenario = int(selecao.split(":")[0])
            cenario_selecionado = cenarios_disponiveis[idx_cenario]
            rotas_df = cenario_selecionado.get('rotas')
            depot_lat = cenario_selecionado.get('lat_partida', default_depot_location[0])
            depot_lon = cenario_selecionado.get('lon_partida', default_depot_location[1])
            map_location = [depot_lat, depot_lon]

            if rotas_df is not None and not rotas_df.empty and 'Latitude' in rotas_df.columns and 'Longitude' in rotas_df.columns:
                st.info(f"Exibindo rotas do cenário: {cenario_selecionado.get('data', '')} ({cenario_selecionado.get('tipo', '')})")
                # Filtro de placas e cards de resumo
                placa_selecionada = None
                if 'Veículo' in rotas_df.columns:
                    placas_unicas = rotas_df['Veículo'].dropna().unique().tolist()
                    placa_selecionada = st.selectbox(
                        "Selecione a placa do veículo para análise:",
                        options=placas_unicas,
                        index=0,
                        help="Selecione uma placa para visualizar e analisar as rotas desse veículo no mapa."
                    )
                    if placa_selecionada:
                        rotas_df = rotas_df[rotas_df['Veículo'] == placa_selecionada]
                        # Cards de resumo
                        capacidade_veiculo = None
                        frota_df = None
                        try:
                            from database import carregar_frota
                            frota_df = carregar_frota()
                        except Exception:
                            pass
                        if frota_df is not None and not frota_df.empty and 'Placa' in frota_df.columns:
                            veic_row = frota_df[frota_df['Placa'] == placa_selecionada]
                            if not veic_row.empty:
                                capacidade_veiculo = veic_row.iloc[0].get('Capacidade (Kg)', None)
                        qtd_pedidos = len(rotas_df)
                        peso_total = rotas_df['Peso dos Itens'].sum() if 'Peso dos Itens' in rotas_df.columns else 0
                # Exibe rotas no mapa com trajeto real por ruas usando OSRM
                if not rotas_df.empty:
                    pontos = rotas_df.dropna(subset=["Latitude", "Longitude"])
                    if not pontos.empty:
                        if 'Sequencia' in pontos.columns:
                            pontos = pontos.sort_values('Sequencia')
                        coords = [[depot_lat, depot_lon]]
                        coords += pontos[["Latitude", "Longitude"]].values.tolist()
                        if len(coords) > 2 and (coords[-1] != coords[0]):
                            coords.append([depot_lat, depot_lon])
                        m = folium.Map(location=[depot_lat, depot_lon], zoom_start=12)
                        folium.Marker([depot_lat, depot_lon], icon=folium.Icon(color='blue', icon='home'), tooltip='Depósito').add_to(m)
                        for i, row in pontos.iterrows():
                            # <<< MODIFICADO: Garante que 'Nº Pedido' seja usado no tooltip e popup >>>
                            pedido_info = f"Pedido: {row.get('Nº Pedido', 'ID Desconhecido')}"
                            folium.Marker(
                                [row['Latitude'], row['Longitude']],
                                tooltip=pedido_info, # Mostra ao passar o mouse
                                popup=pedido_info,   # Mostra ao clicar
                                icon=folium.Icon(color='red', icon='info-sign') # Mantém ícone vermelho
                            ).add_to(m)
                        # Trajeto real por ruas (OSRM)
                        # Calcular distância total (km) e tempo total (min) da rota
                        distancia_total_km = 0
                        tempo_total_min = 0
                        import requests
                        for i in range(len(coords)-1):
                            origem = coords[i]
                            destino = coords[i+1]
                            url = f"http://localhost:5000/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}?overview=full&geometries=geojson"
                            try:
                                resp = requests.get(url, timeout=10)
                                if resp.status_code == 200:
                                    data = resp.json()
                                    if data.get('routes'):
                                        route = data['routes'][0]
                                        geometry = route['geometry']
                                        # Define cor: vermelho para ida, azul para volta
                                        if i < len(coords)-2:
                                            cor_linha = 'red'  # Ida
                                        else:
                                            cor_linha = 'blue' # Volta para base
                                        folium.PolyLine(
                                            locations=[(lat, lon) for lon, lat in geometry['coordinates']],
                                            color=cor_linha, weight=4, opacity=0.8
                                        ).add_to(m)
                                        distancia_total_km += route.get('distance', 0) / 1000
                                        tempo_total_min += route.get('duration', 0) / 60
                            except Exception:
                                pass
                        st_folium(m, width=None, height=500)
                        # Exibir métricas organizadas em 2 colunas, separadas por '-'
                        with st.container():
                            col_esq, col_dir = st.columns(2)
                            with col_esq:
                                st.metric("Placa do Veículo", placa_selecionada)
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                st.metric("Pedidos Empenhados", qtd_pedidos)
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                st.metric("Distância Total (km)", f"{distancia_total_km:.1f}")
                            with col_dir:
                                st.metric("Capacidade do Veículo (Kg)", f"{capacidade_veiculo:,.1f}" if capacidade_veiculo is not None else "N/A")
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                st.metric("Peso Empenhado (Kg)", f"{peso_total:,.1f}")
                                st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                                # Exibir tempo estimado no formato hh:mm
                                horas = int(tempo_total_min // 60) if tempo_total_min else 0
                                minutos = int(round(tempo_total_min % 60)) if tempo_total_min else 0
                                tempo_formatado = f"{horas}:{minutos:02d}"
                                st.metric("Tempo Estimado (h)", tempo_formatado)
                    else:
                        st.info("Não há coordenadas válidas para exibir o trajeto.")
                else:
                    st.info("Não há dados de rota para a placa selecionada.")
            else:
                st.warning("Dados de rotas ou coordenadas ausentes no cenário selecionado. Exibindo apenas depósito.")
        except (ValueError, IndexError):
            st.error("Erro ao selecionar o cenário.")

    # --- Lógica de Exibição do Mapa (comum para CSV e Cenários) ---
    if rotas_df is not None and not rotas_df.empty and 'Latitude' in rotas_df.columns and 'Longitude' in rotas_df.columns:
        # Filtro de placas e cards de resumo
        placa_selecionada = None
        if 'Veículo' in rotas_df.columns:
            placas_unicas = rotas_df['Veículo'].dropna().unique().tolist()
            placa_selecionada = st.selectbox(
                "Selecione a placa do veículo para análise:",
                options=placas_unicas,
                index=0,
                help="Selecione uma placa para visualizar e analisar as rotas desse veículo no mapa."
            )
            if placa_selecionada:
                rotas_df = rotas_df[rotas_df['Veículo'] == placa_selecionada]
                # Cards de resumo
                capacidade_veiculo = None
                frota_df = None
                try:
                    from database import carregar_frota
                    frota_df = carregar_frota()
                except Exception:
                    pass
                if frota_df is not None and not frota_df.empty and 'Placa' in frota_df.columns:
                    veic_row = frota_df[frota_df['Placa'] == placa_selecionada]
                    if not veic_row.empty:
                        capacidade_veiculo = veic_row.iloc[0].get('Capacidade (Kg)', None)
                qtd_pedidos = len(rotas_df)
                peso_total = rotas_df['Peso dos Itens'].sum() if 'Peso dos Itens' in rotas_df.columns else 0
        # Exibe rotas no mapa com trajeto real por ruas usando OSRM
        if not rotas_df.empty:
            pontos = rotas_df.dropna(subset=["Latitude", "Longitude"])
            if not pontos.empty:
                if 'Sequencia' in pontos.columns:
                    pontos = pontos.sort_values('Sequencia')
                coords = [[depot_lat, depot_lon]]
                coords += pontos[["Latitude", "Longitude"]].values.tolist()
                if len(coords) > 2 and (coords[-1] != coords[0]):
                    coords.append([depot_lat, depot_lon])
                m = folium.Map(location=[depot_lat, depot_lon], zoom_start=12)
                folium.Marker([depot_lat, depot_lon], icon=folium.Icon(color='blue', icon='home'), tooltip='Depósito').add_to(m)
                for i, row in pontos.iterrows():
                    # <<< MODIFICADO: Garante que 'Nº Pedido' seja usado no tooltip e popup >>>
                    pedido_info = f"Pedido: {row.get('Nº Pedido', 'ID Desconhecido')}"
                    folium.Marker(
                        [row['Latitude'], row['Longitude']],
                        tooltip=pedido_info, # Mostra ao passar o mouse
                        popup=pedido_info,   # Mostra ao clicar
                        icon=folium.Icon(color='red', icon='info-sign') # Mantém ícone vermelho
                    ).add_to(m)
                # Trajeto real por ruas (OSRM)
                # Calcular distância total (km) e tempo total (min) da rota
                distancia_total_km = 0
                tempo_total_min = 0
                import requests
                for i in range(len(coords)-1):
                    origem = coords[i]
                    destino = coords[i+1]
                    url = f"http://localhost:5000/route/v1/driving/{origem[1]},{origem[0]};{destino[1]},{destino[0]}?overview=full&geometries=geojson"
                    try:
                        resp = requests.get(url, timeout=10)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get('routes'):
                                route = data['routes'][0]
                                geometry = route['geometry']
                                # Define cor: vermelho para ida, azul para volta
                                if i < len(coords)-2:
                                    cor_linha = 'red'  # Ida
                                else:
                                    cor_linha = 'blue' # Volta para base
                                folium.PolyLine(
                                    locations=[(lat, lon) for lon, lat in geometry['coordinates']],
                                    color=cor_linha, weight=4, opacity=0.8
                                ).add_to(m)
                                distancia_total_km += route.get('distance', 0) / 1000
                                tempo_total_min += route.get('duration', 0) / 60
                    except Exception:
                        pass
                st_folium(m, width=None, height=500)
                # Exibir métricas organizadas em 2 colunas, separadas por '-'
                with st.container():
                    col_esq, col_dir = st.columns(2)
                    with col_esq:
                        st.metric("Placa do Veículo", placa_selecionada)
                        st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                        st.metric("Pedidos Empenhados", qtd_pedidos)
                        st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                        st.metric("Distância Total (km)", f"{distancia_total_km:.1f}")
                    with col_dir:
                        st.metric("Capacidade do Veículo (Kg)", f"{capacidade_veiculo:,.1f}" if capacidade_veiculo is not None else "N/A")
                        st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                        st.metric("Peso Empenhado (Kg)", f"{peso_total:,.1f}")
                        st.markdown("<div style='font-size:1.2rem;text-align:center;'>-</div>", unsafe_allow_html=True)
                        # Exibir tempo estimado no formato hh:mm
                        horas = int(tempo_total_min // 60) if tempo_total_min else 0
                        minutos = int(round(tempo_total_min % 60)) if tempo_total_min else 0
                        tempo_formatado = f"{horas}:{minutos:02d}"
                        st.metric("Tempo Estimado (h)", tempo_formatado)
            else:
                st.info("Não há coordenadas válidas para exibir o trajeto.")
        else:
            st.info("Não há dados de rota para a placa selecionada.")
    # <<< ADICIONADO: Mensagem se rotas_df for None após tentativa de carga >>>
    elif selecao != "Mostrar apenas pedidos": # Se tentou carregar CSV ou cenário e falhou
        st.warning("Não foi possível carregar ou exibir os dados da rota selecionada.")

# Comentar execução direta se a navegação for centralizada
# if __name__ == "__main__":
#     show()
