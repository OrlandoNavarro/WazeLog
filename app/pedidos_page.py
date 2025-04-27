import streamlit as st
from pedidos import processar_pedidos, obter_coordenadas
from database import carregar_pedidos, salvar_pedidos
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
    st.header("Gerenciar Pedidos", divider="rainbow")
    st.write("Importe, visualize, edite, adicione ou remova pedidos de entrega.")
    st.divider()
    if 'df_pedidos' not in st.session_state:
        st.session_state.df_pedidos = pd.DataFrame()
    arquivo = st.file_uploader("Upload da planilha de pedidos", type=["xlsx", "xlsm", "csv", "json"])
    if arquivo:
        try:
            with st.spinner("Processando pedidos e buscando coordenadas, isso pode levar alguns minutos..."):
                df = processar_pedidos(arquivo)
            st.session_state.df_pedidos = df.copy()
            salvar_pedidos(df)
            st.success("Pedidos importados com sucesso!")
        except Exception as e:
            st.error(f"Erro ao processar os pedidos: {e}")
    df = st.session_state.df_pedidos
    if df.empty:
        df = carregar_pedidos()
        st.session_state.df_pedidos = df.copy()
    if not df.empty:
        # Garantir que as colunas Regiao, Endereco Completo, Latitude e Longitude existam e estejam corretas
        if 'Endereço de Entrega' in df.columns and 'Bairro de Entrega' in df.columns and 'Cidade de Entrega' in df.columns:
            df['Região'] = df.apply(lambda row: f"{row['Cidade de Entrega']} - {row['Bairro de Entrega']}" if str(row['Cidade de Entrega']).strip().lower() == 'são paulo' and row['Bairro de Entrega'] else row['Cidade de Entrega'], axis=1)
            df['Endereço Completo'] = df['Endereço de Entrega'].astype(str) + ', ' + df['Bairro de Entrega'].astype(str) + ', ' + df['Cidade de Entrega'].astype(str)
        if 'Latitude' not in df.columns:
            df['Latitude'] = None
        if 'Longitude' not in df.columns:
            df['Longitude'] = None
        if 'Janela de Descarga' not in df.columns:
            df['Janela de Descarga'] = 30
        # Filtro para ordenar a planilha por coluna
        colunas_ordenaveis = list(df.columns)
        coluna_ordem = st.selectbox("Ordenar por", colunas_ordenaveis, index=0)
        if coluna_ordem:
            df = df.sort_values(by=coluna_ordem, key=lambda x: x.astype(str)).reset_index(drop=True)
        # Filtros avançados
        if 'Região' in df.columns:
            regioes = sorted([r for r in df['Região'].dropna().unique() if r and str(r).strip() and str(r).lower() != 'nan'])
        else:
            regioes = []
        regiao_filtro = st.selectbox("Filtrar por região", ["Todas"] + regioes)
        status_filtro = st.selectbox("Status de coordenadas", ["Todos", "Com coordenadas", "Sem coordenadas"])
        if 'Janela de Descarga' in df.columns:
            min_janela = int(df['Janela de Descarga'].min())
            max_janela = int(df['Janela de Descarga'].max())
            if min_janela < max_janela:
                janela_min, janela_max = st.slider(
                    "Filtrar por janela de descarga (minutos)",
                    min_value=min_janela,
                    max_value=max_janela,
                    value=(min_janela, max_janela)
                )
            else:
                st.info(f"Janela de descarga fixa: {min_janela} minutos")
                janela_min, janela_max = min_janela, max_janela
        else:
            janela_min, janela_max = 30, 30
        df_filtrado = df.copy()
        if regiao_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Região'] == regiao_filtro]
        if status_filtro == "Com coordenadas":
            df_filtrado = df_filtrado[df_filtrado['Latitude'].notnull() & df_filtrado['Longitude'].notnull()]
        elif status_filtro == "Sem coordenadas":
            df_filtrado = df_filtrado[df_filtrado['Latitude'].isnull() | df_filtrado['Longitude'].isnull()]
        if 'Janela de Descarga' in df_filtrado.columns:
            df_filtrado = df_filtrado[(df_filtrado['Janela de Descarga'] >= janela_min) & (df_filtrado['Janela de Descarga'] <= janela_max)]
        # Busca global
        filtro = st.text_input("Buscar pedidos (qualquer campo)")
        if filtro:
            filtro_lower = filtro.lower()
            df_filtrado = df_filtrado[df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(filtro_lower).any(), axis=1)]
        # Validação visual: destacar linhas com dados faltantes
        def get_row_style(row):
            falta_lat = 'Latitude' not in row or pd.isnull(row.get('Latitude'))
            falta_lon = 'Longitude' not in row or pd.isnull(row.get('Longitude'))
            falta_descarga = 'Janela de Descarga' not in row or pd.isnull(row.get('Janela de Descarga'))
            if falta_lat or falta_lon or falta_descarga:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)
        # Exibir apenas a planilha editável, sem duplicar visualização
        st.subheader("Editar Pedidos")
        df_editado = st.data_editor(
            df_filtrado,
            num_rows="dynamic",
            use_container_width=True,
            key="pedidos_editor",
            column_config={
                "Janela de Descarga": st.column_config.NumberColumn(
                    "Janela de Descarga",
                    format="%d min",
                    help="Tempo estimado de descarga no cliente (em minutos)."
                ),
                "Latitude": st.column_config.NumberColumn(
                    "Latitude",
                    help="Latitude do endereço de entrega."
                ),
                "Longitude": st.column_config.NumberColumn(
                    "Longitude",
                    help="Longitude do endereço de entrega."
                ),
                "Região": st.column_config.TextColumn(
                    "Região",
                    help="Região agrupada automaticamente pelo sistema."
                ),
                "Endereço Completo": st.column_config.TextColumn(
                    "Endereço Completo",
                    help="Endereço completo gerado a partir dos campos de endereço, bairro e cidade."
                )
            },
            column_order=df.columns.tolist(),
            hide_index=True
        )
        if not df_editado.equals(df_filtrado):
            # Atualiza o DataFrame original com as edições feitas no filtrado
            df_update = df.copy()
            df_update.update(df_editado)
            st.session_state.df_pedidos = df_update.copy()
            salvar_pedidos(st.session_state.df_pedidos)
        # Botão para reprocessar coordenadas
        if st.button("Reprocessar Coordenadas", type="primary"):
            with st.spinner("Reprocessando coordenadas apenas para pedidos sem coordenadas..."):
                df_pedidos = st.session_state.df_pedidos.copy()
                mask_sem_coord = df_pedidos['Latitude'].isnull() | df_pedidos['Longitude'].isnull()
                pedidos_sem_coord = df_pedidos[mask_sem_coord]
                n = len(pedidos_sem_coord)
                if n == 0:
                    st.success("Todos os pedidos já possuem coordenadas!")
                else:
                    latitudes = df_pedidos['Latitude'].tolist()
                    longitudes = df_pedidos['Longitude'].tolist()
                    progress_bar = st.progress(0, text="Buscando coordenadas...")
                    for idx, (i, row) in enumerate(pedidos_sem_coord.iterrows()):
                        lat, lon = obter_coordenadas(row['Endereço Completo'])
                        latitudes[i] = lat
                        longitudes[i] = lon
                        progress_bar.progress((idx + 1) / n, text=f"Buscando coordenadas... ({idx+1}/{n})")
                    df_pedidos['Latitude'] = latitudes
                    df_pedidos['Longitude'] = longitudes
                    progress_bar.empty()
                    salvar_pedidos(df_pedidos)
                    st.session_state.df_pedidos = df_pedidos.copy()
                    st.success("Coordenadas reprocessadas apenas para pedidos sem coordenadas!")
                    st.rerun()
        st.divider()
        st.subheader("Remover pedidos")
        # Remover pedidos selecionados
        def format_option(x):
            num = df_editado.loc[x, 'Nº Pedido'] if 'Nº Pedido' in df_editado.columns else str(x)
            cliente = df_editado.loc[x, 'Nome Cliente'] if 'Nome Cliente' in df_editado.columns else ''
            return f"{num} - {cliente}" if cliente else f"{num}"
        indices_remover = st.multiselect("Selecione os pedidos para remover", df_editado.index.tolist(), format_func=format_option)
        if st.button("Remover selecionados") and indices_remover:
            # Remover do DataFrame original com base no 'Nº Pedido' selecionado
            if 'Nº Pedido' in df_editado.columns and 'Nº Pedido' in st.session_state.df_pedidos.columns:
                pedidos_remover = df_editado.loc[indices_remover, 'Nº Pedido']
                st.session_state.df_pedidos = st.session_state.df_pedidos[~st.session_state.df_pedidos['Nº Pedido'].isin(pedidos_remover)].reset_index(drop=True)
            else:
                st.session_state.df_pedidos = st.session_state.df_pedidos.drop(indices_remover).reset_index(drop=True)
            salvar_pedidos(st.session_state.df_pedidos)
            st.success("Pedidos removidos!")
            st.rerun()
        # Botão para limpar todos os pedidos
        if st.button("Limpar todos os pedidos", type="primary"):
            st.session_state.df_pedidos = pd.DataFrame()
            salvar_pedidos(st.session_state.df_pedidos)
            st.success("Todos os pedidos foram removidos!")
            st.rerun()
    st.divider()
    st.subheader("Adicionar novo pedido")
    with st.form("add_pedido_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            numero = st.text_input("Nº Pedido")
            cod_cliente = st.text_input("Cód. Cliente")
            nome_cliente = st.text_input("Nome Cliente")
            grupo_cliente = st.text_input("Grupo Cliente")
        with col2:
            regiao = st.text_input("Região")
            endereco_entrega = st.text_input("Endereço de Entrega")
            bairro_entrega = st.text_input("Bairro de Entrega")
            cidade_entrega = st.text_input("Cidade de Entrega")
            endereco_completo = st.text_input("Endereço Completo", value="", disabled=True)
            qtde_itens = st.number_input("Qtde. dos Itens", min_value=0, step=1)
            peso_itens = st.number_input("Peso dos Itens", min_value=0.0, step=1.0, format="%.2f")
        with col3:
            latitude = st.number_input("Latitude", format="%.14f", value=-23.51689237191825)
            longitude = st.number_input("Longitude", format="%.14f", value=-46.48921155767101)
            anomalia = st.checkbox("Anomalia")
            janela_descarga = st.number_input("Janela de Descarga (min)", min_value=1, value=30, step=1, help="Tempo estimado de descarga no cliente (em minutos).")
        submitted = st.form_submit_button("Adicionar pedido")
        if submitted and numero:
            # Gerar Região automaticamente se não preenchida
            regiao_final = regiao.strip() if regiao.strip() else (f"{cidade_entrega} - {bairro_entrega}" if cidade_entrega.lower() == "são paulo" and bairro_entrega else cidade_entrega)
            # Gerar Endereço Completo automaticamente
            endereco_completo_final = f"{endereco_entrega}, {bairro_entrega}, {cidade_entrega}"
            novo = {
                "Nº Pedido": numero,
                "Cód. Cliente": cod_cliente,
                "Nome Cliente": nome_cliente,
                "Grupo Cliente": grupo_cliente,
                "Região": regiao_final,
                "Endereço Completo": endereco_completo_final,
                "Endereço de Entrega": endereco_entrega,
                "Bairro de Entrega": bairro_entrega,
                "Cidade de Entrega": cidade_entrega,
                "Qtde. dos Itens": qtde_itens,
                "Peso dos Itens": peso_itens,
                "Latitude": latitude,
                "Longitude": longitude,
                "Janela de Descarga": janela_descarga,
                "Anomalia": anomalia
            }
            st.session_state.df_pedidos = pd.concat([st.session_state.df_pedidos, pd.DataFrame([novo])], ignore_index=True)
            salvar_pedidos(st.session_state.df_pedidos)
            st.success("Pedido adicionado!")
            st.rerun()
    # Exportação de anomalias para CSV
    if 'df_filtrado' in locals():
        if 'Janela de Descarga' not in df_filtrado.columns:
            df_filtrado['Janela de Descarga'] = 30
        anomalias = df_filtrado[df_filtrado['Latitude'].isnull() | df_filtrado['Longitude'].isnull() | df_filtrado['Janela de Descarga'].isnull()]
        if not anomalias.empty:
            st.download_button(
                label="Exportar anomalias para CSV",
                data=anomalias.to_csv(index=False).encode('utf-8'),
                file_name=f"anomalias_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    # Visualização de pedidos no mapa (fora do formulário)
    if 'df_filtrado' in locals() and st.button("Visualizar pedidos no mapa"):
        if 'Latitude' in df_filtrado.columns and 'Longitude' in df_filtrado.columns:
            st.map(df_filtrado.dropna(subset=["Latitude", "Longitude"]))
        else:
            st.warning("Não há coordenadas suficientes para exibir no mapa.")
