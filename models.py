from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random

db = SQLAlchemy()

class Patient(db.Model):
    __tablename__ = 'patient'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    sus = db.Column(db.String(20), nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamento
    consultas = db.relationship('Encounter', backref='paciente', lazy=True)

class Encounter(db.Model):
    __tablename__ = 'encounter'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    data = db.Column(db.DateTime, default=datetime.now)
    sintomas = db.Column(db.Text)
    nivel_dor = db.Column(db.Integer)
    temperatura = db.Column(db.Float)
    batimentos = db.Column(db.Integer)
    pressao_sistolica = db.Column(db.Integer)
    pressao_diastolica = db.Column(db.Integer)
    prioridade = db.Column(db.String(50))
    senha_chamada = db.Column(db.String(10))
    status = db.Column(db.String(20), default='aguardando')  # aguardando, em_atendimento, finalizado
    observacoes = db.Column(db.Text)

# Armazenamento temporário da conversa (em memória)
conversas_ativas = {}

class SistemaTriagem:
    """Sistema inteligente de triagem da AMÉLIA"""
    
    # Perguntas do protocolo de triagem
    PERGUNTAS = [
        {"id": 1, "texto": "Olá! Sou a AMÉLIA 🤖💙\n\nVou fazer algumas perguntas para entender melhor como você está se sentindo.\n\nQual é o seu principal sintoma ou queixa hoje?", "tipo": "texto"},
        {"id": 2, "texto": "Há quanto tempo você está sentindo isso?\n(Digite: horas, dias ou semanas)", "tipo": "tempo"},
        {"id": 3, "texto": "Em uma escala de 0 a 10, qual é o seu nível de dor ou desconforto?\n(0 = sem dor, 10 = dor insuportável)", "tipo": "numero"},
        {"id": 4, "texto": "Você está com algum destes sintomas?\n\n• Febre alta\n• Dificuldade para respirar\n• Dor no peito\n• Sangramento\n• Vômitos intensos\n• Desmaios\n\n(Responda: sim ou não)", "tipo": "sim_nao"},
    ]
    
    @staticmethod
    def iniciar_conversa(paciente_id):
        """Inicia uma nova conversa de triagem"""
        conversas_ativas[paciente_id] = {
            'etapa': 0,
            'respostas': {},
            'sintomas_coletados': [],
            'dados_vitais': {}
        }
        return SistemaTriagem.PERGUNTAS[0]['texto']
    
    @staticmethod
    def processar_resposta(paciente_id, resposta):
        """Processa a resposta do paciente e retorna próxima pergunta"""
        if paciente_id not in conversas_ativas:
            return SistemaTriagem.iniciar_conversa(paciente_id)
        
        conversa = conversas_ativas[paciente_id]
        etapa_atual = conversa['etapa']
        
        # Salva a resposta atual
        if etapa_atual < len(SistemaTriagem.PERGUNTAS):
            pergunta_atual = SistemaTriagem.PERGUNTAS[etapa_atual]
            conversa['respostas'][pergunta_atual['id']] = resposta
            conversa['sintomas_coletados'].append(resposta)
        
        # Avança para próxima etapa
        conversa['etapa'] += 1
        
        # Se ainda há perguntas, retorna a próxima
        if conversa['etapa'] < len(SistemaTriagem.PERGUNTAS):
            return SistemaTriagem.PERGUNTAS[conversa['etapa']]['texto']
        
        # Se terminou as perguntas, coleta sinais vitais
        if conversa['etapa'] == len(SistemaTriagem.PERGUNTAS):
            return "Agora vou verificar seus sinais vitais...\n\n📊 Medindo temperatura...\n💓 Medindo batimentos cardíacos...\n\n(Clique em 'Enviar' para continuar)"
        
        # Finaliza triagem
        return SistemaTriagem.finalizar_triagem(paciente_id)
    
    @staticmethod
    def coletar_sinais_vitais():
        """Simula coleta de sinais vitais (em produção viria dos sensores Arduino)"""
        return {
            'temperatura': round(random.uniform(36.0, 39.5), 1),
            'batimentos': random.randint(60, 120),
            'pressao_sistolica': random.randint(90, 160),
            'pressao_diastolica': random.randint(60, 100)
        }
    
    @staticmethod
    def calcular_prioridade(conversa):
        """Calcula prioridade baseada nas respostas e sinais vitais"""
        pontos = 0
        
        # Analisa nível de dor (pergunta 3)
        nivel_dor = conversa['respostas'].get(3, '0')
        try:
            dor = int(nivel_dor)
            if dor >= 8:
                pontos += 40
            elif dor >= 5:
                pontos += 25
            elif dor >= 3:
                pontos += 10
        except:
            pass
        
        # Analisa sintomas graves (pergunta 4)
        sintomas_graves = conversa['respostas'].get(4, '').lower()
        if 'sim' in sintomas_graves:
            pontos += 50
        
        # Analisa tempo de sintoma (pergunta 2)
        tempo = conversa['respostas'].get(2, '').lower()
        if 'hora' in tempo:
            pontos += 15
        
        # Analisa sinais vitais
        vitais = conversa['dados_vitais']
        
        # Temperatura
        if vitais.get('temperatura', 36.5) >= 39.0:
            pontos += 30
        elif vitais.get('temperatura', 36.5) >= 38.0:
            pontos += 15
        
        # Batimentos
        batimentos = vitais.get('batimentos', 75)
        if batimentos >= 110 or batimentos <= 50:
            pontos += 25
        elif batimentos >= 100 or batimentos <= 60:
            pontos += 10
        
        # Pressão
        pressao_s = vitais.get('pressao_sistolica', 120)
        if pressao_s >= 160 or pressao_s <= 90:
            pontos += 20
        
        # Define prioridade
        if pontos >= 80:
            return 'URGENTE', '🔴'
        elif pontos >= 50:
            return 'ALTA', '🟠'
        elif pontos >= 25:
            return 'MÉDIA', '🟡'
        else:
            return 'BAIXA', '🟢'
    
    @staticmethod
    def gerar_senha_chamada(prioridade):
        """Gera senha de chamada baseada na prioridade"""
        prefixos = {
            'URGENTE': 'U',
            'ALTA': 'A',
            'MÉDIA': 'M',
            'BAIXA': 'B'
        }
        prefixo = prefixos.get(prioridade, 'G')
        numero = random.randint(1, 999)
        return f"{prefixo}{numero:03d}"
    
    @staticmethod
    def finalizar_triagem(paciente_id):
        """Finaliza a triagem e salva no banco de dados"""
        conversa = conversas_ativas[paciente_id]
        
        # Coleta sinais vitais
        conversa['dados_vitais'] = SistemaTriagem.coletar_sinais_vitais()
        
        # Calcula prioridade
        prioridade, emoji = SistemaTriagem.calcular_prioridade(conversa)
        
        # Gera senha de chamada
        senha = SistemaTriagem.gerar_senha_chamada(prioridade)
        
        # Cria registro no banco
        vitais = conversa['dados_vitais']
        nivel_dor = conversa['respostas'].get(3, 0)
        
        try:
            nivel_dor = int(nivel_dor)
        except:
            nivel_dor = 0
        
        nova_consulta = Encounter(
            patient_id=paciente_id,
            sintomas='\n'.join(conversa['sintomas_coletados']),
            nivel_dor=nivel_dor,
            temperatura=vitais['temperatura'],
            batimentos=vitais['batimentos'],
            pressao_sistolica=vitais['pressao_sistolica'],
            pressao_diastolica=vitais['pressao_diastolica'],
            prioridade=prioridade,
            senha_chamada=senha,
            status='aguardando'
        )
        
        db.session.add(nova_consulta)
        db.session.commit()
        
        # Monta resposta final
        resposta_final = f"""
✅ Triagem concluída com sucesso!

📋 **RESUMO DA TRIAGEM**

{emoji} **Prioridade: {prioridade}**
🎫 **Senha de chamada: {senha}**

📊 **Sinais Vitais:**
• Temperatura: {vitais['temperatura']}°C
• Batimentos: {vitais['batimentos']} bpm
• Pressão: {vitais['pressao_sistolica']}/{vitais['pressao_diastolica']} mmHg
• Nível de dor: {nivel_dor}/10

📝 **Queixa principal:**
{conversa['respostas'].get(1, 'Não informado')}

⏱️ **Tempo estimado de espera:**
{SistemaTriagem.estimar_tempo_espera(prioridade)}

💡 **Orientações:**
{SistemaTriagem.gerar_orientacoes(prioridade)}

Aguarde a chamada da sua senha no painel. Obrigada por usar a AMÉLIA! 💙
"""
        
        # Limpa conversa
        del conversas_ativas[paciente_id]
        
        return resposta_final
    
    @staticmethod
    def estimar_tempo_espera(prioridade):
        """Estima tempo de espera baseado na prioridade"""
        tempos = {
            'URGENTE': 'Atendimento imediato',
            'ALTA': 'Aproximadamente 15-30 minutos',
            'MÉDIA': 'Aproximadamente 30-60 minutos',
            'BAIXA': 'Aproximadamente 1-2 horas'
        }
        return tempos.get(prioridade, 'Aguarde a chamada')
    
    @staticmethod
    def gerar_orientacoes(prioridade):
        """Gera orientações baseadas na prioridade"""
        if prioridade == 'URGENTE':
            return "Permaneça próximo ao balcão de atendimento. Em caso de piora, avise imediatamente a equipe."
        elif prioridade == 'ALTA':
            return "Permaneça na sala de espera. Se sentir piora dos sintomas, avise a recepção."
        else:
            return "Aguarde confortavelmente na sala de espera. Mantenha-se hidratado."
    
    @staticmethod
    def obter_historico(paciente_id):
        """Retorna histórico de conversas"""
        if paciente_id in conversas_ativas:
            return conversas_ativas[paciente_id]['sintomas_coletados']
        return []
    
    @staticmethod
    def resetar_conversa(paciente_id):
        """Reseta a conversa de um paciente"""
        if paciente_id in conversas_ativas:
            del conversas_ativas[paciente_id]