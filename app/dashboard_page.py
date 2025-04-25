import streamlit as st
from database import carregar_pedidos, carregar_frota

def show():
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
    </style>
    """, unsafe_allow_html=True)
    st.header("Dashboard 🚀", divider="rainbow")
    st.markdown('<div class="alert-info">📊 Visão geral dos indicadores do <b>Wazelog</b>.</div>', unsafe_allow_html=True)
    pedidos = carregar_pedidos()
    total = len(pedidos)
    if 'Latitude' in pedidos.columns and 'Longitude' in pedidos.columns:
        com_coord = pedidos.dropna(subset=["Latitude", "Longitude"])
        total_coord = len(com_coord)
    else:
        total_coord = 0
    st.markdown('<div class="section-title">📦 Pedidos</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'<div class="kpi-card"><span class="kpi-icon">✅</span><div><b>Pedidos com coordenadas</b><br><span style="font-size:1.3rem">{total_coord} / {total}</span></div></div>', unsafe_allow_html=True)
    with col2:
        num_regioes = pedidos['Região'].nunique() if 'Região' in pedidos.columns else 0
        peso_total_pedidos = pedidos['Peso dos Itens'].sum() if 'Peso dos Itens' in pedidos.columns else 0
        st.markdown(f'<div class="kpi-card"><span class="kpi-icon">🗺️</span><div><b>Regiões distintas</b><br><span style="font-size:1.3rem">{num_regioes}</span></div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-card"><span class="kpi-icon">⚖️</span><div><b>Peso total a entregar (Kg)</b><br><span style="font-size:1.3rem">{peso_total_pedidos:,.0f} Kg</span></div></div>', unsafe_allow_html=True)
    st.divider()
    st.markdown('<div class="section-title">🚚 Frota</div>', unsafe_allow_html=True)
    frota = carregar_frota()
    total_veiculos = len(frota)
    capacidade_total_kg = frota["Capacidade (Kg)"].sum() if "Capacidade (Kg)" in frota.columns else 0
    col3, col4 = st.columns(2)
    with col3:
        st.markdown(f'<div class="kpi-card"><span class="kpi-icon">🚚</span><div><b>Veículos na Frota</b><br><span style="font-size:1.3rem">{total_veiculos}</span></div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="kpi-card"><span class="kpi-icon">📦</span><div><b>Capacidade Total (Kg)</b><br><span style="font-size:1.3rem">{capacidade_total_kg:,.0f} Kg</span></div></div>', unsafe_allow_html=True)
    st.divider()
    st.caption("KPIs e gráficos em breve.")
