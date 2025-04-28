import streamlit as st
import pandas as pd
from database import carregar_pedidos, carregar_endereco_partida # Adicionado carregar_endereco_partida
import folium
from streamlit_folium import st_folium

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

def show():
    st.header("Mapas de Rotas", divider="rainbow")
    st.write("Visualize no mapa os pontos dos pedidos e as rotas por veículo.")
    st.divider()

    # <<< INICIALIZAR O MAPA AQUI >>>
    # Tenta carregar o endereço de partida para centralizar o mapa inicialmente
    endereco_partida, lat_partida, lon_partida = carregar_endereco_partida()
    # Usa coordenadas de partida salvas ou um default (ex: centro de SP)
    default_location = [lat_partida, lon_partida] if lat_partida and lon_partida else [-23.5505, -46.6333]
    m = folium.Map(location=default_location, zoom_start=10) # Cria o objeto mapa 'm'

    try:
        pedidos = carregar_pedidos()
        # ... (possível carregamento de frota) ...

        if pedidos is not None and not pedidos.empty:
            pedidos_mapa = pedidos.dropna(subset=['Latitude', 'Longitude']).copy()

            if not pedidos_mapa.empty:
                # Adiciona marcador para cada pedido
                for idx, row in pedidos_mapa.iterrows():
                    num_pedido = str(row.get('Nº Pedido', 'N/A'))
                    tooltip_text = f"Pedido: {num_pedido}<br>Cliente: {row.get('Nome Cliente', '')}"

                    folium.CircleMarker(
                        location=[row['Latitude'], row['Longitude']],
                        radius=5,
                        color='red',
                        fill=True,
                        fill_color='red',
                        fill_opacity=0.7,
                        tooltip=tooltip_text
                    ).add_to(m) # Agora 'm' existe

                # Ajusta o zoom para conter todos os pedidos
                map_bounds = [
                    [pedidos_mapa['Latitude'].min(), pedidos_mapa['Longitude'].min()],
                    [pedidos_mapa['Latitude'].max(), pedidos_mapa['Longitude'].max()]
                ]
                m.fit_bounds(map_bounds, padding=(0.01, 0.01))

            else:
                st.warning("Nenhum pedido com coordenadas válidas para exibir no mapa.")
                # Mapa já foi criado com localização default

        else:
            st.warning("Não foi possível carregar os dados dos pedidos.")
            # Mapa já foi criado com localização default

        # Exibe o mapa (agora 'm' sempre existe)
        st_folium(m, width=725, height=500)

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {str(e)}")
        import traceback
        traceback.print_exc()

    # Exibir rotas por placa se houver cenários roteirizados
    if 'cenarios_roteirizacao' in st.session_state and st.session_state.cenarios_roteirizacao:
        st.divider()
        st.markdown('<div class="section-title">🚚 Visualizar rotas por veículo</div>', unsafe_allow_html=True)
        # Selecionar cenário
        df_cenarios = pd.DataFrame([
            {
                'Data': c['data'],
                'Tipo': c['tipo'],
                'Pedidos': c.get('qtd_pedidos', ''),
                'Veículos': c.get('qtd_veiculos', ''),
                'Distância Total': c.get('distancia_total', '')
            }
            for c in st.session_state.cenarios_roteirizacao
        ])
        idx = st.selectbox("Selecione o cenário de roteirização", range(len(st.session_state.cenarios_roteirizacao)), format_func=lambda i: f"{df_cenarios.iloc[i]['Data']} - {df_cenarios.iloc[i]['Tipo']}")
        rotas = st.session_state.cenarios_roteirizacao[idx]['rotas']
        if 'Veículo' in rotas.columns:
            placas = rotas['Veículo'].dropna().unique().tolist()
            placa_sel = st.selectbox("Selecione a placa do veículo para visualizar a rota", placas)
            rota_veic = rotas[rotas['Veículo'] == placa_sel]
            if 'Latitude' in rota_veic.columns and 'Longitude' in rota_veic.columns:
                st.map(rota_veic.rename(columns={'Latitude': 'latitude', 'Longitude': 'longitude'}).dropna(subset=['latitude', 'longitude']))
                st.dataframe(rota_veic, use_container_width=True)
                # --- KPIs do veículo selecionado ---
                from database import carregar_frota
                frota_df = carregar_frota()
                capacidade_kg = None
                if 'Placa' in frota_df.columns and 'Capacidade (Kg)' in frota_df.columns:
                    cap_row = frota_df[frota_df['Placa'] == placa_sel]
                    if not cap_row.empty:
                        capacidade_kg = cap_row.iloc[0]['Capacidade (Kg)']
                peso_total = rota_veic['Peso dos Itens'].sum() if 'Peso dos Itens' in rota_veic.columns else None
                qtd_entregas = len(rota_veic)
                colk1, colk2 = st.columns(2)
                with colk1:
                    st.markdown(f'<div class="kpi-card"><span class="kpi-icon">🚚</span><div><b>Placa</b><br><span style="font-size:1.3rem">{placa_sel}</span></div></div>', unsafe_allow_html=True)
                with colk2:
                    st.markdown(f'<div class="kpi-card"><span class="kpi-icon">🚛</span><div><b>Capacidade do Veículo</b><br><span style="font-size:1.3rem">{capacidade_kg if capacidade_kg is not None else "-"} Kg</span></div></div>', unsafe_allow_html=True)
                colk3, colk4 = st.columns(2)
                with colk3:
                    st.markdown(f'<div class="kpi-card"><span class="kpi-icon">📦</span><div><b>Entregas</b><br><span style="font-size:1.3rem">{qtd_entregas}</span></div></div>', unsafe_allow_html=True)
                with colk4:
                    st.markdown(f'<div class="kpi-card"><span class="kpi-icon">⚖️</span><div><b>Peso Total no Veículo</b><br><span style="font-size:1.3rem">{peso_total:,.0f} Kg</span></div></div>', unsafe_allow_html=True)
            else:
                st.warning("Não há coordenadas suficientes para exibir a rota no mapa.")
        else:
            st.warning("As rotas não possuem coluna de veículo para seleção.")
    else:
        st.info("Gere rotas na página de Roteirização para visualizar por veículo.")
