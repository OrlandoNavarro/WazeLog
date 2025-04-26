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
        df = pd.read_sql('SELECT endereco_completo, latitude, longitude FROM pedidos', conn)
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
        return lat, lon
    lat, lon = obter_coordenadas_nominatim(endereco)
    return lat, lon

def processar_pedidos(arquivo, max_linhas=None):
    nome = arquivo.name if hasattr(arquivo, 'name') else str(arquivo)
    ext = os.path.splitext(nome)[-1].lower()
    if ext in ['.xlsx', '.xlsm']:
        df = pd.read_excel(arquivo)
    elif ext == '.csv':
        df = pd.read_csv(arquivo)
    elif ext == '.json':
        df = pd.read_json(arquivo)
    else:
        raise ValueError('Formato de arquivo não suportado.')
    df['Região'] = df.apply(definir_regiao, axis=1)
    df['Endereço Completo'] = df['Endereço de Entrega'].astype(str) + ', ' + df['Bairro de Entrega'].astype(str) + ', ' + df['Cidade de Entrega'].astype(str)
    # Remover colunas originais após criar Endereço Completo
    df = df.drop(['Endereço de Entrega', 'Bairro de Entrega', 'Cidade de Entrega'], axis=1)
    # Limitar número de linhas para teste, se max_linhas for fornecido
    if max_linhas is not None:
        df = df.head(max_linhas)
    n = len(df)
    latitudes = [None] * n
    longitudes = [None] * n
    progress_bar = st.progress(0, text="Buscando coordenadas...")
    coord_dict = carregar_coordenadas_salvas()
    def buscar_coordenada_db(endereco):
        from app.database import buscar_coordenada
        return buscar_coordenada(endereco)
    def processar_linha(i, row):
        lat = row.get('Latitude')
        lon = row.get('Longitude')
        if pd.notnull(lat) and pd.notnull(lon):
            latitudes[i] = lat
            longitudes[i] = lon
        else:
            # Busca primeiro no dicionário carregado
            lat, lon = buscar_coordenadas_no_dict(row['Endereço Completo'], coord_dict)
            if lat is not None and lon is not None:
                latitudes[i] = lat
                longitudes[i] = lon
            else:
                # Busca diretamente no banco de dados (tabela coordenadas)
                lat, lon = buscar_coordenada_db(row['Endereço Completo'])
                if lat is not None and lon is not None:
                    latitudes[i] = lat
                    longitudes[i] = lon
                else:
                    # Só consulta API externa se não encontrar no banco
                    lat, lon = obter_coordenadas(row['Endereço Completo'])
                    latitudes[i] = lat
                    longitudes[i] = lon
    threads = []
    for i, row in df.iterrows():
        t = threading.Thread(target=processar_linha, args=(i, row))
        threads.append(t)
        t.start()
        # Limita o número de threads simultâneas para não sobrecarregar
        if len(threads) >= 10:
            for t in threads:
                t.join()
            threads = []
        progresso = (i + 1) / n
        tempo_decorrido = time.time() - tempo_inicio
        tempo_estimado = tempo_decorrido / progresso if progresso > 0 else 0
        tempo_restante = tempo_estimado - tempo_decorrido
        progress_bar.progress(progresso, text=f"Buscando coordenadas... ({i+1}/{n}) | Tempo restante: {int(tempo_restante)}s")
    # Aguarda threads restantes
    for t in threads:
        t.join()
    df['Latitude'] = latitudes
    df['Longitude'] = longitudes
    progress_bar.empty()
    # Normalização e detecção de anomalias
    df = df.drop_duplicates()
    df = df.dropna(subset=['Nº Pedido', 'Endereço Completo'])
    df['Anomalia'] = df.isnull().any(axis=1)
    # Reorganizar colunas na ordem desejada
    colunas_ordem = [
        "Nº Pedido", "Cód. Cliente", "Nome Cliente", "Grupo Cliente",
        "Região", "Endereço Completo", "Qtde. dos Itens", "Peso dos Itens",
        "Latitude", "Longitude", "Janela de Descarga", "Anomalia"
    ]
    df = df[[col for col in colunas_ordem if col in df.columns]]
    return df
