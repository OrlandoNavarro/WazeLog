import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'wazelog.db')

# Conexão e criação das tabelas

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Tabela frota
    cur.execute('''CREATE TABLE IF NOT EXISTS frota (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        placa TEXT,
        transportador TEXT,
        descricao TEXT,
        veiculo TEXT,
        capacidade_cx INTEGER,
        capacidade_kg REAL,
        disponivel INTEGER,
        id_veiculo TEXT
    )''')
    # Tabela pedidos
    cur.execute('''CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_pedido TEXT,
        cod_cliente TEXT,
        nome_cliente TEXT,
        grupo_cliente TEXT,
        regiao TEXT,
        endereco_completo TEXT,
        qtde_itens INTEGER,
        peso_itens REAL,
        latitude REAL,
        longitude REAL,
        janela_descarga INTEGER DEFAULT 30,
        anomalia INTEGER
    )''')
    # Tabela config para endereço de partida
    cur.execute('''CREATE TABLE IF NOT EXISTS config (
        chave TEXT PRIMARY KEY,
        valor TEXT,
        latitude REAL,
        longitude REAL
    )''')
    # Tabela coordenadas
    cur.execute('''CREATE TABLE IF NOT EXISTS coordenadas (
        endereco_completo TEXT PRIMARY KEY,
        latitude REAL,
        longitude REAL
    )''')
    conn.commit()
    conn.close()

# Funções para endereço de partida

def salvar_endereco_partida(endereco, latitude, longitude):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''INSERT OR REPLACE INTO config (chave, valor, latitude, longitude)
                   VALUES (?, ?, ?, ?)''', ("endereco_partida", endereco, latitude, longitude))
    conn.commit()
    conn.close()

def carregar_endereco_partida():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''SELECT valor, latitude, longitude FROM config WHERE chave = ?''', ("endereco_partida",))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2]
    return None, None, None

# Funções para Frota

def salvar_frota(df):
    conn = get_connection()
    df = df.copy()
    df['disponivel'] = df['Disponível'].astype(int)
    df = df.rename(columns={
        'Placa': 'placa',
        'Transportador': 'transportador',
        'Descrição': 'descricao',
        'Veículo': 'veiculo',
        'Capacidade (Cx)': 'capacidade_cx',
        'Capacidade (Kg)': 'capacidade_kg',
        'ID Veículo': 'id_veiculo',
        'disponivel': 'disponivel'
    })
    df.to_sql('frota', conn, if_exists='replace', index=False)
    conn.close()

def carregar_frota():
    conn = get_connection()
    df = pd.read_sql('SELECT * FROM frota', conn)
    conn.close()
    if not df.empty:
        df = df.drop(columns=['id'], errors="ignore")
        df = df.rename(columns={
            'placa': 'Placa',
            'transportador': 'Transportador',
            'descricao': 'Descrição',
            'veiculo': 'Veículo',
            'capacidade_cx': 'Capacidade (Cx)',
            'capacidade_kg': 'Capacidade (Kg)',
            'id_veiculo': 'ID Veículo',
            'disponivel': 'Disponível'
        })
        df['Disponível'] = df['Disponível'].astype(bool)
    return df

def limpar_frota():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM frota')
    conn.commit()
    conn.close()

# Funções para Pedidos

def salvar_pedidos(df):
    conn = get_connection()
    df = df.copy()
    # Garante que as colunas Latitude e Longitude existam
    if 'Latitude' not in df.columns:
        df['Latitude'] = None
    if 'Longitude' not in df.columns:
        df['Longitude'] = None
    # Garante que a coluna Janela de Descarga exista
    if 'Janela de Descarga' not in df.columns:
        df['Janela de Descarga'] = 30
    # Remove colunas duplicadas de anomalia antes de renomear/criar
    for col in ['anomalia', 'Anomalia']:
        if col in df.columns:
            df = df.drop(columns=[col])
    # Renomeia colunas
    df = df.rename(columns={
        'Nº Pedido': 'numero_pedido',
        'Cód. Cliente': 'cod_cliente',
        'Nome Cliente': 'nome_cliente',
        'Grupo Cliente': 'grupo_cliente',
        'Região': 'regiao',
        'Endereço Completo': 'endereco_completo',
        'Qtde. dos Itens': 'qtde_itens',
        'Peso dos Itens': 'peso_itens',
        'Latitude': 'latitude',
        'Longitude': 'longitude',
        'Janela de Descarga': 'janela_descarga'
    })
    # Cria coluna 'anomalia' final
    df['anomalia'] = 0
    if 'Anomalia' in df.columns:
        df['anomalia'] = df['Anomalia'].astype(int)
    df.to_sql('pedidos', conn, if_exists='replace', index=False)
    conn.close()

def carregar_pedidos():
    conn = get_connection()
    df = pd.read_sql('SELECT * FROM pedidos', conn)
    conn.close()
    if not df.empty:
        df = df.drop(columns=['id'], errors="ignore")
        df = df.rename(columns={
            'numero_pedido': 'Nº Pedido',
            'cod_cliente': 'Cód. Cliente',
            'nome_cliente': 'Nome Cliente',
            'grupo_cliente': 'Grupo Cliente',
            'regiao': 'Região',
            'endereco_completo': 'Endereço Completo',
            'qtde_itens': 'Qtde. dos Itens',
            'peso_itens': 'Peso dos Itens',
            'latitude': 'Latitude',
            'longitude': 'Longitude',
            'janela_descarga': 'Janela de Descarga',
            'anomalia': 'Anomalia'
        })
        # Remover colunas de endereço originais se existirem
        for col in ["Endereço de Entrega", "Bairro de Entrega", "Cidade de Entrega"]:
            if col in df.columns:
                df = df.drop(columns=[col])
        # Reorganizar colunas na ordem desejada
        colunas_ordem = [
            "Nº Pedido", "Cód. Cliente", "Nome Cliente", "Grupo Cliente",
            "Região", "Endereço Completo", "Qtde. dos Itens", "Peso dos Itens",
            "Latitude", "Longitude", "Janela de Descarga", "Anomalia"
        ]
        df = df[[col for col in colunas_ordem if col in df.columns]]
        if 'Anomalia' in df.columns:
            df['Anomalia'] = df['Anomalia'].astype(bool)
    return df

def salvar_coordenada(endereco_completo, latitude, longitude):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''INSERT OR REPLACE INTO coordenadas (endereco_completo, latitude, longitude)
                   VALUES (?, ?, ?)''', (endereco_completo, latitude, longitude))
    conn.commit()
    conn.close()

def buscar_coordenada(endereco_completo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''SELECT latitude, longitude FROM coordenadas WHERE endereco_completo = ?''', (endereco_completo,))
    row = cur.fetchone()
    conn.close()
    if row and row[0] is not None and row[1] is not None:
        return row[0], row[1]
    return None, None
