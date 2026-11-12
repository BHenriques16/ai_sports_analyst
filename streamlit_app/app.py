import streamlit as st
import requests
import pandas as pd
import altair as alt

API_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Sports Scout MVP", layout="wide")
st.title("🏀 AI Sports Scout - Player Scout")

st.sidebar.header("Administração")
if st.sidebar.button("Sincronizar Equipas/Jogadores"):
    with st.spinner("A sincronizar base de dados..."):
        resp = requests.post(f"{API_URL}/sync/rosters")
        st.sidebar.success(resp.json()["message"])

@st.cache_data(ttl=600)
def fetch_player_names():
    try:
        resp = requests.get(f"{API_URL}/players")
        if resp.status_code == 200:
            return resp.json()
    except:
        return []

player_names = fetch_player_names()

search_name = st.selectbox(
    "Pesquisa de Jogador",
    options=player_names,
    index=None,
    placeholder="Começa a escrever aqui... (ex: Luka)"
)

# Função em cache para gerir as chamadas à API com o filtro de adversário
@st.cache_data(ttl=60)
def fetch_stats(name, opp=None):
    url = f"{API_URL}/player/{name}/stats"
    if opp and opp != "Todos":
        url += f"?opponent={opp}"
    return requests.get(url).json()

if search_name:
    with st.spinner(f"A obter dados de {search_name}..."):
        full_data = fetch_stats(search_name)
        
    if "error" in full_data:
        st.error(full_data["error"])
    else:
        unique_opps = full_data["stats"].get("unique_opponents", [])
        
        # Filtro de H2H (Adversário) logo abaixo do nome
        opp_choice = st.selectbox("🎯 Filtrar por Adversário (Head-to-Head)", ["Todos"] + unique_opps)
        
        if opp_choice != "Todos":
            data = fetch_stats(search_name, opp_choice)
        else:
            data = full_data
        
        p_name = data["player_name"]
        stats = data["stats"]
        
        st.header(f"{p_name}")
        if opp_choice != "Todos":
            st.caption(f"A mostrar histórico filtrado apenas contra: **{opp_choice}**")
        
        # --- 1. CABEÇALHO: VISÃO GERAL ---
        st.markdown("##### Médias (Amostra Atual)")
        h1, h2, h3, h4, h5, h6 = st.columns(6)
        h1.metric("PPG", stats["season_avg"]["pts"])
        h2.metric("RPG", stats["season_avg"]["reb"])
        h3.metric("APG", stats["season_avg"]["ast"])
        h4.metric("SPG", stats["season_avg"]["stl"])
        h5.metric("BPG", stats["season_avg"]["blk"])
        h6.metric("MPG", stats["season_avg"]["minutes"])
        
        st.divider()
        
        # --- 2. PAINEL DE CONTROLOS INTERATIVOS ---
        st.markdown("### ⚙️ Análise de Tendências e Over/Under")
        ctrl1, ctrl2, ctrl3 = st.columns(3)
        
        stat_map = {
            "Pontos": "pts", 
            "Ressaltos": "reb", 
            "Assistências": "ast", 
            "Roubos de Bola": "stl", 
            "Desarmes (Blocks)": "blk",
            "Pontos + Ressaltos + Assistências (PRA)": "pra",
            "Pontos + Assistências (PA)": "pa",
            "Pontos + Ressaltos (PR)": "pr",
            "Assistências + Ressaltos (AR)": "ar",
            "Roubos + Desarmes (Stocks)": "bs"
        }
        
        stat_choice = ctrl1.selectbox("Estatística a analisar", list(stat_map.keys()))
        stat_key = stat_map[stat_choice]
        
        num_games = ctrl2.selectbox("Analisar últimos X jogos", [10, 20, 30, 50], index=1)
        
        default_line = float(stats["ou_analysis"][stat_key]["default_line"])
        ou_line = ctrl3.number_input("Linha de Over/Under", value=default_line, step=0.5)
        
        # --- CÁLCULOS DINÂMICOS DA UI ---
        df = pd.DataFrame(stats["games_log"])
        df_filtered = df.head(num_games).copy()
        
        overs = (df_filtered[stat_key] > ou_line).sum()
        hit_rate = (overs / len(df_filtered)) * 100 if len(df_filtered) > 0 else 0
        
        if hit_rate >= 80:
            badge = "🔥"
        elif hit_rate <= 30:
            badge = "❄️"
        else:
            badge = "📊"
        
        std_dev = df_filtered[stat_key].std()
        
        # --- MÉTRICAS RECENTES ---
        st.markdown(f"**Performance: Últimos {len(df_filtered)} Jogos da amostra**")
        col1, col2, col3, col4 = st.columns(4)
        
        recent_avg = df_filtered[stat_key].mean()
        delta_val = round(recent_avg - stats["season_avg"][stat_key], 1)
        
        col1.metric(f"Média", round(recent_avg, 1), delta=delta_val)
        col2.metric(f"Overs (> {ou_line})", f"{overs} em {len(df_filtered)}")
        col3.metric(f"Taxa Acerto {badge}", f"{hit_rate:.1f}%")
        col4.metric(f"Volatilidade", round(std_dev, 1))
        
        # --- SPLITS (Casa vs Fora e B2B) ---
        st.markdown(f"**Contexto (Média da Amostra - {stat_choice})**")
        split_h = stats.get("splits", {}).get("Home", {}).get(stat_key, 0)
        split_a = stats.get("splits", {}).get("Away", {}).get(stat_key, 0)
        
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("🏠 Em Casa", split_h)
        sc2.metric("✈️ Fora", split_a)
        
        b2b_games = df[df['is_b2b'] == True]
        if not b2b_games.empty:
            b2b_avg = b2b_games[stat_key].mean()
            sc3.metric(" خ Back-to-Back", round(b2b_avg, 1))
        else:
            sc3.metric(" خ Back-to-Back", "N/A")
        
        # --- GRÁFICO INTERATIVO COM CORES CONDICIONAIS ---
        df_chart = df_filtered.iloc[::-1].copy()
        
        bars = alt.Chart(df_chart).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X('game_date:T', title='Data', axis=alt.Axis(format='%d %b', labelAngle=-45)),
            y=alt.Y(f'{stat_key}:Q', title=stat_choice),
            color=alt.condition(
                alt.datum[stat_key] > ou_line,
                alt.value('#10b981'),  
                alt.value('#ef4444')   
            ),
            tooltip=[
                alt.Tooltip('game_date:T', title='Data'),
                alt.Tooltip('matchup:N', title='Jogo'),
                alt.Tooltip(f'{stat_key}:Q', title=stat_choice),
                alt.Tooltip('home_away:N', title='Local'),
                alt.Tooltip('is_b2b:N', title='B2B?')
            ]
        )
        
        rule = alt.Chart(pd.DataFrame({'line': [ou_line]})).mark_rule(color='white', strokeWidth=2, strokeDash=[5, 5]).encode(
            y='line:Q'
        )
        
        st.altair_chart((bars + rule).properties(height=400), use_container_width=True)
        
        # --- TABELA DE DADOS BRUTOS ---
        with st.expander("Ver Registo de Jogos (Tabela)"):
            display_cols = ['game_date', 'matchup', 'home_away', 'is_b2b', 'minutes', 'pts', 'reb', 'ast', 'stl', 'blk', 'pra', 'pa', 'pr', 'ar', 'bs']
            st.dataframe(df_filtered[display_cols], use_container_width=True)