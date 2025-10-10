import os
import psycopg2
import os

def conectar():
    url = os.getenv("DATABASE_URL")  # variável de ambiente no Render
    conn = psycopg2.connect(url)
    return conn


def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # Tabela usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        )
    ''')

    # Insere usuário admin padrão, se não existir
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

    # Tabela coletas (corrigida, incluindo status e data_coleta)
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
    
    # Adicionar colunas se não existirem
    if 'volumes' not in colunas:
        cursor.execute("ALTER TABLE coletas ADD COLUMN volumes TEXT")
    if 'peso' not in colunas:
        cursor.execute("ALTER TABLE coletas ADD COLUMN peso TEXT")
    if 'valor_mercadoria' not in colunas:
        cursor.execute("ALTER TABLE coletas ADD COLUMN valor_mercadoria TEXT")
    if 'dimensoes' not in colunas:
        cursor.execute("ALTER TABLE coletas ADD COLUMN dimensoes TEXT")
    if 'observacoes' not in colunas:
        cursor.execute("ALTER TABLE coletas ADD COLUMN observacoes TEXT")
    
    conn.commit()
    conn.close()




if __name__ == '__main__':
    criar_tabelas()
