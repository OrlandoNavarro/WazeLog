import streamlit as st
import pandas as pd
import requests
import openpyxl
from pedidos import obter_coordenadas
from database import salvar_cnpj_enderecos, carregar_cnpj_enderecos, limpar_cnpj_enderecos
import io

def extrair_nome_campo(campo, chave_nome='nome', chave_sigla='sigla'):
    if isinstance(campo, dict):
        if chave_nome in campo:
            return campo[chave_nome]
        if chave_sigla in campo:
            return campo[chave_sigla]
        return str(campo)
    return str(campo)

def buscar_endereco_cnpj(cnpj):
    url1 = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    url2 = f"https://publica.cnpj.ws/cnpj/{cnpj}"
    url3 = f"https://www.receitaws.com.br/v1/cnpj/{cnpj}"
    url4 = f"https://api-publica.simplesreceita.com.br/api/v1/empresa/{cnpj}"
    # 1. BrasilAPI
    try:
        resp = requests.get(url1, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            municipio = extrair_nome_campo(data.get('municipio', ''))
            uf = extrair_nome_campo(data.get('uf', ''), chave_nome='sigla', chave_sigla='sigla')
            endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}, {data.get('bairro', '')}, {municipio}, {uf}"
            situacao = data.get('situacao_cadastral', '') or data.get('situacao', '')
            if endereco.strip(", "):
                return endereco, situacao
    except Exception:
        pass
    # 2. CNPJ.ws
    try:
        resp = requests.get(url2, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            est = data.get('estabelecimento', {})
            cidade = extrair_nome_campo(est.get('cidade', ''))
            estado = extrair_nome_campo(est.get('estado', ''), chave_nome='sigla', chave_sigla='sigla')
            endereco = f"{est.get('logradouro', '')}, {est.get('numero', '')}, {est.get('bairro', '')}, {cidade}, {estado}"
            situacao = est.get('situacao_cadastral', '') or est.get('situacao', '')
            if endereco.strip(", "):
                return endereco, situacao
    except Exception:
        pass
    # 3. ReceitaWS
    try:
        resp = requests.get(url3, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            municipio = extrair_nome_campo(data.get('municipio', ''))
            uf = extrair_nome_campo(data.get('uf', ''), chave_nome='sigla', chave_sigla='sigla')
            endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}, {data.get('bairro', '')}, {municipio}, {uf}"
            situacao = data.get('situacao', '')
            if endereco.strip(", "):
                return endereco, situacao
    except Exception:
        pass
    # 4. SimplesReceita
    try:
        resp = requests.get(url4, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            municipio = extrair_nome_campo(data.get('municipio', ''))
            uf = extrair_nome_campo(data.get('uf', ''), chave_nome='sigla', chave_sigla='sigla')
            endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}, {data.get('bairro', '')}, {municipio}, {uf}"
            situacao = data.get('situacao_cadastral', '') or data.get('situacao', '')
            if endereco.strip(", "):
                return endereco, situacao
    except Exception:
        pass
    return None, None

def google_maps_link(endereco):
    from urllib.parse import quote_plus
    if endereco is None:
        endereco = ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(str(endereco))}"

# Para obter coordenadas, continue usando a função obter_coordenadas(endereco) ou outra API de geocodificação.
# O link do Google Maps não retorna latitude/longitude diretamente.

def buscar_cnpj_no_banco(cnpj):
    df = carregar_cnpj_enderecos()
    if "CNPJ" not in df.columns:
        for col in df.columns:
            if col.lower() == "cnpj":
                df = df.rename(columns={col: "CNPJ"})
    row = df[df["CNPJ"].astype(str) == str(cnpj)]
    if not row.empty:
        return row.iloc[0]
    return None

def situacao_cadastral_str(situacao):
    mapa = {
        "1": "NULA",
        "2": "ATIVA",
        "3": "SUSPENSA",
        "4": "INAPTA",
        "8": "BAIXADA",
        1: "NULA",
        2: "ATIVA",
        3: "SUSPENSA",
        4: "INAPTA",
        8: "BAIXADA",
        None: "Desconhecida",
        "": "Desconhecida",
        "erro": "Erro",
        "error": "Erro"
    }
    if isinstance(situacao, (int, float)):
        situacao = int(situacao)
    s = str(situacao).strip().lower() if situacao is not None else ""
    if s in mapa:
        return mapa[s]
    if s.isdigit() and int(s) in mapa:
        return mapa[int(s)]
    if s in ["erro", "error"]:
        return "Erro"
    if not s or s in ["none", "nan"]:
        return "Desconhecida"
    return s.upper()

def show():
    # <<< ADICIONADO: Inicializa estado de processamento >>>
    if 'processing_cnpj' not in st.session_state:
        st.session_state.processing_cnpj = False

    st.header("🔎 Busca de CNPJ", divider="rainbow")
    st.markdown("""
    <style>
    .stButton>button {font-weight:bold;}
    .stDownloadButton>button {font-weight:bold;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='background-color:#fff3cd;padding:12px;border-radius:8px;border:1px solid #ffeeba;margin-bottom:18px;'>
    ⚠️ <b>Aviso importante sobre zeros à esquerda no CNPJ:</b><br>
    Ao abrir a planilha no Excel, use o assistente de importação e defina a coluna CNPJ como <b>Texto</b> para garantir que os zeros à esquerda sejam preservados.<br>
    Se abrir diretamente, o Excel pode remover os zeros iniciais automaticamente.
    </div>
    """, unsafe_allow_html=True)

    # --- Busca em lote ---
    with st.container():
        st.subheader("📑 Busca em Lote de CNPJs")
        st.write("Faça upload de uma planilha com CNPJs. O sistema irá buscar o endereço e as coordenadas de cada um.")
        arquivo = st.file_uploader("Upload da planilha de CNPJs", type=["xlsx", "xls", "csv"], key="upload_lote")
        if st.button("🔍 Buscar em lote") and arquivo:
            if arquivo.name.endswith(".csv"):
                df = pd.read_csv(arquivo, dtype=str, keep_default_na=False)
            else:
                df = pd.read_excel(arquivo, dtype=str)
            if "CNPJ" in df.columns:
                df["CNPJ"] = df["CNPJ"].astype(str).str.replace(r'\D', '', regex=True).str.zfill(14)
            st.info(f"Total de CNPJs: {len(df)}")
            resultados = []
            latitudes = []
            longitudes = []
            enderecos = []
            links = []
            situacoes = []
            progress = st.progress(0)
            for idx, row in df.iterrows():
                cnpj = str(row.get("CNPJ", "")).replace(".", "").replace("/", "").replace("-", "")
                row_banco = buscar_cnpj_no_banco(cnpj)
                if row_banco is not None and pd.notnull(row_banco.get("Endereco")) and row_banco.get("Endereco") != "Não encontrado":
                    endereco = row_banco.get("Endereco")
                    lat = row_banco.get("Latitude")
                    lon = row_banco.get("Longitude")
                    situacao = row_banco.get("Status", "")
                else:
                    endereco, situacao = buscar_endereco_cnpj(cnpj)
                    if endereco:
                        lat, lon = obter_coordenadas(endereco)
                    else:
                        lat, lon = None, None
                enderecos.append(endereco or "Não encontrado")
                situacoes.append(situacao_cadastral_str(situacao))
                links.append(google_maps_link(endereco) if endereco else "")
                latitudes.append(lat)
                longitudes.append(lon)
                progress.progress((idx+1)/len(df), text=f"Processando {idx+1}/{len(df)}")
            progress.empty()
            df_result = df.copy()
            df_result["Endereço"] = enderecos
            df_result["Situação Cadastral"] = situacoes
            df_result["Google Maps"] = links
            df_result["Latitude"] = latitudes
            df_result["Longitude"] = longitudes
            # Garante ordem das colunas
            colunas = [
                "CNPJ", "Situação Cadastral", "Endereço", "Google Maps", "Latitude", "Longitude"
            ]
            outras_colunas = [c for c in df_result.columns if c not in colunas]
            df_result = df_result[colunas + outras_colunas]
            df_result = df_result.rename(columns={
                "Endereço": "Endereco",
                "Situação Cadastral": "Status"
            })
            # Remove colunas duplicadas mantendo só a primeira ocorrência
            df_result = df_result.loc[:, ~df_result.columns.duplicated()]
            st.success("Processamento concluído!")
            st.dataframe(df_result, use_container_width=True)
            salvar_cnpj_enderecos(df_result)
            # Exibir todos os pontos no mapa se houver coordenadas
            df_map = df_result.dropna(subset=["Latitude", "Longitude"]).copy()
            df_map["Latitude"] = pd.to_numeric(df_map["Latitude"], errors="coerce")
            df_map["Longitude"] = pd.to_numeric(df_map["Longitude"], errors="coerce")
            df_map = df_map.dropna(subset=["Latitude", "Longitude"])
            if not df_map.empty:
                st.map(df_map.rename(columns={"Latitude": "latitude", "Longitude": "longitude"}))
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_result.to_excel(writer, index=False)
                ws = writer.sheets['Sheet1']
                # Força a coluna CNPJ como texto (assume que CNPJ é a primeira coluna)
                for cell in ws[ws.min_column]:
                    if cell.row == 1:
                        continue  # pula o cabeçalho
                    cell.number_format = '@'
            output.seek(0)
            st.download_button(
                label="Baixar resultado em Excel",
                data=output.getvalue(),
                file_name="cnpjs_com_endereco_coordenadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            # Novo: Selecionar CNPJ para visualizar detalhes
            cnpjs_disponiveis = df_result["CNPJ"].dropna().astype(str).unique().tolist()
            if cnpjs_disponiveis:
                cnpj_sel = st.selectbox("Selecione um CNPJ para ver detalhes", cnpjs_disponiveis)
                row = df_result[df_result["CNPJ"].astype(str) == cnpj_sel].iloc[0]
                endereco = row.get("Endereço", "")
                lat = row.get("Latitude", None)
                lon = row.get("Longitude", None)
                link = google_maps_link(endereco) if endereco else ""
                st.markdown(f"<b>Endereço:</b> {endereco}", unsafe_allow_html=True)
                st.markdown(f"<b>Google Maps:</b> <a href='{link}' target='_blank'>{link}</a>", unsafe_allow_html=True)
                if pd.notnull(lat) and pd.notnull(lon):
                    st.info(f"Coordenadas: {lat}, {lon}")
                    df_temp = pd.DataFrame({"latitude": [lat], "longitude": [lon]})
                    df_temp = df_temp.dropna(subset=["latitude", "longitude"])
                    df_temp["latitude"] = pd.to_numeric(df_temp["latitude"], errors="coerce")
                    df_temp["longitude"] = pd.to_numeric(df_temp["longitude"], errors="coerce")
                    if not df_temp.empty:
                        st.map(df_temp)
                else:
                    st.warning("Coordenadas não encontradas para este endereço.")

    # --- Edição dos dados salvos ---
    st.divider()
    with st.container():
        st.subheader("📝 Editar CNPJs salvos no banco de dados")
        df_cnpj = carregar_cnpj_enderecos()
        # Padronizar nomes de colunas e garantir todas as colunas relevantes
        colunas_padrao = [
            'CNPJ', 'Status', 'Cód. Edata', 'Cód. Mega', 'Nome',
            'Endereco', 'Latitude', 'Longitude', 'Google Maps'
        ]
        if not df_cnpj.empty:
            # Renomear variações para padrão
            col_renomear = {}
            for col in df_cnpj.columns:
                if col.lower() == 'cnpj' and col != 'CNPJ':
                    col_renomear[col] = 'CNPJ'
                if col.lower() == 'status' and col != 'Status':
                    col_renomear[col] = 'Status'
                if col.lower() in ['cód. edata', 'cod_edata', 'cod. edata'] and col != 'Cód. Edata':
                    col_renomear[col] = 'Cód. Edata'
                if col.lower() in ['cód. mega', 'cod_mega', 'cod. mega'] and col != 'Cód. Mega':
                    col_renomear[col] = 'Cód. Mega'
                if col.lower() == 'nome' and col != 'Nome':
                    col_renomear[col] = 'Nome'
                if col.lower() == 'endereco' and col != 'Endereco':
                    col_renomear[col] = 'Endereco'
                if col.lower() == 'latitude' and col != 'Latitude':
                    col_renomear[col] = 'Latitude'
                if col.lower() == 'longitude' and col != 'Longitude':
                    col_renomear[col] = 'Longitude'
                if col.lower() in ['google maps', 'googlemaps', 'maps'] and col != 'Google Maps':
                    col_renomear[col] = 'Google Maps'
            if col_renomear:
                df_cnpj = df_cnpj.rename(columns=col_renomear)
            # Remover colunas duplicadas (mantém só a primeira ocorrência)
            df_cnpj = df_cnpj.loc[:, ~df_cnpj.columns.duplicated()]
            # Garantir todas as colunas padrão
            for col in colunas_padrao:
                if col not in df_cnpj.columns:
                    df_cnpj[col] = ''
            # Reordenar colunas
            df_cnpj = df_cnpj[[col for col in colunas_padrao if col in df_cnpj.columns]]
        if not df_cnpj.empty:
            # Filtros e ordenação igual pedidos
            colunas_ordenaveis = [col for col in df_cnpj.columns if col not in ["Sel."]]
            coluna_ordem = st.selectbox("Ordenar por", colunas_ordenaveis, index=0, key="ordem_cnpj")
            if coluna_ordem in df_cnpj.columns:
                df_cnpj = df_cnpj.sort_values(by=coluna_ordem, key=lambda x: x.astype(str)).reset_index(drop=True)
            status_filtro = st.selectbox("Status de coordenadas", ["Todos", "Com coordenadas", "Sem coordenadas"], key="status_coord_cnpj")
            df_filtrado = df_cnpj.copy()
            if status_filtro == "Com coordenadas":
                df_filtrado = df_filtrado[df_filtrado['Latitude'].notnull() & df_filtrado['Longitude'].notnull()]
            elif status_filtro == "Sem coordenadas":
                df_filtrado = df_filtrado[df_filtrado['Latitude'].isnull() | df_filtrado['Longitude'].isnull()]
            filtro = st.text_input("Buscar CNPJ (qualquer campo)", key="busca_cnpj")
            if filtro:
                filtro_lower = filtro.lower()
                df_filtrado = df_filtrado[df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(filtro_lower).any(), axis=1)]
            st.write("Você pode filtrar, editar e exportar os dados dos CNPJs salvos:")
            df_editado = st.data_editor(
                df_filtrado,
                num_rows="dynamic",
                use_container_width=True,
                key="cnpj_editor",
                column_order=df_cnpj.columns.tolist(),
                hide_index=True
            )
            if not df_editado.equals(df_filtrado):
                # Atualiza o DataFrame original com as edições feitas no filtrado
                df_update = df_cnpj.copy()
                df_update.update(df_editado)
                salvar_cnpj_enderecos(df_update)
                st.success("Alterações salvas no banco de dados!")
        else:
            st.info("Nenhum CNPJ salvo no banco de dados ainda.")
        if st.button("Limpar dados salvos"):
            limpar_cnpj_enderecos()
            st.success("Dados salvos foram limpos com sucesso!")
        # Botão para buscar endereço Google Maps e coordenadas dos que não têm endereço OU estão como 'CNPJ ...'
        if not df_cnpj.empty:
            mask_nao_encontrado = (
                df_cnpj["Endereco"].isnull() |
                (df_cnpj["Endereco"] == "") |
                (df_cnpj["Endereco"] == "Não encontrado") |
                df_cnpj["Endereco"].astype(str).str.startswith('CNPJ')
            )
            df_nao_encontrado = df_cnpj[mask_nao_encontrado].copy()
            total = len(df_nao_encontrado)
            if st.button("Buscar Endereço Google Maps e Coordenadas para não localizados", key="btn_gmaps_coord"):
                if total == 0:
                    st.info("Todos os CNPJs já possuem endereço.")
                else:
                    progress = st.progress(0, text="Buscando endereços e coordenadas...")
                    for idx, (i, row) in enumerate(df_nao_encontrado.iterrows()):
                        cnpj = str(row.get("CNPJ", "")).replace(".", "").replace("/", "").replace("-", "")
                        endereco, situacao = buscar_endereco_cnpj(cnpj)
                        if not endereco:
                            endereco = f"CNPJ {cnpj}"  # fallback
                        link = google_maps_link(endereco)
                        lat, lon = obter_coordenadas(endereco)
                        df_cnpj.at[i, "Endereco"] = endereco
                        df_cnpj.at[i, "Status"] = situacao_cadastral_str(situacao)
                        df_cnpj.at[i, "Google Maps"] = link
                        df_cnpj.at[i, "Latitude"] = lat
                        df_cnpj.at[i, "Longitude"] = lon
                        progress.progress((idx+1)/total, text=f"Processando {idx+1}/{total}")
                    progress.empty()
                    salvar_cnpj_enderecos(df_cnpj)
                    st.success("Endereços e coordenadas buscados para os não localizados!")
                    st.rerun()
        # Botão para buscar apenas coordenadas para endereços já localizados e sem coordenadas
        if not df_cnpj.empty:
            if st.button("Buscar Coordenadas para Endereços já Localizados", key="btn_coord_only"):
                mask_sem_coord = (
                    df_cnpj["Endereco"].notnull() &
                    (df_cnpj["Endereco"] != "") &
                    (df_cnpj["Endereco"] != "Não encontrado") &
                    (df_cnpj["Latitude"].isnull() | df_cnpj["Longitude"].isnull())
                )
                df_sem_coord = df_cnpj[mask_sem_coord].copy()
                total = len(df_sem_coord)
                if total == 0:
                    st.info("Todos os endereços já possuem coordenadas.")
                else:
                    progress = st.progress(0, text="Buscando coordenadas...")
                    for idx, (i, row) in enumerate(df_sem_coord.iterrows()):
                        endereco = row.get("Endereco", "")
                        lat, lon = obter_coordenadas(endereco)
                        df_cnpj.at[i, "Latitude"] = lat
                        df_cnpj.at[i, "Longitude"] = lon
                        progress.progress((idx+1)/total, text=f"Processando {idx+1}/{total}")
                    progress.empty()
                    salvar_cnpj_enderecos(df_cnpj)
                    st.success("Coordenadas buscadas para todos os endereços já localizados!")
                    st.rerun()
        # Botão para reprocessar endereços que estão como 'CNPJ ...' (endereços não encontrados)
        if not df_cnpj.empty:
            mask_cnpj_falso = df_cnpj['Endereco'].astype(str).str.startswith('CNPJ')
            if mask_cnpj_falso.any():
                if st.button("Reprocessar endereços não encontrados (CNPJ ...)", key="btn_reprocessar_cnpj_falso"):
                    total = mask_cnpj_falso.sum()
                    progress = st.progress(0, text="Reprocessando endereços...")
                    for idx, (i, row) in enumerate(df_cnpj[mask_cnpj_falso].iterrows()):
                        cnpj = str(row.get("CNPJ", "")).replace(".", "").replace("/", "").replace("-", "")
                        endereco, situacao = buscar_endereco_cnpj(cnpj)
                        if not endereco:
                            endereco = f"CNPJ {cnpj}"  # fallback
                        link = google_maps_link(endereco)
                        lat, lon = obter_coordenadas(endereco)
                        df_cnpj.at[i, "Endereco"] = endereco
                        df_cnpj.at[i, "Status"] = situacao_cadastral_str(situacao)
                        df_cnpj.at[i, "Google Maps"] = link
                        df_cnpj.at[i, "Latitude"] = lat
                        df_cnpj.at[i, "Longitude"] = lon
                        progress.progress((idx+1)/total, text=f"Processando {idx+1}/{total}")
                    progress.empty()
                    salvar_cnpj_enderecos(df_cnpj)
                    st.success("Reprocessamento concluído!")
                    st.rerun()
        # Botão para limpar endereços e coordenadas que estão como (None, None)
        if not df_cnpj.empty:
            mask_none_tuple = df_cnpj['Endereco'].astype(str).isin([
                '(None, None)', 'None, None', "('None', 'None')", 'None', "(None,None)", "('None',None)", "(None,'None')"
            ])
            if mask_none_tuple.any():
                if st.button("Limpar endereços e coordenadas (None, None)", key="btn_limpar_none_tuple"):
                    for i in df_cnpj[mask_none_tuple].index:
                        df_cnpj.at[i, "Endereco"] = ""
                        df_cnpj.at[i, "Latitude"] = ""
                        df_cnpj.at[i, "Longitude"] = ""
                        df_cnpj.at[i, "Google Maps"] = ""
                    salvar_cnpj_enderecos(df_cnpj)
                    st.success("Endereços e coordenadas (None, None) limpos!")
                    st.rerun()

    # --- Busca individual ---
    st.divider()
    with st.container():
        st.subheader("🔎 Busca Individual de CNPJ")
        st.write("Digite um CNPJ para buscar o endereço e as coordenadas.")
        cnpj = st.text_input("CNPJ", max_chars=18, help="Apenas números, pontos, barras e traços serão ignorados.")
        col1, col2 = st.columns([1, 5])
        with col1:
            buscar = st.button("Buscar", key="buscar_individual")
        if buscar and cnpj:
            cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
            # Buscar no banco antes
            row_banco = buscar_cnpj_no_banco(cnpj_limpo)
            if row_banco is not None and pd.notnull(row_banco.get("Endereco")) and row_banco.get("Endereco") != "Não encontrado":
                endereco = row_banco.get("Endereco")
                lat = row_banco.get("Latitude")
                lon = row_banco.get("Longitude")
                situacao = row_banco.get("Status", "")
            else:
                with st.spinner("Buscando endereço..."):
                    endereco, situacao = buscar_endereco_cnpj(cnpj_limpo)
                if endereco:
                    with st.spinner("Buscando coordenadas..."):
                        lat, lon = obter_coordenadas(endereco)
                else:
                    lat, lon = None, None
            # Não salva no banco para buscas individuais
            if endereco:
                link = google_maps_link(endereco)
                st.markdown(f"✅ <b>Endereço encontrado:</b> <a href='{link}' target='_blank'>{endereco}</a>", unsafe_allow_html=True)
                st.markdown(f"<b>Situação Cadastral:</b> <span style='color:#1976d2;font-weight:bold'>{situacao_cadastral_str(situacao)}</span>", unsafe_allow_html=True)
                if pd.notnull(lat) and pd.notnull(lon):
                    st.info(f"Coordenadas: {lat}, {lon}")
                    df_temp = pd.DataFrame({"latitude": [lat], "longitude": [lon]})
                    df_temp = df_temp.dropna(subset=["latitude", "longitude"])
                    df_temp["latitude"] = pd.to_numeric(df_temp["latitude"], errors="coerce")
                    df_temp["longitude"] = pd.to_numeric(df_temp["longitude"], errors="coerce")
                    if not df_temp.empty:
                        st.map(df_temp)
                else:
                    st.warning("Coordenadas não encontradas para este endereço.")
            else:
                st.error("Endereço não encontrado para este CNPJ.")