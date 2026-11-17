import requests

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"

def generate_player_report(player_name: str, stat_choice: str, stat_key: str, ou_line: float, ou_direction: str, stats_data: dict):
    
    season_avg = stats_data.get('season_avg', {}).get(stat_key, 0)
    l10_avg = stats_data.get('last_10_avg', {}).get(stat_key, 0)
    l5_avg = stats_data.get('last_5_avg', {}).get(stat_key, 0)
    
    home_avg = stats_data.get('splits', {}).get('Home', {}).get(stat_key, 0)
    away_avg = stats_data.get('splits', {}).get('Away', {}).get(stat_key, 0)

    system_prompt = """És um analista de dados desportivos profissional e especialista em apostas na NBA (Player Props).
O teu objetivo é analisar as estatísticas fornecidas e redigir um relatório de scouting tático e preditivo focado no valor da aposta proposta (Over ou Under).
Regras absolutas:
1. Baseia-te EXCLUSIVAMENTE nos números fornecidos. NÃO inventes estatísticas passadas nem factos.
2. Usa um tom assertivo, frio e profissional (estilo apostador sharp).
3. Estrutura a resposta de forma limpa, com os seguintes pontos:
   - 📈 Tendência de Forma (Análise do momento recente vs Época)
   - 🏠 Contexto Casa/Fora (Como é que jogar em casa/fora afeta o jogador)
   - 🎯 Veredito de Aposta (Avalia se há valor na linha e direção selecionadas ou se é melhor evitar, justificando o risco)."""

    user_prompt = f"""
Analisa o mercado de '{stat_choice}' para o jogador {player_name}.
Aposta em análise: {ou_direction} {ou_line}

DADOS MATEMÁTICOS TOTAIS:
- Média da Época Regular: {season_avg}
- Média dos Últimos 10 Jogos: {l10_avg}
- Média dos Últimos 5 Jogos: {l5_avg}
- Média a Jogar em Casa: {home_avg}
- Média a Jogar Fora: {away_avg}

Com base apenas nestes números, redige o teu AI Scout Report em Português de Portugal avaliando especificamente a entrada no {ou_direction} {ou_line}.
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num:predict": 2048
        }
    }
    
    try:
        # Aumentado para 300 segundos
        response = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=300)
        response.raise_for_status()
        return response.json().get("response", "Erro: Resposta vazia do modelo.")
    except Exception as e:
        return f"Erro de comunicação com o Ollama. Garante que correste o modelo no terminal. Erro Técnico: {e}"

def chat_with_agent(messages: list, slate_context: str):
    system_prompt = f"""És um assistente virtual especializado em apostas desportivas e análise tática da NBA.
O teu objetivo é ajudar o utilizador a encontrar valor em apostas (Player Props, Totais de Jogo, Matchups).
Responde sempre em Português de Portugal, com um tom profissional, analítico e direto.

CONTEXTO DOS JOGOS DE HOJE (SLATE):
{slate_context}

Usa esta informação dos jogos de hoje para contextualizar as tuas respostas sempre que o utilizador perguntar sobre a jornada atual. Se recomendares uma aposta, explica de forma lógica o porquê."""

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "model": MODEL_NAME,
        "messages": full_messages,
        "stream": False,
        "options": {
            "temperature": 0.4
        }
    }
    
    try:
        # Aumentado para 300 segundos
        response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=300)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "Erro: Resposta vazia do modelo.")
    except Exception as e:
        return f"Erro de comunicação com o Ollama no modo Chat. Erro Técnico: {e}"