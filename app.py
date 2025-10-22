from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, Patient, Encounter, SistemaTriagem
import os

app = Flask(__name__)

# Desabilita instance folder (Vercel tem sistema read-only)
app.instance_path = '/tmp'

# Configuração do banco de dados
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Vercel - Usa PostgreSQL
    # Corrige URL se vier com postgres:// ao invés de postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Remove channel_binding se estiver causando problemas
    if "channel_binding=require" in database_url:
        database_url = database_url.replace("&channel_binding=require", "").replace("channel_binding=require&", "").replace("channel_binding=require", "")
    
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    print(f"🔗 Conectando ao PostgreSQL...")
else:
    # Local - Usa SQLite
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///amelia.db"
    print(f"🔗 Usando SQLite local...")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave_secreta_amelia_2025")

# Inicializa o banco de dados
db.init_app(app)

# Cria as tabelas
with app.app_context():
    try:
        db.create_all()
        print("✅ Tabelas criadas/verificadas com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")

@app.route("/")
def index():
    """Página inicial"""
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Login do paciente"""
    if request.method == "POST":
        cpf = request.form["cpf"].replace(".", "").replace("-", "")
        senha = request.form["senha"]
        
        paciente = Patient.query.filter_by(cpf=cpf).first()
        
        if paciente and check_password_hash(paciente.senha_hash, senha):
            session["paciente_id"] = paciente.id
            session["paciente_nome"] = paciente.nome
            flash(f"Bem-vindo(a), {paciente.nome}!", "success")
            return redirect(url_for("chat_triagem"))
        else:
            flash("CPF ou senha incorretos.", "danger")
    
    return render_template("login.html")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    """Cadastro de novo paciente"""
    if request.method == "POST":
        nome = request.form["nome"]
        cpf = request.form["cpf"].replace(".", "").replace("-", "")
        sus = request.form["sus"]
        senha = request.form["senha"]
        confirma_senha = request.form["confirma_senha"]
        
        # Validações
        if senha != confirma_senha:
            flash("As senhas não coincidem!", "danger")
            return redirect(url_for("cadastro"))
        
        if len(senha) < 6:
            flash("A senha deve ter no mínimo 6 caracteres!", "danger")
            return redirect(url_for("cadastro"))
        
        # Verifica se CPF já existe
        if Patient.query.filter_by(cpf=cpf).first():
            flash("CPF já cadastrado no sistema!", "danger")
            return redirect(url_for("cadastro"))
        
        # Cria novo paciente
        senha_hash = generate_password_hash(senha)
        novo_paciente = Patient(
            nome=nome,
            cpf=cpf,
            sus=sus,
            senha_hash=senha_hash
        )
        
        db.session.add(novo_paciente)
        db.session.commit()
        
        flash("Cadastro realizado com sucesso! Faça login para continuar.", "success")
        return redirect(url_for("login"))
    
    return render_template("cadastro.html")

@app.route("/chat_triagem", methods=["GET", "POST"])
def chat_triagem():
    """Chat de triagem com AMÉLIA"""
    if "paciente_id" not in session:
        flash("Faça login para acessar a triagem.", "warning")
        return redirect(url_for("login"))
    
    paciente_id = session["paciente_id"]
    resposta_amelia = None
    historico = []
    
    # Inicializa conversa na sessão se não existir
    if 'conversa_triagem' not in session:
        session['conversa_triagem'] = {
            'etapa': 0,
            'respostas': {},
            'sintomas_coletados': [],
            'dados_vitais': {}
        }
    
    if request.method == "POST":
        mensagem = request.form.get("mensagem", "").strip()
        
        if mensagem:
            # Processa a resposta do usuário usando sessão
            resposta_amelia = SistemaTriagem.processar_resposta_sessao(session, mensagem)
            historico = session['conversa_triagem'].get('sintomas_coletados', [])
            
            # Se a triagem finalizou, salva no banco
            if session['conversa_triagem'].get('finalizado', False):
                SistemaTriagem.salvar_triagem(paciente_id, session['conversa_triagem'])
                # Limpa a conversa da sessão
                session.pop('conversa_triagem', None)
            else:
                # Salva a sessão modificada
                session.modified = True
            
            # Debug - mostra no console
            print(f"Mensagem do usuário: {mensagem}")
            print(f"Resposta da AMÉLIA: {resposta_amelia}")
            print(f"Histórico: {historico}")
    else:
        # GET - Primeira vez ou recarregou a página
        historico = session['conversa_triagem'].get('sintomas_coletados', [])
        
        # Se não há conversa ativa, inicia uma nova
        if session['conversa_triagem']['etapa'] == 0 and not historico:
            resposta_amelia = SistemaTriagem.iniciar_conversa_sessao(session)
            session.modified = True
    
    return render_template(
        "chattriagem.html",
        resposta=resposta_amelia,
        historico=historico
    )

@app.route("/resetar_triagem")
def resetar_triagem():
    """Reseta a conversa de triagem"""
    if "paciente_id" in session:
        session.pop('conversa_triagem', None)
        session.modified = True
        flash("Triagem resetada. Você pode iniciar uma nova conversa.", "info")
    return redirect(url_for("chat_triagem"))

@app.route("/prontuario")
def prontuario():
    """Visualiza prontuário do paciente"""
    if "paciente_id" not in session:
        flash("Faça login para acessar seu prontuário.", "warning")
        return redirect(url_for("login"))
    
    paciente_id = session["paciente_id"]
    paciente = Patient.query.get(paciente_id)
    consultas = Encounter.query.filter_by(patient_id=paciente_id).order_by(Encounter.data.desc()).all()
    
    return render_template(
        "prontuario.html",
        paciente=paciente,
        consultas=consultas
    )

@app.route("/painel_atendimento")
def painel_atendimento():
    """Painel para equipe de saúde - visualiza fila de atendimento"""
    # Busca consultas aguardando atendimento, ordenadas por prioridade
    ordem_prioridade = {
        'URGENTE': 1,
        'ALTA': 2,
        'MÉDIA': 3,
        'BAIXA': 4
    }
    
    consultas = Encounter.query.filter_by(status='aguardando').all()
    consultas_ordenadas = sorted(
        consultas,
        key=lambda x: (ordem_prioridade.get(x.prioridade, 5), x.data)
    )
    
    return render_template(
        "painel_atendimento.html",
        consultas=consultas_ordenadas
    )

@app.route("/chamar_paciente/<int:consulta_id>")
def chamar_paciente(consulta_id):
    """Atualiza status da consulta para 'em atendimento'"""
    consulta = Encounter.query.get(consulta_id)
    if consulta:
        consulta.status = 'em_atendimento'
        db.session.commit()
        flash(f"Paciente {consulta.senha_chamada} chamado!", "success")
    return redirect(url_for("painel_atendimento"))

@app.route("/finalizar_atendimento/<int:consulta_id>")
def finalizar_atendimento(consulta_id):
    """Finaliza o atendimento"""
    consulta = Encounter.query.get(consulta_id)
    if consulta:
        consulta.status = 'finalizado'
        db.session.commit()
        flash("Atendimento finalizado!", "success")
    return redirect(url_for("painel_atendimento"))

@app.route("/logout")
def logout():
    """Logout do sistema"""
    session.clear()
    flash("Logout realizado com sucesso!", "info")
    return redirect(url_for("index"))

@app.route("/sobre")
def sobre():
    """Página sobre o projeto"""
    return render_template("sobre.html")

# Filtro customizado para formatar data
@app.template_filter('formatar_data')
def formatar_data(data):
    if data:
        return data.strftime("%d/%m/%Y às %H:%M")
    return ""

# Filtro para cor da prioridade
@app.template_filter('cor_prioridade')
def cor_prioridade(prioridade):
    cores = {
        'URGENTE': 'danger',
        'ALTA': 'warning',
        'MÉDIA': 'info',
        'BAIXA': 'success'
    }
    return cores.get(prioridade, 'secondary')

# Para rodar localmente
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
