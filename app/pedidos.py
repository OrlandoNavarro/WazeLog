import pandas as pd
import requests
import os
import sqlite3
import itertools
import streamlit as st
import threading
import time

OPENCAGE_KEYS = [
    "5161dbd006cf4c43a7f7dd789ee1a3da",
    "6f522c67add14152926990afbe127384",
    "6c2d02cafb2e4b49aa3485a62262e54b"
]
key_cycle = itertools.cycle(OPENCAGE_KEYS)

def definir_regiao(row):
    cidade = str(row.get("Cidade de Entrega", "")).strip()
    bairro = str(row.get("Bairro de Entrega", "")).strip()
    if cidade.lower() == "são paulo":
        return f"{cidade} - {bairro}" if bairro else cidade
    return cidade

def obter_coordenadas_opencage(endereco):
    key = next(key_cycle)
    url = f"https://api.opencagedata.com/geocode/v1/json?q={requests.utils.quote(str(endereco or ''))}&key={key}&language=pt&countrycode=br&limit=1"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results")
            if results:
                geometry = results[0]["geometry"]
                return geometry["lat"], geometry["lng"]
    except Exception:
        pass
    return None, None

def obter_coordenadas_nominatim(endereco):
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={requests.utils.quote(endereco)}&addressdetails=0&limit=1"
        headers = {"User-Agent": "roteirizador_entregas"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            results = resp.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None, None

def carregar_coordenadas_salvas():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'wazelog.db')
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql('SELECT endereco_completo, latitude, longitude FROM coordenadas', conn)
        return {row['endereco_completo']: (row['latitude'], row['longitude']) for _, row in df.iterrows()}
    except Exception:
        return {}
    finally:
        conn.close()

def buscar_coordenadas_no_dict(endereco, coord_dict):
    if endereco in coord_dict:
        lat, lon = coord_dict[endereco]
        if pd.notnull(lat) and pd.notnull(lon):
            return lat, lon
    return None, None

def obter_coordenadas(endereco):
    # Busca apenas em APIs externas, pois a busca no banco já é feita no fluxo principal
    lat, lon = obter_coordenadas_opencage(endereco)
    if lat is not None and lon is not None:
        try:
            from app.database import salvar_coordenada
            salvar_coordenada(endereco, lat, lon)
        except Exception:
            pass
        return lat, lon
    lat, lon = obter_coordenadas_nominatim(endereco)
    if lat is not None and lon is not None:
        try:
            from app.database import salvar_coordenada
            salvar_coordenada(endereco, lat, lon)
        except Exception:
            pass
    return lat, lon

def processar_pedidos(arquivo, max_linhas=None, tamanho_lote=20, delay_lote=5):
    nome = arquivo.name if hasattr(arquivo, 'name') else str(arquivo)
    ext = os.path.splitext(nome)[-1].lower()
    if ext in ['.xlsx', '.xlsm']:
        df = pd.read_excel(arquivo)
    elif ext == '.csv':
        # Tenta detectar o separador e encoding
        try:
            df = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8-sig') # Tenta UTF-8 com BOM
        except Exception:
            try:
                # Volta para o arquivo original se a primeira tentativa falhar
                if hasattr(arquivo, 'seek'):
                    arquivo.seek(0)
                df = pd.read_csv(arquivo, sep=None, engine='python') # Tenta detectar automaticamente
            except Exception as e:
                 raise ValueError(f"Erro ao ler CSV. Verifique o formato e encoding. Erro: {e}")
    elif ext == '.json':
        df = pd.read_json(arquivo)
    else:
        raise ValueError('Formato de arquivo não suportado.')

    # --- Lógica de Endereço Ajustada ---
    # Verifica se 'Endereço Completo' já existe
    if 'Endereço Completo' not in df.columns:
        # Se não existe, tenta criar a partir das outras colunas
        colunas_endereco_necessarias = ['Endereço de Entrega', 'Bairro de Entrega', 'Cidade de Entrega']
        colunas_faltantes = [col for col in colunas_endereco_necessarias if col not in df.columns]

        if not colunas_faltantes:
            st.info("Coluna 'Endereço Completo' não encontrada. Criando a partir de 'Endereço de Entrega', 'Bairro', 'Cidade'.")
            # Garante que as colunas são string antes de concatenar, tratando nulos
            df['Endereço Completo'] = df['Endereço de Entrega'].fillna('').astype(str) + ', ' + \
                                     df['Bairro de Entrega'].fillna('').astype(str) + ', ' + \
                                     df['Cidade de Entrega'].fillna('').astype(str)
            # Limpa espaços extras e vírgulas redundantes
            df['Endereço Completo'] = df['Endereço Completo'].str.replace(r'^,\s*|,?\s*,\s*$', '', regex=True).str.strip()
            df['Endereço Completo'] = df['Endereço Completo'].str.replace(r'\s*,\s*,', ',', regex=True) # Remove vírgulas duplas

            # Remover colunas originais APENAS se 'Endereço Completo' foi criado
            try:
                df = df.drop(colunas_endereco_necessarias, axis=1)
            except KeyError:
                 st.warning("Não foi possível remover colunas de endereço originais após criar 'Endereço Completo'.")
        else:
            # Se 'Endereço Completo' não existe E as colunas para criá-lo também não, levanta erro
            raise ValueError(f"Erro: Coluna 'Endereço Completo' não encontrada e colunas necessárias para criá-la ({', '.join(colunas_faltantes)}) também estão ausentes.")
    else:
        st.info("Coluna 'Endereço Completo' encontrada no arquivo. Usando-a diretamente.")
        # Garante que a coluna existente seja string
        df['Endereço Completo'] = df['Endereço Completo'].fillna('').astype(str)


    # --- Continua o processamento ---
    # Definir Região (Tenta usar Cidade/Bairro se existirem, senão usa uma lógica baseada no Endereço Completo se possível)
    if 'Cidade de Entrega' in df.columns and 'Bairro de Entrega' in df.columns:
         df['Região'] = df.apply(definir_regiao, axis=1) # Usa a função original
         # Remove colunas de cidade/bairro se ainda existirem (caso 'Endereço Completo' já existisse)
         try:
             df = df.drop(['Bairro de Entrega', 'Cidade de Entrega'], axis=1, errors='ignore')
         except KeyError:
             pass # Ignora se já foram removidas
    else:
         # Tenta extrair cidade do endereço completo (simplificado)
         try:
            df['Região'] = df['Endereço Completo'].str.split(',').str[-1].str.strip()
         except Exception:
            df['Região'] = 'N/A' # Fallback
         st.warning("Colunas 'Cidade de Entrega'/'Bairro de Entrega' não encontradas. 'Região' definida a partir do 'Endereço Completo' (pode ser impreciso).")


    # Limitar número de linhas para teste, se max_linhas for fornecido
    if max_linhas is not None:
        df = df.head(max_linhas)

    n = len(df)
    latitudes = [None] * n
    longitudes = [None] * n
    progress_bar = st.progress(0, text="Buscando coordenadas...")
    coord_dict = carregar_coordenadas_salvas()
    tempo_inicio = time.time()

    def buscar_coordenada_db(endereco):
        from app.database import buscar_coordenada
        return buscar_coordenada(endereco)
    def processar_linha(i, row):
        lat = row.get('Latitude') # Pega Latitude da linha (planilha)
        lon = row.get('Longitude') # Pega Longitude da linha (planilha)

        # Verifica se Latitude e Longitude da planilha são válidas
        if pd.notnull(lat) and pd.notnull(lon):
            # Se forem válidas, usa elas diretamente
            latitudes[i] = lat
            longitudes[i] = lon
        else:
            # SOMENTE SE NÃO forem válidas na planilha, busca no dict/db/api
            lat, lon = buscar_coordenadas_no_dict(row['Endereço Completo'], coord_dict)
            if lat is not None and lon is not None:
                latitudes[i] = lat
                longitudes[i] = lon
            else:
                lat, lon = buscar_coordenada_db(row['Endereço Completo'])
                if lat is not None and lon is not None:
                    latitudes[i] = lat
                    longitudes[i] = lon
                else:
                    lat, lon = obter_coordenadas(row['Endereço Completo'])
                    latitudes[i] = lat
                    longitudes[i] = lon
    # Processamento em lotes
    for inicio in range(0, n, tamanho_lote):
        fim = min(inicio + tamanho_lote, n)
        threads = []
        for i in range(inicio, fim):
            row = df.iloc[i]
            t = threading.Thread(target=processar_linha, args=(i, row))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        progresso = (fim) / n
        tempo_decorrido = time.time() - tempo_inicio
        tempo_estimado = tempo_decorrido / progresso if progresso > 0 else 0
        tempo_restante = tempo_estimado - tempo_decorrido
        progress_bar.progress(progresso, text=f"Buscando coordenadas... ({fim}/{n}) | Tempo restante: {int(tempo_restante)}s")
        if fim < n:
            time.sleep(delay_lote)
    df['Latitude'] = latitudes
    df['Longitude'] = longitudes
    progress_bar.empty()

    # Normalização e detecção de anomalias
    df = df.drop_duplicates()
    # Garante que 'Nº Pedido' exista antes de usar no dropna
    colunas_essenciais_dropna = ['Endereço Completo']
    if 'Nº Pedido' in df.columns:
        colunas_essenciais_dropna.append('Nº Pedido')
    else:
        st.warning("Coluna 'Nº Pedido' não encontrada. Não será usada para remover linhas nulas.")

    df = df.dropna(subset=colunas_essenciais_dropna)
    df['Anomalia'] = df.isnull().any(axis=1)

    # Reorganizar colunas na ordem desejada (adapta se colunas não existirem)
    colunas_ordem_base = [
        "Nº Pedido", "Cód. Cliente", "Nome Cliente", "Grupo Cliente",
        "Região", "Endereço Completo", "Qtde. dos Itens", "Peso dos Itens",
        "Latitude", "Longitude", "Janela de Descarga", "Anomalia"
    ]
    colunas_presentes_ordenadas = [col for col in colunas_ordem_base if col in df.columns]
    # Adiciona quaisquer outras colunas que não estavam na lista base ao final
    outras_colunas = [col for col in df.columns if col not in colunas_presentes_ordenadas]
    df = df[colunas_presentes_ordenadas + outras_colunas]

    return df
