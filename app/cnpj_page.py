import streamlit as st
import pandas as pd
import requests
from pedidos import obter_coordenadas
from database import salvar_cnpj_enderecos, carregar_cnpj_enderecos, limpar_cnpj_enderecos
import io

def buscar_endereco_cnpj(cnpj):
    url1 = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    url2 = f"https://publica.cnpj.ws/cnpj/{cnpj}"
    url3 = f"https://www.receitaws.com.br/v1/cnpj/{cnpj}"
    url4 = f"https://api-publica.simplesreceita.com.br/api/v1/empresa/{cnpj}"
    # url5 = f"https://www.cnpjaberto.com/api/v1/empresa?cnpj={cnpj}"  # Requer token
    # 1. BrasilAPI
    try:
        resp = requests.get(url1, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}, {data.get('bairro', '')}, {data.get('municipio', '')}, {data.get('uf', '')}"
            if endereco.strip(", "):
                return endereco
    except Exception:
        pass
    # 2. CNPJ.ws
    try:
        resp = requests.get(url2, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            est = data.get('estabelecimento', {})
            endereco = f"{est.get('logradouro', '')}, {est.get('numero', '')}, {est.get('bairro', '')}, {est.get('cidade', '')}, {est.get('estado', '')}"
            if endereco.strip(", "):
                return endereco
    except Exception:
        pass
    # 3. ReceitaWS
    try:
        resp = requests.get(url3, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}, {data.get('bairro', '')}, {data.get('municipio', '')}, {data.get('uf', '')}"
            if endereco.strip(", "):
                return endereco
    except Exception:
        pass
    # 4. SimplesReceita
    try:
        resp = requests.get(url4, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}, {data.get('bairro', '')}, {data.get('municipio', '')}, {data.get('uf', '')}"
            if endereco.strip(", "):
                return endereco
    except Exception:
        pass
    # 5. CNPJ Aberto (exemplo, requer token)
    # try:
    #     headers = {"Authorization": "Token SEU_TOKEN_AQUI"}
    #     resp = requests.get(url5, headers=headers, timeout=10)
    #     if resp.status_code == 200:
    #         data = resp.json()
    #         if data and isinstance(data, list) and len(data) > 0:
    #             empresa = data[0]
    #             endereco = f"{empresa.get('logradouro', '')}, {empresa.get('numero', '')}, {empresa.get('bairro', '')}, {empresa.get('municipio', '')}, {empresa.get('uf', '')}"
    #             if endereco.strip(", "):
    #                 return endereco
    # except Exception:
    #     pass
    return None

def google_maps_link(endereco):
    from urllib.parse import quote_plus
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(endereco)}"

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

def show():
    st.header("Busca CNPJ", divider="rainbow")
    aba = st.tabs(["Buscar individual", "Buscar em lote"])
    with aba[0]:
        st.write("Digite um CNPJ para buscar o endereço e as coordenadas.")
        cnpj = st.text_input("CNPJ", max_chars=18, help="Apenas números, pontos, barras e traços serão ignorados.")
        if st.button("Buscar", key="buscar_individual") and cnpj:
            cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
            # Buscar no banco antes
            row_banco = buscar_cnpj_no_banco(cnpj_limpo)
            if row_banco is not None and pd.notnull(row_banco.get("Endereco")) and row_banco.get("Endereco") != "Não encontrado":
                endereco = row_banco.get("Endereco")
                lat = row_banco.get("Latitude")
                lon = row_banco.get("Longitude")
            else:
                with st.spinner("Buscando endereço..."):
                    endereco = buscar_endereco_cnpj(cnpj_limpo)
                if endereco:
                    with st.spinner("Buscando coordenadas..."):
                        lat, lon = obter_coordenadas(endereco)
                else:
                    lat, lon = None, None
                # Salvar no banco
                df_salvar = pd.DataFrame([{ "CNPJ": cnpj_limpo, "Endereco": endereco or "Não encontrado", "Latitude": lat, "Longitude": lon }])
                salvar_cnpj_enderecos(df_salvar)
            if endereco:
                link = google_maps_link(endereco)
                st.markdown(f"✅ <b>Endereço encontrado:</b> <a href='{link}' target='_blank'>{endereco}</a>", unsafe_allow_html=True)
                if lat and lon:
                    st.info(f"Coordenadas: {lat}, {lon}")
                    st.map({"latitude": [lat], "longitude": [lon]})
                else:
                    st.warning("Coordenadas não encontradas para este endereço.")
            else:
                st.error("Endereço não encontrado para este CNPJ.")
    with aba[1]:
        st.write("Faça upload de uma planilha com CNPJs. O sistema irá buscar o endereço e as coordenadas de cada um.")
        arquivo = st.file_uploader("Upload da planilha de CNPJs", type=["xlsx", "xls", "csv"], key="upload_lote")
        if st.button("Buscar em lote") and arquivo:
            if arquivo.name.endswith(".csv"):
                df = pd.read_csv(arquivo)
            else:
                df = pd.read_excel(arquivo)
            st.info(f"Total de CNPJs: {len(df)}")
            resultados = []
            latitudes = []
            longitudes = []
            enderecos = []
            links = []
            progress = st.progress(0)
            for idx, row in df.iterrows():
                cnpj = str(row.get("CNPJ", "")).replace(".", "").replace("/", "").replace("-", "")
                row_banco = buscar_cnpj_no_banco(cnpj)
                if row_banco is not None and pd.notnull(row_banco.get("Endereco")) and row_banco.get("Endereco") != "Não encontrado":
                    endereco = row_banco.get("Endereco")
                    lat = row_banco.get("Latitude")
                    lon = row_banco.get("Longitude")
                else:
                    endereco = buscar_endereco_cnpj(cnpj)
                    if endereco:
                        lat, lon = obter_coordenadas(endereco)
                    else:
                        lat, lon = None, None
                enderecos.append(endereco or "Não encontrado")
                links.append(google_maps_link(endereco) if endereco else "")
                latitudes.append(lat)
                longitudes.append(lon)
                # Salvar no banco cada resultado
                df_salvar = pd.DataFrame([{ "CNPJ": cnpj, "Endereco": endereco or "Não encontrado", "Latitude": lat, "Longitude": lon }])
                salvar_cnpj_enderecos(df_salvar)
                progress.progress((idx+1)/len(df), text=f"Processando {idx+1}/{len(df)}")
            progress.empty()
            df_result = df.copy()
            df_result["Endereço"] = enderecos
            df_result["Google Maps"] = links
            df_result["Latitude"] = latitudes
            df_result["Longitude"] = longitudes
            st.success("Processamento concluído!")
            st.dataframe(df_result, use_container_width=True)
            # Exibir todos os pontos no mapa se houver coordenadas
            df_map = df_result.dropna(subset=["Latitude", "Longitude"])
            if not df_map.empty:
                st.map(df_map.rename(columns={"Latitude": "latitude", "Longitude": "longitude"}))
            output = io.BytesIO()
            df_result.to_excel(output, index=False, engine='openpyxl')
            st.download_button(
                label="Baixar resultado em Excel",
                data=output.getvalue(),
                file_name="cnpjs_com_endereco_coordenadas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            # Salvar no banco de dados
            salvar_cnpj_enderecos(df_result)
        # Exibir dados salvos
        st.divider()
        st.subheader("Dados salvos no banco de dados")
        df_salvo = carregar_cnpj_enderecos()
        # Padronizar nome da coluna para 'Endereco' se existir variações
        for col in df_salvo.columns:
            if col.lower() == "endereco" and col != "Endereco":
                df_salvo = df_salvo.rename(columns={col: "Endereco"})
        # Garantir que as colunas Latitude e Longitude existam
        if "Latitude" not in df_salvo.columns:
            df_salvo["Latitude"] = None
        if "Longitude" not in df_salvo.columns:
            df_salvo["Longitude"] = None
        if not df_salvo.empty:
            # Botão para rebuscar endereço apenas para linhas sem endereço
            if st.button("Rebuscar Endereço pelo CNPJ"):
                mask_nao_encontrado = df_salvo["Endereco"].isnull() | (df_salvo["Endereco"] == "") | (df_salvo["Endereco"] == "Não encontrado")
                if mask_nao_encontrado.any():
                    for idx, row in df_salvo[mask_nao_encontrado].iterrows():
                        cnpj = str(row.get("CNPJ", "")).replace(".", "").replace("/", "").replace("-", "")
                        endereco = buscar_endereco_cnpj(cnpj)
                        df_salvo.at[idx, "Endereco"] = endereco or "Não encontrado"
                    salvar_cnpj_enderecos(df_salvo)
                    st.success("Endereços atualizados!")
                    st.rerun()
                else:
                    st.info("Todos os CNPJs já possuem endereço.")
            # Botão para buscar coordenadas apenas para linhas sem coordenadas e com endereço válido
            if st.button("Buscar Coordenadas para Endereços já Localizados"):
                mask_sem_coord = (
                    df_salvo["Endereco"].notnull() &
                    (df_salvo["Endereco"] != "") &
                    (df_salvo["Endereco"] != "Não encontrado") &
                    (df_salvo["Latitude"].isnull() | df_salvo["Longitude"].isnull())
                )
                if mask_sem_coord.any():
                    for idx, row in df_salvo[mask_sem_coord].iterrows():
                        endereco = row.get("Endereco", "")
                        lat, lon = obter_coordenadas(endereco)
                        df_salvo.at[idx, "Latitude"] = lat
                        df_salvo.at[idx, "Longitude"] = lon
                    salvar_cnpj_enderecos(df_salvo)
                    st.success("Coordenadas atualizadas!")
                    st.rerun()
                else:
                    st.info("Todos os endereços já possuem coordenadas.")
        else:
            st.warning("Atenção: Os dados salvos não possuem a coluna 'Endereco'. Faça uma nova busca em lote para atualizar os dados.")
        if st.button("Limpar dados salvos"):
            limpar_cnpj_enderecos()
            st.success("Dados salvos foram limpos com sucesso!")