import sys
import os
import streamlit as st
import pandas as pd
import requests
sys.dont_write_bytecode = True

st.set_page_config(page_title="Wazelog", layout="wide")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard_page import show as show_dashboard
from frota_page import show as show_frota
from pedidos_page import show as show_pedidos
from roteirizacao_page import show as show_roteirizacao
from mapas_page import show as show_mapas
from cnpj_page import show as show_cnpj
from database import init_db
init_db()

# Material Design aprimorado com cabeçalho e menu lateral com ícones
st.markdown('''

    <style>
    .main-header {
        background: linear-gradient(90deg, #1976d2 0%, #2196f3 100%);
        color: #fff;
        padding: 1.2rem 2rem 1.2rem 2rem;
        border-radius: 0 0 18px 18px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .main-header h1 {
        font-family: 'Roboto', sans-serif;
        font-size: 2.2rem;
        margin: 0;
        letter-spacing: 1px;
    }
    .main-header img {
        height: 48px;
        margin-right: 10px;
    }
    .stSidebar {
        background: #fff;
        border-radius: 16px;
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.06);
        padding-top: 1.5rem;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(25, 118, 210, 0.08);
    }
    </style>
''', unsafe_allow_html=True)

# Cabeçalho fixo
st.markdown(
    '''<div class="main-header">
        <img src="https://img.icons8.com/color/96/000000/route.png" alt="logo" />
        <h1>Wazelog - Roteirizador de Entregas</h1>
    </div>''',
    unsafe_allow_html=True
)

# Menu lateral customizado com design premium
st.markdown('''
<style>
.sidebar-menu-premium {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    margin-top: 1.5rem;
}
.menu-item-premium {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    padding: 2.1rem 1.2rem;
    border-radius: 16px;
    font-size: 1.25rem;
    font-weight: 600;
    color: #1976d2;
    background: #fff;
    box-shadow: 0 2px 8px rgba(25, 118, 210, 0.07);
    border: 1px solid transparent;
    transition: background 0.18s, color 0.18s, border 0.18s, box-shadow 0.18s;
    cursor: pointer;
    position: relative;
}
.menu-item-premium.selected {
    background: linear-gradient(90deg, #1565c0 0%, #1976d2 100%);
    color: #fff;
    border: 1px solid #1565c0;
    box-shadow: 0 4px 16px rgba(25, 118, 210, 0.13);
    padding: 0.2rem 0.5rem;
    margin-bottom: 1.1rem;
}
.menu-item-premium:hover {
    background: #e3f2fd;
    color: #1565c0;
    border: 2px solid #90caf9;
}
.menu-icon-premium {
    font-size: 2.1rem;
    filter: drop-shadow(0 1px 2px #90caf9);
    margin-right: 0.2rem;
}
.menu-title-premium {
    font-size: 1.4rem;
    font-weight: 800;
    color: #1976d2;
    margin-bottom: 1.2rem;
    letter-spacing: 1px;
    text-align: left;
    padding-left: 0.2rem;
}
.menu-divider-premium {
    height: 1px;
    background: linear-gradient(90deg, #1976d2 0%, #64b5f6 100%);
    margin: 0.7rem 0 0.7rem 0;
    border: none;
}
</style>
''', unsafe_allow_html=True)

# CSS aprimorado para modo claro e escuro (dark 100% escuro)
st.markdown('''
<style>
body[data-theme="dark"], .stApp[data-theme="dark"] {
    --card-bg: #181a1b !important;
    --card-fg: #f5f7fa !important;
    --section-title: #90caf9 !important;
    --table-bg: #181a1b !important;
    --table-fg: #f5f7fa !important;
    --container-bg: #181a1b !important;
    background: #181a1b !important;
    color: #f5f7fa !important;
}
body[data-theme="dark"] .kpi-card, .stApp[data-theme="dark"] .kpi-card,
body[data-theme="dark"] .stMetric, .stApp[data-theme="dark"] .stMetric,
body[data-theme="dark"] .stContainer, .stApp[data-theme="dark"] .stContainer {
    background: var(--card-bg, #181a1b) !important;
    color: var(--card-fg, #f5f7fa) !important;
    box-shadow: 0 2px 16px rgba(25, 118, 210, 0.18);
    border: 1px solid #23272b !important;
}
body[data-theme="dark"] .section-title, .stApp[data-theme="dark"] .section-title {
    color: var(--section-title, #90caf9) !important;
}
body[data-theme="dark"] .stDataFrame, .stApp[data-theme="dark"] .stDataFrame,
body[data-theme="dark"] .stDataEditor, .stApp[data-theme="dark"] .stDataEditor {
    background: var(--table-bg, #181a1b) !important;
    color: var(--table-fg, #f5f7fa) !important;
    border-radius: 16px !important;
    border: 1px solid #23272b !important;
}
body[data-theme="dark"] .stButton>button, .stApp[data-theme="dark"] .stButton>button,
body[data-theme="dark"] .stDownloadButton>button, .stApp[data-theme="dark"] .stDownloadButton>button {
    background: #23272b !important;
    color: #90caf9 !important;
    border: 1px solid #1976d2 !important;
}
body[data-theme="dark"] .stButton>button:hover, .stApp[data-theme="dark"] .stButton>button:hover,
body[data-theme="dark"] .stDownloadButton>button:hover, .stApp[data-theme="dark"] .stDownloadButton>button:hover {
    background: #1976d2 !important;
    color: #fff !important;
}
/* Remove gradientes claros e bordas claras do modo dark */
body[data-theme="dark"] .main-header {
    background: linear-gradient(90deg, #181a1b 0%, #23272b 100%) !important;
    color: #f5f7fa !important;
}
body[data-theme="dark"] .menu-item-premium {
    background: #23272b !important;
    color: #90caf9 !important;
    border: 1px solid #23272b !important;
}
body[data-theme="dark"] .menu-item-premium.selected {
    background: linear-gradient(90deg, #1976d2 0%, #23272b 100%) !important;
    color: #fff !important;
    border: 1px solid #1976d2 !important;
}
body[data-theme="dark"] .menu-item-premium:hover {
    background: #263238 !important;
    color: #90caf9 !important;
    border: 1.5px solid #90caf9 !important;
}
body[data-theme="dark"] .stSidebar {
    background: #181a1b !important;
    color: #f5f7fa !important;
    border: 1px solid #23272b !important;
}
</style>
''', unsafe_allow_html=True)

menu_itens = [
    ("Dashboard", "🏠"),
    ("Frota", "🚚"),
    ("Pedidos", "📦"),
    ("Roteirização", "🗺️"),
    ("Mapas", "🗾"),
    ("Busca CNPJ", "🔎")
]

with st.sidebar:
    st.markdown("<div class='menu-title-premium'>✨ Menu Principal</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-menu-premium'>", unsafe_allow_html=True)
    pagina = None
    for nome, icone in menu_itens:
        selected = st.session_state.get('pagina_selecionada', 'Dashboard') == nome
        btn_html = f"""
        <div class='menu-item-premium{' selected' if selected else ''}'>
            <span class='menu-icon-premium'>{icone}</span> {nome}
        </div>
        """
        if selected:
            st.markdown(btn_html, unsafe_allow_html=True)
            pagina = nome
        else:
            if st.button(f"{icone} {nome}", key=f"menu_{nome}"):
                st.session_state['pagina_selecionada'] = nome
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='menu-divider-premium'>", unsafe_allow_html=True)
    # Toggle dark mode
    if "modo_escuro" not in st.session_state:
        st.session_state["modo_escuro"] = False
    modo_escuro = st.toggle("🌙 Modo escuro", value=st.session_state["modo_escuro"], key="modo_escuro_toggle")
    st.session_state["modo_escuro"] = modo_escuro

# Tema claro/escuro
if st.session_state["modo_escuro"]:
    st.markdown('''
        <style>
        body, .stApp { background-color: #181a1b !important; }
        .main-header { background: linear-gradient(90deg, #23272b 0%, #1976d2 100%); color: #fff; }
        .sidebar-menu .menu-item, .sidebar-menu .menu-item.selected { color: #90caf9; }
        .sidebar-menu .menu-item.selected { background: #263238; }
        .stSidebar { background: #23272b; color: #fff; }
        .stDataFrame, .stDataEditor { background: #23272b; color: #fff; }
        </style>
    ''', unsafe_allow_html=True)

# Renderiza página selecionada
if pagina == "Dashboard":
    show_dashboard()
elif pagina == "Frota":
    show_frota()
elif pagina == "Pedidos":
    show_pedidos()
elif pagina == "Roteirização":
    show_roteirizacao()
elif pagina == "Mapas":
    show_mapas()
elif pagina == "Busca CNPJ":
    show_cnpj()
