import requests
import os
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime, timedelta
from banco import conectar, criar_tabelas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet


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
        if not conn:
            flash("Erro ao conectar ao banco de dados.")
            return render_template('login.html')

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario = %s AND senha = %s", (usuario, senha))
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
    conn.close()

    fretes_pendentes = 0
    fretes_concluidos = 0

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

        estabelecimento = dados.get('estabelecimento') or {}
        razao_social = dados.get('razao_social') or dados.get('nome') or ''
        logradouro = estabelecimento.get('logradouro') or ''
        numero = estabelecimento.get('numero') or ''
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

@app.route('/clientes')
def listar_clientes():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes ORDER BY id DESC")
    clientes = cursor.fetchall()
    conn.close()

    return render_template('clientes.html', clientes=clientes)

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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, dados)
        conn.commit()
        conn.close()
        flash("Cliente cadastrado com sucesso!")
        return redirect(url_for('listar_clientes'))

    return render_template('novo_cliente.html')

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
        id_, data_coleta, cliente_nome, destinatario_nome, destinatario_cidade, destinatario_uf, status = coleta
        if isinstance(data_coleta, str):
            data_coleta = datetime.strptime(data_coleta, '%Y-%m-%d %H:%M:%S')
        if status == 'Pendente':
            if agora - data_coleta > timedelta(hours=24):
                status_atual = 'Atrasado'
            else:
                status_atual = 'Pendente'
        else:
            status_atual = status
        coletas_com_status.append((id_, data_coleta, cliente_nome, destinatario_nome, destinatario_cidade, destinatario_uf, status_atual))

    return render_template('coletas.html', coletas=coletas_com_status)

@app.route('/coletas/marcar_coletado/<int:coleta_id>', methods=['POST'])
def marcar_coletado(coleta_id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE coletas SET status = 'Coletado' WHERE id = %s", (coleta_id,))
    conn.commit()
    conn.close()
    flash('Coleta marcada como coletada com sucesso!', 'success')
    return redirect(url_for('listar_coletas'))

@app.route('/coletas/nova', methods=['GET', 'POST'])
def nova_coleta():
    if 'usuario' not in session:
        return redirect(url_for('login'))

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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', dados)
        conn.commit()
        conn.close()
        flash("Coleta criada com sucesso!")
        return redirect(url_for('listar_coletas'))

    cursor.execute("SELECT id, nome FROM clientes ORDER BY nome ASC")
    clientes = cursor.fetchall()
    conn.close()
    return render_template('nova_coleta.html', clientes=clientes)

###IMPRIMIR O PDF DA COLETA

from reportlab.lib.colors import Color, black, HexColor

@app.route('/coletas/imprimir/<int:coleta_id>')
def imprimir_coleta(coleta_id):
    conn = conectar()
    cursor = conn.cursor()

    # Buscar dados da coleta
    cursor.execute('''
        SELECT c.id, c.data_coleta, cl.nome, cl.endereco, cl.cidade, cl.estado,
               c.destinatario_nome, c.destinatario_endereco, c.destinatario_cidade, c.destinatario_uf,
               c.volumes, c.peso, c.valor_mercadoria, c.dimensoes, c.observacoes
        FROM coletas c
        JOIN clientes cl ON c.cliente_id = cl.id
        WHERE c.id = ?
    ''', (coleta_id,))
    coleta = cursor.fetchone()

    # Buscar dados da empresa
    cursor.execute("SELECT nome, cnpj, ie, endereco FROM empresa WHERE id = 1")
    empresa = cursor.fetchone()
    conn.close()

    if not coleta:
        return "Coleta não encontrada", 404

    if empresa:
        nome_empresa, cnpj_empresa, ie_empresa, endereco_empresa = empresa
    else:
        nome_empresa, cnpj_empresa, ie_empresa, endereco_empresa = (
            "GP CARGO EXPRESS", "49.710.786/0001-20", "127.847.255.116", "Rua Tatsuo Kawana, Agua Chata - Guarulhos/SP"
        )

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # ------------------ Logo arredondado ------------------
    try:
        import os
        from reportlab.lib.utils import ImageReader
        from PIL import Image, ImageDraw

        logo_path = os.path.join("static", "logo.png")
        if os.path.exists(logo_path):
            # Abrir logo com PIL
            logo_img = Image.open(logo_path).convert("RGBA")
            w, h = logo_img.size
            # Criar máscara arredondada
            mask = Image.new('L', (w, h), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0,0,w,h), fill=255)
            logo_img.putalpha(mask)
            # Salvar temporariamente
            temp_path = os.path.join("static", "logo_temp.png")
            logo_img.save(temp_path, format="PNG")
            # Desenhar no PDF
            p.drawImage(temp_path, 50, height - 110, width=80, height=80, mask='auto')
    except Exception as e:
        print("Erro ao carregar logo:", e)

    # ------------------ Dados da empresa centralizados ------------------
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2 + 30, height - 50, nome_empresa)
    p.setFont("Helvetica", 10)
    p.drawCentredString(width / 2 + 30, height - 65, f"CNPJ: {cnpj_empresa}  IE: {ie_empresa}")
    p.drawCentredString(width / 2 + 30, height - 80, endereco_empresa)

    # Coleta número
    p.setFont("Helvetica-Bold", 14)
    p.drawString(200, height - 130, f"COLETA Nº {coleta[0]}")


    # Função para desenhar blocos com sombra e fundo branco (corrigida)
    def draw_block(x, y, w, h, title, lines):
        # Sombra leve
        shadow = Color(0,0,0, alpha=0.1)
        p.setFillColor(shadow)
        p.roundRect(x+3, y-3, w, h, 10, stroke=0, fill=1)
        
        # Fundo branco
        p.setFillColor(HexColor("#FFFFFF"))
        p.roundRect(x, y, w, h, 10, stroke=1, fill=1)
        
        # Título
        p.setFillColor(black)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(x+5, y + h - 15, title)
        
        # Conteúdo
        p.setFont("Helvetica", 10)
        linha_y = y + h - 30
        for linha in lines:
            # Quebrar linha em várias se exceder largura
            linhas_quebradas = textwrap.wrap(linha, width=50)  # Ajuste width conforme necessidade
            for l in linhas_quebradas:
                p.drawString(x+10, linha_y, l)
                linha_y -= 12  # espaçamento entre linhas


    # ----------- Blocos Remetente e Destinatário -----------
    margem_top = height - 160
    bloco_altura = 80
    bloco_largura = 250

    draw_block(
        50, margem_top - bloco_altura,
        bloco_largura, bloco_altura,
        "Remetente",
        [f"Nome: {coleta[2]}", f"Endereço: {coleta[3]}, {coleta[4]} - {coleta[5]}"]
    )

    draw_block(
        330, margem_top - bloco_altura,
        bloco_largura, bloco_altura,
        "Destinatário",
        [f"Nome: {coleta[6]}", f"Endereço: {coleta[7]}, {coleta[8]} - {coleta[9]}"]
    )

    # ----------- Informações da Coleta -----------
    info_top = margem_top - bloco_altura - 50
    draw_block(
        50, info_top - 90,
        530, 90,
        "Informações da Coleta",
        [f"Volumes: {coleta[10]}", f"Peso: {coleta[11]}", f"Valor da Mercadoria: {coleta[12]}", f"Dimensões: {coleta[13]}"]
    )

    # ----------- Observações -----------
    obs_top = info_top - 130
    draw_block(
        50, obs_top - 60,
        530, 60,
        "Observações",
        (coleta[14] or '').split('\n')
    )

    # Data da coleta
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, obs_top - 80, f"Data da Coleta: {coleta[1]}")

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"coleta_{coleta[0]}.pdf", mimetype='application/pdf')

    # Rodapé
    p.setFont("Helvetica-Oblique", 8)
    p.drawCentredString(width/2, 30, "www.gpcargo.log.br - Telefone: (11) 99676-5702")

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"coleta_{coleta[0]}.pdf", mimetype='application/pdf')

@app.route("/fretes")
def listar_fretes():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT * FROM fretes ORDER BY data_coleta DESC")
    fretes = cur.fetchall()
    con.close()
    return render_template("fretes.html", fretes=fretes)

@app.route("/fretes/novo", methods=["GET", "POST"])
def novo_frete():
    if 'usuario' not in session:
        return redirect(url_for('login'))
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
            VALUES (%s, %s, %s, %s, %s, %s)
        """, dados)
        con.commit()
        con.close()
        flash("Frete cadastrado com sucesso!", "success")
        return redirect(url_for("listar_fretes"))
    return render_template("fretes_form.html")

if __name__ == '__main__':
    # app.run(debug=True)
    pass
