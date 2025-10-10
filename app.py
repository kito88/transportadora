6import requests
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from datetime import datetime
from datetime import datetime, timedelta
from banco import conectar, criar_tabelas

app = Flask(__name__)
app.secret_key = 'chave_super_secreta'

criar_tabelas()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']

        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND senha = ?", (usuario, senha))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['usuario'] = usuario
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0]

    fretes_pendentes = 0
    fretes_concluidos = 0

    conn.close()

    return render_template('dashboard.html',
                           usuario=session['usuario'],
                           total_clientes=total_clientes,
                           fretes_pendentes=fretes_pendentes,
                           fretes_concluidos=fretes_concluidos)

@app.route('/api/consulta_cnpj')
def consulta_cnpj():
    cnpj = request.args.get('cnpj', '')
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj))

    if not cnpj_limpo or len(cnpj_limpo) != 14:
        return jsonify({'erro': 'CNPJ inválido'}), 400

    url = f'https://publica.cnpj.ws/cnpj/{cnpj_limpo}'
    try:
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()

        # Alguns campos podem estar diretamente no objeto ou em 'estabelecimento'
        estabelecimento = dados.get('estabelecimento') or {}

        # Tentativa alternativa para pegar campos
        razao_social = dados.get('razao_social') or dados.get('nome') or ''
        logradouro = estabelecimento.get('logradouro') or dados.get('logradouro') or ''
        numero = estabelecimento.get('numero') or dados.get('numero') or ''
        telefone = estabelecimento.get('telefone1') or estabelecimento.get('telefone') or ''

        dados_relevantes = {
            'razao_social': razao_social,
            'endereco': f"{logradouro}, {numero}".strip(', '),
            'telefone': telefone
        }
        return jsonify(dados_relevantes)
    except requests.exceptions.RequestException as e:
        return jsonify({'erro': 'Erro ao consultar CNPJ', 'detalhes': str(e)}), 500
    except ValueError:
        return jsonify({'erro': 'Resposta da API inválida'}), 500

###ROTA LISTAR CLIENTES

@app.route('/clientes')
def listar_clientes():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes")
    clientes = cursor.fetchall()
    conn.close()
    return render_template('clientes.html', clientes=clientes)


####rota criar clientes

@app.route('/clientes/novo', methods=['GET', 'POST'])
def novo_cliente():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        dados = (
            request.form.get('nome'),
            request.form.get('documento'),
            request.form.get('cep'),
            request.form.get('endereco'),
            request.form.get('bairro'),
            request.form.get('cidade'),
            request.form.get('estado'),
            request.form.get('telefone')
        )
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clientes (nome, documento, cep, endereco, bairro, cidade, estado, telefone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, dados)
        conn.commit()
        conn.close()
        flash("Cliente cadastrado com sucesso!")
        return redirect(url_for('listar_clientes'))

    return render_template('novo_cliente.html')



###ROTA PARA LISTAR COLETAS

@app.route('/coletas')
def listar_coletas():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.data_coleta, cl.nome, c.destinatario_nome, c.destinatario_cidade, c.destinatario_uf, c.status
        FROM coletas c
        JOIN clientes cl ON c.cliente_id = cl.id
        ORDER BY c.data_coleta DESC
    ''')
    coletas = cursor.fetchall()
    conn.close()

    coletas_com_status = []
    agora = datetime.now()

    for coleta in coletas:
        id_, data_coleta_str, cliente_nome, destinatario_nome, destinatario_cidade, destinatario_uf, status = coleta
        data_coleta = datetime.strptime(data_coleta_str, '%Y-%m-%d %H:%M:%S')
        # Atualizar status baseado na data e status atual
        if status == 'Pendente':
            if agora - data_coleta > timedelta(hours=24):
                status_atual = 'Atrasado'
            else:
                status_atual = 'Pendente'
        else:
            status_atual = status
        coletas_com_status.append((id_, data_coleta_str, cliente_nome, destinatario_nome, destinatario_cidade, destinatario_uf, status_atual))

    return render_template('coletas.html', coletas=coletas_com_status)

###ALTERANDO O STATUS COLETADO

@app.route('/coletas/marcar_coletado/<int:coleta_id>', methods=['POST'])
def marcar_coletado(coleta_id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE coletas SET status = 'Coletado' WHERE id = ?", (coleta_id,))
    conn.commit()
    conn.close()
    flash('Coleta marcada como coletada com sucesso!', 'success')
    return redirect(url_for('listar_coletas'))



###INSERINDO A ATUALIZAÇÃO PARA DATA DA COLETA

@app.route('/coletas/nova', methods=['GET', 'POST'])
def nova_coleta():
    conn = conectar()
    cursor = conn.cursor()

    if request.method == 'POST':
        dados = (
            request.form['cliente_id'],
            request.form['destinatario_nome'],
            request.form['destinatario_endereco'],
            request.form['destinatario_cidade'],
            request.form['destinatario_uf'],
            request.form.get('volumes', ''),
            request.form.get('peso', ''),
            request.form.get('valor_mercadoria', ''),
            request.form.get('dimensoes', ''),
            request.form.get('observacoes', '')
        )
        cursor.execute('''
            INSERT INTO coletas 
            (cliente_id, destinatario_nome, destinatario_endereco, destinatario_cidade, destinatario_uf,
             volumes, peso, valor_mercadoria, dimensoes, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', dados)
        conn.commit()
        conn.close()
        flash("Coleta criada com sucesso!")
        return redirect(url_for('listar_coletas'))

    cliente_id = request.args.get('cliente_id')
    cliente = None
    if cliente_id:
        cursor.execute("SELECT id, nome FROM clientes WHERE id = ?", (cliente_id,))
        cliente = cursor.fetchone()

    cursor.execute("SELECT id, nome FROM clientes")
    clientes = cursor.fetchall()
    conn.close()

    return render_template('nova_coleta.html', clientes=clientes, cliente=cliente, cliente_id=cliente_id)

###IMPRIMIR O PDF DA COLETA

@app.route('/coletas/imprimir/<int:coleta_id>')
def imprimir_coleta(coleta_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.data_coleta, cl.nome, cl.endereco, cl.cidade, cl.estado,
               c.destinatario_nome, c.destinatario_endereco, c.destinatario_cidade, c.destinatario_uf,
               c.volumes, c.peso, c.valor_mercadoria, c.dimensoes, c.observacoes
        FROM coletas c
        JOIN clientes cl ON c.cliente_id = cl.id
        WHERE c.id = ?
    ''', (coleta_id,))
    coleta = cursor.fetchone()
    conn.close()

    if not coleta:
        return "Coleta não encontrada", 404

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "GP CARGO EXPRESS")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 65, "CNPJ: 00.000.000/0001-00")
    p.drawString(50, height - 80, "Endereço: Rua Exemplo, 123 - São Paulo - SP")

    p.setFont("Helvetica-Bold", 14)
    p.drawString(200, height - 110, f"COLETA Nº {coleta[0]}")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 140, "Remetente:")
    p.setFont("Helvetica", 10)
    p.drawString(60, height - 155, f"{coleta[2]}")
    p.drawString(60, height - 170, f"{coleta[3]}, {coleta[4]} - {coleta[5]}")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 200, "Destinatário:")
    p.setFont("Helvetica", 10)
    p.drawString(60, height - 215, f"{coleta[6]}")
    p.drawString(60, height - 230, f"{coleta[7]}, {coleta[8]} - {coleta[9]}")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 260, f"Volumes: {coleta[10]}")
    p.drawString(50, height - 275, f"Peso: {coleta[11]}")
    p.drawString(50, height - 290, f"Valor da Mercadoria: {coleta[12]}")
    p.drawString(50, height - 305, f"Dimensões: {coleta[13]}")

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 335, "Observações:")
    p.setFont("Helvetica", 10)
    text = p.beginText(60, height - 350)
    for linha in (coleta[14] or '').split('\n'):
        text.textLine(linha)
    p.drawText(text)

    p.drawString(50, height - 400, f"Data da Coleta: {coleta[1]}")

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"coleta_{coleta[0]}.pdf", mimetype='application/pdf')

@app.route("/fretes")
def listar_fretes():
    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT * FROM fretes ORDER BY data_coleta DESC")
    fretes = cur.fetchall()
    con.close()
    return render_template("fretes.html", fretes=fretes)

@app.route("/fretes/novo", methods=["GET", "POST"])
def novo_frete():
    if request.method == "POST":
        dados = (
            request.form["remetente"], request.form["destinatario"],
            request.form["endereco_origem"], request.form["endereco_destino"],
            request.form["data_coleta"], request.form.get("observacoes", "")
        )
        con = conectar()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO fretes (remetente, destinatario, endereco_origem, endereco_destino, data_coleta, observacoes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, dados)
        con.commit()
        con.close()
        flash("Frete cadastrado com sucesso!", "success")
        return redirect(url_for("listar_fretes"))
    return render_template("fretes_form.html")

if __name__ == '__main__':
    #app.run(debug=True)
