import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
st.set_page_config(page_title="Wazelog", layout="wide")

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
    .sidebar-menu .menu-item {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        padding: 0.7rem 1rem;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: 500;
        color: #1976d2;
        margin-bottom: 0.2rem;
        cursor: pointer;
        transition: background 0.15s;
    }
    .sidebar-menu .menu-item.selected {
        background: #e3f2fd;
        color: #1565c0;
        font-weight: 700;
    }
    .sidebar-menu .menu-item:hover {
        background: #e3f2fd;
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

# Menu lateral customizado com ícones
menu_itens = [
    ("Dashboard", "🏠"),
    ("Frota", "🚚"),
    ("Pedidos", "📦"),
    ("Roteirização", "🗺️"),
    ("Mapas", "🗺️"),
    ("Busca CNPJ", "🔎")
]

with st.sidebar:
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-menu'>", unsafe_allow_html=True)
    pagina = None
    for nome, icone in menu_itens:
        if st.session_state.get('pagina_selecionada', 'Dashboard') == nome:
            st.markdown(f"<div class='menu-item selected'>{icone} {nome}</div>", unsafe_allow_html=True)
            pagina = nome
        else:
            if st.button(f"{icone} {nome}", key=f"menu_{nome}"):
                st.session_state['pagina_selecionada'] = nome
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    # Toggle dark mode
    modo_escuro = st.toggle("🌙 Modo escuro", value=False)

# Tema claro/escuro
if modo_escuro:
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
