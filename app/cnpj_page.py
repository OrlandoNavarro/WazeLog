import streamlit as st
import pandas as pd
import requests
from pedidos import obter_coordenadas
from database import salvar_cnpj_enderecos, carregar_cnpj_enderecos, limpar_cnpj_enderecos
import io
import time

def buscar_endereco_cnpj(cnpj):
    url1 = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    url2 = f"https://publica.cnpj.ws/cnpj/{cnpj}"
    # Primeira tentativa: BrasilAPI
    try:
        resp = requests.get(url1, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            endereco = f"{data.get('logradouro', '')}, {data.get('numero', '')}, {data.get('bairro', '')}, {data.get('municipio', '')}, {data.get('uf', '')}"
            if endereco.strip(", "):
                return endereco
    except Exception:
        pass
    # Segunda tentativa: CNPJ.ws
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
    return None

def google_maps_link(endereco):
    from urllib.parse import quote_plus
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(endereco)}"

def show():
    st.header("Busca CNPJ", divider="rainbow")
    aba = st.tabs(["Buscar individual", "Buscar em lote"])
    with aba[0]:
        st.write("Digite um CNPJ para buscar o endereço e as coordenadas.")
        cnpj = st.text_input("CNPJ", max_chars=18, help="Apenas números, pontos, barras e traços serão ignorados.")
        if st.button("Buscar", key="buscar_individual") and cnpj:
            cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
            with st.spinner("Buscando endereço..."):
                endereco = buscar_endereco_cnpj(cnpj_limpo)
            if endereco:
                link = google_maps_link(endereco)
                st.markdown(f"✅ <b>Endereço encontrado:</b> <a href='{link}' target='_blank'>{endereco}</a>", unsafe_allow_html=True)
                with st.spinner("Buscando coordenadas..."):
                    lat, lon = obter_coordenadas(endereco)
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
                endereco = buscar_endereco_cnpj(cnpj)
                # Delay para evitar bloqueio das APIs
                time.sleep(1)
                enderecos.append(endereco or "Não encontrado")
                links.append(google_maps_link(endereco) if endereco else "")
                lat, lon = (None, None)
                if endereco:
                    lat, lon = obter_coordenadas(endereco)
                latitudes.append(lat)
                longitudes.append(lon)
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
        if not df_salvo.empty:
            st.dataframe(df_salvo, use_container_width=True)
            # Botão para tentar buscar endereços não encontrados
            if "Endereco" in df_salvo.columns:
                if st.button("Buscar endereços não localizados novamente"):
                    mask_nao_encontrado = (df_salvo["Endereco"].isnull()) | (df_salvo["Endereco"] == "Não encontrado")
                    df_nao_encontrado = df_salvo[mask_nao_encontrado].copy()
                    if not df_nao_encontrado.empty:
                        for idx, row in df_nao_encontrado.iterrows():
                            cnpj = str(row.get("CNPJ", "")).replace(".", "").replace("/", "").replace("-", "")
                            endereco = buscar_endereco_cnpj(cnpj)
                            lat, lon = (None, None)
                            if endereco:
                                lat, lon = obter_coordenadas(endereco)
                            df_salvo.at[idx, "Endereco"] = endereco or "Não encontrado"
                            df_salvo.at[idx, "Google Maps"] = google_maps_link(endereco) if endereco else ""
                            df_salvo.at[idx, "Latitude"] = lat
                            df_salvo.at[idx, "Longitude"] = lon
                        salvar_cnpj_enderecos(df_salvo)
                        st.success("Busca concluída! Dados atualizados.")
                        st.rerun()
                    else:
                        st.info("Todos os CNPJs já possuem endereço.")
                # Novo botão para buscar coordenadas apenas
                if st.button("Buscar coordenadas para endereços já localizados"):
                    mask_sem_coord = (
                        df_salvo["Endereco"].notnull() &
                        (df_salvo["Endereco"] != "Não encontrado") &
                        (df_salvo["Latitude"].isnull() | df_salvo["Longitude"].isnull())
                    )
                    df_sem_coord = df_salvo[mask_sem_coord].copy()
                    if not df_sem_coord.empty:
                        for idx, row in df_sem_coord.iterrows():
                            endereco = row.get("Endereco", "")
                            lat, lon = obter_coordenadas(endereco)
                            df_salvo.at[idx, "Latitude"] = lat
                            df_salvo.at[idx, "Longitude"] = lon
                        salvar_cnpj_enderecos(df_salvo)
                        st.success("Coordenadas buscadas e atualizadas!")
                        st.rerun()
                    else:
                        st.info("Todos os endereços já possuem coordenadas.")
            else:
                st.warning("Atenção: Os dados salvos não possuem a coluna 'Endereco'. Faça uma nova busca em lote para atualizar os dados.")
