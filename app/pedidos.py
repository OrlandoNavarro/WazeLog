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
    # Agora carrega de um CSV simples
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'coordenadas.csv')
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path, dtype=str)
        return {(str(row['CPF/CNPJ']) + '|' + str(row['Endereço Completo'])): (float(row['Latitude']), float(row['Longitude']))
                for _, row in df.iterrows() if pd.notnull(row['Latitude']) and pd.notnull(row['Longitude'])}
    except Exception:
        return {}

def buscar_coordenadas_no_dict(endereco, coord_dict):
    # Agora a chave é CPF/CNPJ|Endereço Completo
    cpf_cnpj = None
    endereco_completo = None
    if isinstance(endereco, dict):
        cpf_cnpj = endereco.get('CPF/CNPJ', '')
        endereco_completo = endereco.get('Endereço Completo', '')
    else:
        # Para compatibilidade, assume que endereco é o endereço completo e CPF/CNPJ não está disponível
        endereco_completo = endereco
    for key in coord_dict:
        if cpf_cnpj and key.startswith(str(cpf_cnpj)+'|') and key.endswith(endereco_completo):
            lat, lon = coord_dict[key]
            if pd.notnull(lat) and pd.notnull(lon):
                return lat, lon
        elif not cpf_cnpj and key.endswith(endereco_completo):
            lat, lon = coord_dict[key]
            if pd.notnull(lat) and pd.notnull(lon):
                return lat, lon
    return None, None

def obter_coordenadas(endereco):
    # Busca apenas em APIs externas, pois a busca no banco já é feita no fluxo principal
    cpf_cnpj = None
    if isinstance(endereco, dict):
        cpf_cnpj = endereco.get('CPF/CNPJ', None)
        endereco_completo = endereco.get('Endereço Completo', None)
    else:
        endereco_completo = endereco
    lat, lon = obter_coordenadas_opencage(endereco_completo)
    if lat is not None and lon is not None:
        salvar_coordenada_csv(cpf_cnpj, endereco_completo, lat, lon)
        return lat, lon
    lat, lon = obter_coordenadas_nominatim(endereco_completo)
    if lat is not None and lon is not None:
        salvar_coordenada_csv(cpf_cnpj, endereco_completo, lat, lon)
    return lat, lon

# Função para salvar coordenada no CSV
def salvar_coordenada_csv(cpf_cnpj, endereco_completo, latitude, longitude):
    import pandas as pd
    import os
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'coordenadas.csv')
    # Carrega ou cria DataFrame
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, dtype=str)
    else:
        df = pd.DataFrame(columns=['CPF/CNPJ', 'Endereço Completo', 'Latitude', 'Longitude'])
    # Remove duplicata se já existir
    mask = (df['CPF/CNPJ'] == str(cpf_cnpj)) & (df['Endereço Completo'] == str(endereco_completo))
    df = df[~mask]
    # Adiciona nova linha
    new_row = {
        'CPF/CNPJ': str(cpf_cnpj) if cpf_cnpj is not None else '',
        'Endereço Completo': str(endereco_completo),
        'Latitude': str(latitude),
        'Longitude': str(longitude)
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(csv_path, index=False)

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

    # Garante que a coluna CNPJ exista e esteja formatada corretamente
    import re
    def formatar_cnpj(cnpj):
        if pd.isnull(cnpj):
            return ''
        cnpj_str = re.sub(r'\D', '', str(cnpj))
        if len(cnpj_str) == 14:
            return f"{cnpj_str[:2]}.{cnpj_str[2:5]}.{cnpj_str[5:8]}/{cnpj_str[8:12]}-{cnpj_str[12:]}"
        return cnpj

    if 'CNPJ' in df.columns:
        df['CNPJ'] = df['CNPJ'].apply(formatar_cnpj)

    # Não é mais necessário remover a coluna CPF/CNPJ, pois ela não será criada
    # --- Lógica de Endereço Ajustada ---
    # Verifica se 'Endereço Completo' já existe
    if 'Endereço Completo' not in df.columns:
        # Agora inclui 'Estado de Entrega'
        colunas_endereco_necessarias = [
            'Endereço de Entrega', 'Bairro de Entrega', 'Cidade de Entrega', 'Estado de Entrega'
        ]
        colunas_faltantes = [col for col in colunas_endereco_necessarias if col not in df.columns]

        if not colunas_faltantes:
            st.info("Coluna 'Endereço Completo' não encontrada. Criando a partir de 'Endereço de Entrega', 'Bairro', 'Cidade', 'Estado'.")
            # Garante que as colunas são string antes de concatenar, tratando nulos
            df['Endereço Completo'] = (
                df['Endereço de Entrega'].fillna('').astype(str) + ', ' +
                df['Bairro de Entrega'].fillna('').astype(str) + ', ' +
                df['Cidade de Entrega'].fillna('').astype(str) + ', ' +
                df['Estado de Entrega'].fillna('').astype(str)
            )
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
            raise ValueError(
                f"Erro: Coluna 'Endereço Completo' não encontrada e colunas necessárias para criá-la ({', '.join(colunas_faltantes)}) também estão ausentes."
            )
    else:
        st.info("Coluna 'Endereço Completo' encontrada no arquivo. Usando-a diretamente.")
        # Garante que a coluna existente seja string
        df['Endereço Completo'] = df['Endereço Completo'].fillna('').astype(str)

    # --- Garante colunas essenciais ---
    if 'Janela de Descarga' not in df.columns:
        df['Janela de Descarga'] = 30
    if 'Latitude' not in df.columns:
        df['Latitude'] = None
    if 'Longitude' not in df.columns:
        df['Longitude'] = None

    # --- Garante colunas de janela de tempo e tempo de serviço para VRPTW ---
    if 'Janela Início' not in df.columns:
        df['Janela Início'] = "06:00"
    else:
        df['Janela Início'] = df['Janela Início'].fillna('').replace('', '06:00')
    if 'Janela Fim' not in df.columns:
        df['Janela Fim'] = "20:00"
    else:
        df['Janela Fim'] = df['Janela Fim'].fillna('').replace('', '20:00')
    if 'Tempo de Serviço' not in df.columns:
        df['Tempo de Serviço'] = "00:30"
    else:
        df['Tempo de Serviço'] = df['Tempo de Serviço'].fillna('').replace('', '00:30')

    # --- Continua o processamento ---
    # Definir Região apenas pela Cidade de Entrega
    if 'Cidade de Entrega' in df.columns:
        df['Região'] = df['Cidade de Entrega'].astype(str).str.strip()
    else:
        # Tenta extrair cidade do endereço completo (simplificado)
        try:
            df['Região'] = df['Endereço Completo'].str.split(',').str[-2].str.strip()
        except Exception:
            df['Região'] = 'N/A' # Fallback
        st.warning("Coluna 'Cidade de Entrega' não encontrada. 'Região' definida a partir do 'Endereço Completo' (pode ser impreciso).")


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
        "Nº Pedido", "Cód. Cliente", "CNPJ", "Nome Cliente", "Grupo Cliente",
        "Região", "Endereço Completo", "Qtde. dos Itens", "Peso dos Itens",
        "Latitude", "Longitude", "Janela de Descarga", "Anomalia"
    ]
    colunas_presentes_ordenadas = [col for col in colunas_ordem_base if col in df.columns]
    # Adiciona quaisquer outras colunas que não estavam na lista base ao final
    outras_colunas = [col for col in df.columns if col not in colunas_presentes_ordenadas]
    df = df[colunas_presentes_ordenadas + outras_colunas]

    return df
