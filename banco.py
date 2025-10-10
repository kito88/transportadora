import psycopg
from psycopg.rows import dict_row
import os

def conectar():
    try:
        url = os.getenv("DATABASE_URL")
        conn = psycopg.connect(url)
        return conn
    except Exception as e:
        print("Erro ao conectar ao banco:", e)
        return None

def criar_tabelas():
    conn = conectar()
    if not conn:
        print("Falha ao conectar ao banco de dados.")
        return

    with conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            # Tabela usuarios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    usuario VARCHAR(100) UNIQUE NOT NULL,
                    senha VARCHAR(100) NOT NULL
                )
            ''')

            # Inserir usuário admin padrão se não existir
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            if cursor.fetchone()['count'] == 0:
                cursor.execute(
                    "INSERT INTO usuarios (usuario, senha) VALUES (%s, %s)",
                    ('admin', 'admin')
                )

            # Tabela clientes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clientes (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(150) NOT NULL,
                    documento VARCHAR(20) NOT NULL,
                    cep VARCHAR(10),
                    endereco VARCHAR(150),
                    bairro VARCHAR(100),
                    cidade VARCHAR(100),
                    estado VARCHAR(2),
                    telefone VARCHAR(20)
                )
            ''')

            # Tabela fretes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fretes (
                    id SERIAL PRIMARY KEY,
                    remetente VARCHAR(150) NOT NULL,
                    destinatario VARCHAR(150) NOT NULL,
                    endereco_origem VARCHAR(200) NOT NULL,
                    endereco_destino VARCHAR(200) NOT NULL,
                    data_coleta TIMESTAMP NOT NULL,
                    status VARCHAR(50) DEFAULT 'Pendente',
                    observacoes TEXT
                )
            ''')

            # Tabela coletas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coletas (
                    id SERIAL PRIMARY KEY,
                    cliente_id INTEGER REFERENCES clientes(id),
                    destinatario_nome VARCHAR(150),
                    destinatario_endereco VARCHAR(200),
                    destinatario_cidade VARCHAR(100),
                    destinatario_uf VARCHAR(2),
                    data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    volumes VARCHAR(50),
                    peso VARCHAR(50),
                    valor_mercadoria VARCHAR(50),
                    largura NUMERIC,
                    altura NUMERIC,
                    comprimento NUMERIC,
                    dimensoes VARCHAR(100),
                    volume_m3 NUMERIC,
                    observacoes TEXT,
                    status VARCHAR(50) DEFAULT 'Pendente'
                )
            ''')

    conn.close()
    print("✅ Tabelas criadas/verificadas com sucesso no PostgreSQL.")

if __name__ == "__main__":
    criar_tabelas()