import streamlit as st
from frota import processar_frota
from database import carregar_frota, salvar_frota
import pandas as pd

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
    st.header("Gerenciar Frota", divider="rainbow")
    st.write("Importe, visualize, edite, adicione ou remova veículos da frota.")
    st.divider()
    if 'df_frota' not in st.session_state:
        st.session_state.df_frota = pd.DataFrame()
    arquivo = st.file_uploader("Upload da planilha da frota", type=["xlsx", "xlsm", "csv", "json"])
    if arquivo:
        try:
            df = processar_frota(arquivo)
            st.session_state.df_frota = df.copy()
            salvar_frota(df)
            st.success("Frota importada com sucesso!")
        except Exception as e:
            st.error(f"Erro ao processar a frota: {e}")
    df = st.session_state.df_frota
    if df.empty:
        df = carregar_frota()
        st.session_state.df_frota = df.copy()
    if not df.empty:
        df = df.loc[:, ~df.columns.duplicated()]
        df.columns = [str(col) if col else f"Coluna_{i}" for i, col in enumerate(df.columns)]
        st.subheader("Editar Frota")
        df_editado = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="frota_editor")
        if not df_editado.equals(df):
            st.session_state.df_frota = df_editado.copy()
            salvar_frota(df_editado)
        st.divider()
        st.subheader("Remover veículos")
        def format_option(x):
            placa = df_editado.loc[x, 'Placa'] if 'Placa' in df_editado.columns else str(x)
            descricao = df_editado.loc[x, 'Descrição'] if 'Descrição' in df_editado.columns else ''
            return f"{placa} - {descricao}" if descricao else f"{placa}"
        indices_remover = st.multiselect("Selecione as linhas para remover", df_editado.index, format_func=format_option)
        if st.button("Remover selecionados") and indices_remover:
            st.session_state.df_frota = df_editado.drop(indices_remover).reset_index(drop=True)
            salvar_frota(st.session_state.df_frota)
            st.success("Veículos removidos!")
            st.rerun()
    st.divider()
    st.subheader("Adicionar novo veículo")
    with st.form("add_veiculo_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            placa = st.text_input("Placa")
            transportador = st.text_input("Transportador")
            descricao = st.text_input("Descrição")
        with col2:
            veiculo = st.text_input("Veículo")
            capacidade_cx = st.number_input("Capacidade (Cx)", min_value=0, step=1)
            capacidade_kg = st.number_input("Capacidade (Kg)", min_value=0.0, step=1.0, format="%.2f")
        with col3:
            disponivel = st.selectbox("Disponível", ["Sim", "Não"])
        submitted = st.form_submit_button("Adicionar veículo")
        if submitted and placa:
            novo = {
                "Placa": placa,
                "Transportador": transportador,
                "Descrição": descricao,
                "Veículo": veiculo,
                "Capacidade (Cx)": capacidade_cx,
                "Capacidade (Kg)": capacidade_kg,
                "Disponível": disponivel.lower() == "sim",
                "ID Veículo": placa
            }
            st.session_state.df_frota = pd.concat([st.session_state.df_frota, pd.DataFrame([novo])], ignore_index=True)
            salvar_frota(st.session_state.df_frota)
            st.success("Veículo adicionado!")
            st.rerun()
    # Botão de limpar frota
    if st.button("Limpar Frota", type="primary"):
        from database import limpar_frota
        limpar_frota()
        st.session_state.df_frota = pd.DataFrame()
        st.success("Frota limpa com sucesso!")
        st.rerun()
