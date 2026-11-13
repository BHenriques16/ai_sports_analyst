import streamlit as st
import requests
import pandas as pd
import altair as alt

API_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Sports Scout", layout="wide")
st.title("🏀 AI Sports Scout")

st.sidebar.header("Administração")
if st.sidebar.button("Sincronizar Equipas/Jogadores"):
    with st.spinner("A sincronizar base de dados..."):
        resp = requests.post(f"{API_URL}/sync/rosters")
        st.sidebar.success(resp.json()["message"])
        st.cache_data.clear()

# --- FUNÇÕES DE LIGAÇÃO À API ---
@st.cache_data(ttl=600)
def fetch_players_data():
    try:
        resp = requests.get(f"{API_URL}/players")
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

@st.cache_data(ttl=600)
def fetch_team_names():
    try:
        resp = requests.get(f"{API_URL}/teams")
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

@st.cache_data(ttl=60)
def fetch_stats(name, opp=None):
    url = f"{API_URL}/player/{name}/stats"
    if opp and opp != "Todos":
        url += f"?opponent={opp}"
    return requests.get(url).json()

@st.cache_data(ttl=60)
def fetch_team_stats(name, opp=None):
    url = f"{API_URL}/team/{name}/stats"
    if opp and opp != "Todos":
        url += f"?opponent={opp}"
    return requests.get(url).json()

@st.cache_data(ttl=60)
def fetch_todays_games():
    try:
        resp = requests.get(f"{API_URL}/games/today")
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

players_data = fetch_players_data()
player_names = [p["name"] for p in players_data]
player_team_map = {p["name"]: p["team"] for p in players_data}

def format_player(name):
    if not name: return None
    team = player_team_map.get(name, 'FA')
    return f"{name} ({team})"

team_names = fetch_team_names()

# --- SISTEMA DE NAVEGAÇÃO (TABS) ---
tab_slate, tab1, tab2, tab3 = st.tabs([
    "📅 Slate (Jogos Hoje)",
    "👤 Player Props", 
    "🏟️ Team & Matchup Scout", 
    "⚔️ SGP (Same Game Parlays)"
])

# ==========================================
# TAB 0: SLATE (JOGOS DE HOJE)
# ==========================================
with tab_slate:
    st.subheader("📅 Jogos da Noite")
    
    games = fetch_todays_games()
    
    if not games or "error" in games:
        st.info("Sem jogos agendados para hoje ou a aguardar atualização da NBA.")
    else:
        cols = st.columns(3)
        for i, g in enumerate(games):
            with cols[i % 3].container(border=True):
                st.markdown(f"#### {g['away_abrv']} @ {g['home_abrv']}")
                if g['home_pts'] > 0 or g['away_pts'] > 0:
                    st.markdown(f"{g['away_name']}: **{g['away_pts']}**")
                    st.markdown(f"{g['home_name']}: **{g['home_pts']}**")
                    st.success(f"🔥 {g['status']}")
                else:
                    st.markdown(f"{g['away_name']}")
                    st.markdown(f"{g['home_name']}")
                    st.caption(f"🕒 {g['status']}")

# ==========================================
# TAB 1: PLAYER PROPS
# ==========================================
with tab1:
    search_name = st.selectbox("Pesquisa de Jogador", options=player_names, format_func=format_player, index=None, placeholder="Ex: Luka Doncic")

    if search_name:
        with st.spinner(f"A obter dados de {search_name}..."):
            full_data = fetch_stats(search_name)
            
        if "error" in full_data:
            st.error(full_data["error"])
        else:
            unique_opps = full_data["stats"].get("unique_opponents", [])
            opp_choice = st.selectbox("🎯 Filtrar por Adversário (Head-to-Head)", ["Todos"] + unique_opps, key="h2h_player")
            
            data = fetch_stats(search_name, opp_choice) if opp_choice != "Todos" else full_data
            p_name = data["player_name"]
            stats = data["stats"]
            
            st.header(format_player(p_name))
            if opp_choice != "Todos":
                st.caption(f"Histórico filtrado contra: **{opp_choice}**")
            
            st.markdown("##### Médias e Eficiência (Regular Season)")
            h1, h2, h3, h4, h5, h6 = st.columns(6)
            h1.metric("PPG", stats["season_avg"].get("pts", 0))
            h2.metric("RPG", stats["season_avg"].get("reb", 0))
            h3.metric("APG", stats["season_avg"].get("ast", 0))
            h4.metric("3PM (Triplos)", stats["season_avg"].get("fg3m", 0))
            h5.metric("FG%", f"{stats['season_avg'].get('fg_pct', 0)}%")
            h6.metric("3FG%", f"{stats['season_avg'].get('fg3_pct', 0)}%")
            
            st.divider()
            
            st.markdown("### ⚙️ Análise de Tendências e Over/Under")
            ctrl1, ctrl2, ctrl3 = st.columns(3)
            
            stat_map = {
                "Pontos": "pts", "Ressaltos": "reb", "Assistências": "ast", "Triplos Marcados": "fg3m", 
                "Roubos": "stl", "Desarmes": "blk", "Pts+Reb+Ast (PRA)": "pra", "Pts+Ast (PA)": "pa", 
                "Pts+Reb (PR)": "pr", "Ast+Reb (AR)": "ar", "Roubos+Desarmes (Stocks)": "bs"
            }
            
            stat_choice = ctrl1.selectbox("Estatística a analisar", list(stat_map.keys()))
            stat_key = stat_map[stat_choice]
            
            num_games_sel = ctrl2.selectbox("Analisar últimos X jogos", ["Todos", 5, 10, 20, 30, 50], index=2)
            
            default_line = float(stats["ou_analysis"][stat_key]["default_line"])
            ou_line = ctrl3.number_input("Linha de Over/Under", value=default_line, step=0.5)
            
            df = pd.DataFrame(stats["games_log"])
            
            if num_games_sel == "Todos":
                df_filtered = df.copy()
            else:
                df_filtered = df.head(int(num_games_sel)).copy()
                
            overs = (df_filtered[stat_key] > ou_line).sum()
            hit_rate = (overs / len(df_filtered)) * 100 if len(df_filtered) > 0 else 0
            badge = "🔥" if hit_rate >= 80 else "❄️" if hit_rate <= 30 else "📊"
            std_dev = df_filtered[stat_key].std()
            
            over_and_win = ((df_filtered[stat_key] > ou_line) & (df_filtered['wl'] == 'W')).sum() if 'wl' in df_filtered.columns else "N/A"
            
            st.markdown(f"**Performance: Amostra Selecionada ({len(df_filtered)} Jogos)**")
            col1, col2, col3, col4, col5 = st.columns(5)
            recent_avg = df_filtered[stat_key].mean()
            col1.metric("Média", round(recent_avg, 1), round(recent_avg - stats["season_avg"].get(stat_key, 0), 1))
            col2.metric(f"Overs (> {ou_line})", f"{overs} em {len(df_filtered)}")
            col3.metric(f"Taxa Acerto {badge}", f"{hit_rate:.1f}%")
            col4.metric("Volatilidade", round(std_dev, 1))
            col5.metric("Over + Vitória", f"{over_and_win} jogos")
            
            df_chart = df_filtered.iloc[::-1].copy()
            bars = alt.Chart(df_chart).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X('game_date:T', title='Data', axis=alt.Axis(format='%d %b', labelAngle=-45)),
                y=alt.Y(f'{stat_key}:Q', title=stat_choice),
                color=alt.condition(alt.datum[stat_key] > ou_line, alt.value('#10b981'), alt.value('#ef4444')),
                tooltip=[alt.Tooltip('game_date:T', title='Data'), alt.Tooltip('matchup:N', title='Jogo'), 
                         alt.Tooltip(f'{stat_key}:Q', title=stat_choice), alt.Tooltip('wl:N', title='Resultado (W/L)')]
            )
            rule = alt.Chart(pd.DataFrame({'line': [ou_line]})).mark_rule(color='white', strokeWidth=2, strokeDash=[5, 5]).encode(y='line:Q')
            st.altair_chart((bars + rule).properties(height=400), use_container_width=True)
            
            with st.expander("Ver Registo de Jogos (Tabela)"):
                display_cols = ['game_date', 'matchup', 'wl', 'home_away', 'is_b2b', 'minutes', 'pts', 'reb', 'ast', 'fg3m', 'pra']
                available_cols = [c for c in display_cols if c in df_filtered.columns]
                st.dataframe(df_filtered[available_cols], use_container_width=True)

# ==========================================
# TAB 2: TEAM & MATCHUP SCOUT
# ==========================================
with tab2:
    st.subheader("🏟️ Team Scout (Moneyline & Totais)")
    team_search = st.selectbox("Pesquisa de Equipa", options=team_names, index=None, placeholder="Ex: Boston Celtics", key="team_search")

    if team_search:
        with st.spinner(f"A obter dados de {team_search}..."):
            full_t_data = fetch_team_stats(team_search)
            
        if "error" in full_t_data:
            st.error(full_t_data["error"])
        else:
            unique_t_opps = full_t_data["stats"].get("unique_opponents", [])
            opp_t_choice = st.selectbox("🎯 Filtrar por Adversário (H2H Equipa)", ["Todos"] + unique_t_opps, key="h2h_team")
            
            t_data = fetch_team_stats(team_search, opp_t_choice) if opp_t_choice != "Todos" else full_t_data
            t_name = t_data["team_name"]
            t_stats = t_data["stats"]
            
            st.header(t_name)
            if opp_t_choice != "Todos":
                st.caption(f"Histórico filtrado apenas contra: **{opp_t_choice}**")
            
            st.markdown("##### Visão Geral (Regular Season)")
            
            # AGORA SEMPRE FIXO COM 4 COLUNAS!
            th1, th2, th3, th4 = st.columns(4)
            th1.metric("Win Rate (%)", f"{t_stats['season_avg'].get('win_rate', 0)}%")
            th2.metric("PPG (Pontos da Equipa)", round(t_stats['season_avg'].get('pts', 0), 1))
            th3.metric("Pontos Sofridos", round(t_stats['season_avg'].get('opp_pts', 0), 1))
            th4.metric("Total Jogo (Ambas as Equipas)", round(t_stats['season_avg'].get('total_pts', 0), 1))
            
            st.divider()

            if opp_t_choice != "Todos":
                st.markdown(f"### 🥊 Últimos Confrontos vs {opp_t_choice}")
                h2h_df = pd.DataFrame(t_stats["games_log"])
                
                if not h2h_df.empty:
                    for idx, row in h2h_df.head(5).iterrows():
                        with st.container(border=True):
                            c1, c2, c3, c4 = st.columns([1.5, 2.5, 2.5, 2])
                            c1.markdown(f"📅 **{row['game_date']}**")
                            c2.markdown(f"🏟️ {row['matchup']}")
                            
                            if row['wl'] == 'W':
                                res_text = f"🟢 **Vitória** ({row['pts']} - {row['opp_pts']})"
                            else:
                                res_text = f"🔴 **Derrota** ({row['pts']} - {row['opp_pts']})"
                            
                            c3.markdown(res_text)
                            
                            if row['opp_pts'] > 0:
                                c4.markdown(f"🔢 **Total: {row['total_pts']} pts**")
                            else:
                                c4.markdown("*(Adversário não sincronizado na DB)*")
                st.divider()
            
            st.markdown("### 🏠 Casa vs ✈️ Fora (Splits)")
            sc1, sc2 = st.columns(2)
            
            home_splits = t_stats["splits"].get("Home", {})
            away_splits = t_stats["splits"].get("Away", {})
            
            with sc1:
                st.info("**Registo em Casa**")
                st.metric("Taxa de Vitória (Casa)", f"{home_splits.get('win_rate', 0)}%")
                st.metric("Pontos Marcados", round(home_splits.get('pts', 0), 1))
                
            with sc2:
                st.warning("**Registo Fora**")
                st.metric("Taxa de Vitória (Fora)", f"{away_splits.get('win_rate', 0)}%")
                st.metric("Pontos Marcados", round(away_splits.get('pts', 0), 1))
                
            st.divider()
            
            st.markdown("### 📊 Forma Recente (Pontos e Resultados)")
            df_t = pd.DataFrame(t_stats["games_log"])
            
            num_t_games_sel = st.selectbox("Analisar últimos X jogos (Equipa)", ["Todos", 5, 10, 20, 30], index=1)
            
            if num_t_games_sel == "Todos":
                df_t_filtered = df_t.copy()
            else:
                df_t_filtered = df_t.head(int(num_t_games_sel)).copy()
                
            df_t_chart = df_t_filtered.iloc[::-1].copy()
            
            bars_t = alt.Chart(df_t_chart).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X('game_date:T', title='Data', axis=alt.Axis(format='%d %b', labelAngle=-45)),
                y=alt.Y('pts:Q', title='Pontos Marcados pela Equipa'),
                color=alt.condition(alt.datum.wl == 'W', alt.value('#10b981'), alt.value('#ef4444')),
                tooltip=[alt.Tooltip('game_date:T', title='Data'), alt.Tooltip('matchup:N', title='Jogo'),
                         alt.Tooltip('pts:Q', title='Pontos'), alt.Tooltip('wl:N', title='Resultado')]
            )
            st.altair_chart(bars_t.properties(height=400), use_container_width=True)
            
            with st.expander("Ver Registo de Jogos (Tabela)"):
                st.dataframe(df_t_filtered[['game_date', 'matchup', 'wl', 'home_away', 'pts', 'opp_pts', 'total_pts', 'reb', 'ast', 'fg3m', 'tov']], use_container_width=True)

# ==========================================
# TAB 3: CONSTRUTOR SGP (SAME GAME PARLAYS)
# ==========================================
with tab3:
    st.subheader("⚔️ Construtor SGP (Same Game Parlays)")
    st.markdown("Combina linhas de dois jogadores da **mesma equipa** no **mesmo jogo** para descobrir a taxa de acerto real e as Odds Justas da aposta combinada.")
    
    c1, c2 = st.columns(2)
    p1_name = c1.selectbox("Jogador 1", options=player_names, format_func=format_player, index=None, key="sgp_p1")
    
    p1_team = player_team_map.get(p1_name) if p1_name else None
    p2_options = [p for p in player_names if player_team_map.get(p) == p1_team and p != p1_name] if p1_team else []
    
    p2_name = c2.selectbox(
        f"Jogador 2 {f'(Filtro: {p1_team})' if p1_team else ''}", 
        options=p2_options, 
        format_func=format_player, 
        index=None, 
        key="sgp_p2", 
        disabled=not p1_name
    )
    
    if p1_name and p2_name:
        with st.spinner("A cruzar os registos dos jogos em comum..."):
            d1 = fetch_stats(p1_name)
            d2 = fetch_stats(p2_name)
            
        if "error" in d1 or "error" in d2:
            st.error("Erro ao carregar dados dos jogadores.")
        else:
            st.markdown("### 🎯 Definir Aposta Combinada")
            stat_map_combo = {"Pontos": "pts", "Ressaltos": "reb", "Assistências": "ast", "Triplos": "fg3m", "PRA": "pra"}
            
            cc1, cc2 = st.columns(2)
            with cc1:
                st.markdown(f"**Mercado para {p1_name}**")
                stat_c1 = st.selectbox("Estatística", list(stat_map_combo.keys()), key="sgp_s1", label_visibility="collapsed")
                stat_k1 = stat_map_combo[stat_c1]
                line_1 = st.number_input("Linha Over", value=15.5, step=0.5, key="sgp_l1")
                
            with cc2:
                st.markdown(f"**Mercado para {p2_name}**")
                stat_c2 = st.selectbox("Estatística", list(stat_map_combo.keys()), key="sgp_s2", label_visibility="collapsed")
                stat_k2 = stat_map_combo[stat_c2]
                line_2 = st.number_input("Linha Over", value=5.5, step=0.5, key="sgp_l2")
            
            num_games_sgp = st.selectbox("Amostra de Jogos em Comum", ["Todos", 10, 20, 30], index=1)
            
            df1 = pd.DataFrame(d1["stats"]["games_log"])
            df2 = pd.DataFrame(d2["stats"]["games_log"])
            
            if "game_id" not in df1.columns or "game_id" not in df2.columns:
                st.error("Erro: O backend não devolveu o ID do jogo. Garante que atualizaste o stats_engine.py!")
            else:
                df_merged = pd.merge(
                    df1[['game_id', 'game_date', 'matchup', stat_k1]], 
                    df2[['game_id', stat_k2]], 
                    on="game_id", 
                    suffixes=('_p1', '_p2')
                )
                df_merged = df_merged.sort_values(by="game_date", ascending=False)
                
                if num_games_sgp != "Todos":
                    df_merged = df_merged.head(int(num_games_sgp))
                
                total_games = len(df_merged)
                
                if total_games == 0:
                    st.warning("Não há histórico recente onde ambos os jogadores tenham jogado na mesma partida.")
                else:
                    col_p1 = f"{stat_k1}_p1"
                    col_p2 = f"{stat_k2}_p2"
                    
                    df_merged['Hit_P1'] = df_merged[col_p1] > line_1
                    df_merged['Hit_P2'] = df_merged[col_p2] > line_2
                    df_merged['SGP_Hit'] = df_merged['Hit_P1'] & df_merged['Hit_P2']
                    
                    hr1 = df_merged['Hit_P1'].mean()
                    hr2 = df_merged['Hit_P2'].mean()
                    sgp_hr = df_merged['SGP_Hit'].mean()
                    fair_odds = 1 / sgp_hr if sgp_hr > 0 else 0
                    
                    st.divider()
                    st.markdown("### 📊 Resultados do Same Game Parlay")
                    
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.metric(f"{p1_name} (> {line_1} {stat_c1})", f"{(hr1*100):.1f}%", f"{df_merged['Hit_P1'].sum()} / {total_games}")
                    rc2.metric(f"{p2_name} (> {line_2} {stat_c2})", f"{(hr2*100):.1f}%", f"{df_merged['Hit_P2'].sum()} / {total_games}")
                    
                    rc3.info("**Combinada (Bateram JUNTOS)**")
                    rc3.metric("Probabilidade Real", f"{(sgp_hr*100):.1f}%")
                    rc3.metric("Odd Justa (Fair Value)", f"{fair_odds:.2f}" if fair_odds > 0 else "N/A")
                    
                    with st.expander("Ver Registo de Jogos (Apenas Jogos em Comum)"):
                        st.dataframe(
                            df_merged[['game_date', 'matchup', col_p1, col_p2, 'SGP_Hit']]
                            .rename(columns={col_p1: f"{p1_name} ({stat_c1})", col_p2: f"{p2_name} ({stat_c2})", "SGP_Hit": "Combinada Bateu?"}),
                            use_container_width=True
                        )