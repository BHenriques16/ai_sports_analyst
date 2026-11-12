import streamlit as st
import requests
import pandas as pd

API_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Sports Scout MVP", layout="wide")
st.title("🏀 AI Sports Scout - Test Dashboard")

st.sidebar.header("Administração (Ingestão)")
if st.sidebar.button("1. Sincronizar Equipas/Jogadores"):
    resp = requests.post(f"{API_URL}/sync/rosters")
    st.sidebar.success(resp.json()["message"])

# Jayson Tatum ID = 1628369 (Exemplo)
player_id_input = st.sidebar.text_input("Player ID para fetch stats (Ex: 1628369 para Tatum)")
if st.sidebar.button("2. Sincronizar Stats do Jogador"):
    if player_id_input:
        resp = requests.post(f"{API_URL}/sync/player_stats/{player_id_input}")
        st.sidebar.success(resp.json()["message"])

st.header("Análise de Jogador")
search_name = st.text_input("Pesquisar Jogador (Ex: Jayson Tatum)")

if search_name:
    resp = requests.get(f"{API_URL}/player/{search_name}/stats")
    data = resp.json()
    
    if "error" in data:
        st.error("Jogador não encontrado na BD ou sem dados.")
    else:
        st.subheader(f"Últimos jogos de {data['player']}")
        
        # Converter para Pandas para visualização fácil no Streamlit
        df = pd.DataFrame(data['last_10_games'])
        if not df.empty:
            df = df[['game_date', 'matchup', 'minutes', 'pts', 'reb', 'ast', 'fgm', 'fga']]
            st.dataframe(df)
            
            st.subheader("Tendência de Pontos")
            st.line_chart(df.set_index('game_date')['pts'])
        else:
            st.warning("Sem jogos registados. Faz a sincronização primeiro!")