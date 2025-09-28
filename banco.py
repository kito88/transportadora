import sqlite3
import os

DB_PATH = os.path.join('db', 'transportadora.db')

def conectar():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # Tabela empresa
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresa (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            cnpj TEXT NOT NULL,
            ie TEXT,
            endereco TEXT
        )
    ''')
    # Dados padrão da empresa
    cursor.execute("SELECT COUNT(*) FROM empresa")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO empresa (id, nome, cnpj, ie, endereco)
            VALUES (?, ?, ?, ?, ?)
        ''', (1, 'GP CARGO EXPRESS', '49.710.786/0001-20', '127.847.255.116', 'Rua Tatsuo Kawana, Agua Chata - Guarulhos/SP'))

    # Tabela usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        )
    ''')
    # Usuário admin padrão
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (usuario, senha) VALUES (?, ?)", ('admin', 'admin'))

    # Tabela clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            documento TEXT NOT NULL,
            cep TEXT,
            endereco TEXT,
            bairro TEXT,
            cidade TEXT,
            estado TEXT,
            telefone TEXT
        )
    ''')

    # Tabela fretes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fretes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remetente TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            endereco_origem TEXT NOT NULL,
            endereco_destino TEXT NOT NULL,
            data_coleta TEXT NOT NULL,
            status TEXT DEFAULT 'Pendente',
            observacoes TEXT
        )
    ''')

    # Tabela coletas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            destinatario_nome TEXT,
            destinatario_endereco TEXT,
            destinatario_cidade TEXT,
            destinatario_uf TEXT,
            data_coleta TEXT DEFAULT CURRENT_TIMESTAMP,
            volumes TEXT,
            peso TEXT,
            valor_mercadoria TEXT,
            largura REAL,
            altura REAL,
            comprimento REAL,
            dimensoes TEXT,
            volume_m3 REAL,
            observacoes TEXT,
            status TEXT DEFAULT 'Pendente',
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')

    conn.commit()
    conn.close()

def adicionar_colunas_coletas():
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(coletas)")
    colunas = [col[1] for col in cursor.fetchall()]
    
    # Adiciona colunas se não existirem
    colunas_para_adicionar = {
        'volumes': 'TEXT',
        'peso': 'TEXT',
        'valor_mercadoria': 'TEXT',
        'largura': 'REAL',
        'altura': 'REAL',
        'comprimento': 'REAL',
        'dimensoes': 'TEXT',
        'volume_m3': 'REAL',
        'observacoes': 'TEXT',
        'status': "TEXT DEFAULT 'Pendente'"
    }
    for coluna, tipo in colunas_para_adicionar.items():
        if coluna not in colunas:
            cursor.execute(f"ALTER TABLE coletas ADD COLUMN {coluna} {tipo}")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    criar_tabelas()
    adicionar_colunas_coletas()
