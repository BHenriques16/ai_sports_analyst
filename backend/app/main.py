import sys
import os
import urllib.parse
from datetime import datetime, timedelta
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import engine, Base, get_db
from app.db.models import Player, Team, PlayerGameStat, TeamGameStat
from app.ingestion.nba_fetcher import sync_teams_and_players, fetch_player_gamelogs, fetch_team_gamelogs
from app.stats.stats_engine import calculate_player_stats, calculate_team_stats
from nba_api.stats.endpoints import scoreboardv2
from app.ai.llm_scout import generate_player_report, chat_with_agent

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Sports Scout API")

LAST_FETCHED = {}

def should_update_entity(entity_key: str, latest_game_date, hours_cooldown: int = 6) -> bool:
    now = datetime.now()
    last_fetch = LAST_FETCHED.get(entity_key)
    
    if last_fetch and (now - last_fetch < timedelta(hours=hours_cooldown)):
        return False
        
    if not latest_game_date:
        return True
        
    if latest_game_date >= (now.date() - timedelta(days=1)):
        LAST_FETCHED[entity_key] = now
        return False
        
    return True

@app.post("/sync/rosters")
def sync_rosters(db: Session = Depends(get_db)):
    sync_teams_and_players(db)
    all_teams = db.query(Team).all()
    for t in all_teams:
        last_update = LAST_FETCHED.get(f"T_{t.id}")
        if not last_update or datetime.now() - last_update > timedelta(hours=6):
            fetch_team_gamelogs(t.id, db)
            LAST_FETCHED[f"T_{t.id}"] = datetime.now()
                
    return {"message": "Base de Dados a 100%! Calendários de todas as equipas sincronizados."}

@app.get("/players")
def get_all_players(db: Session = Depends(get_db)):
    results = db.query(Player.full_name, Team.abbreviation)\
                .outerjoin(Team, Player.team_id == Team.id)\
                .filter(Player.is_active == 1)\
                .order_by(Player.full_name).all()
    return [{"name": r[0], "team": r[1] if r[1] else "FA"} for r in results]

@app.get("/teams")
def get_all_teams(db: Session = Depends(get_db)):
    teams = db.query(Team.full_name).order_by(Team.full_name).all()
    return [t[0] for t in teams]

@app.get("/games/today")
def get_todays_games():
    try:
        now = datetime.now() - timedelta(hours=8) 
        
        for offset in range(3):
            target_date = now + timedelta(days=offset)
            date_str = target_date.strftime('%Y-%m-%d')
            
            board = scoreboardv2.ScoreboardV2(game_date=date_str)
            headers = board.game_header.get_data_frame()
            
            if headers.empty:
                continue
                
            if offset == 0 and all(headers['GAME_STATUS_ID'] == 3):
                continue
                
            lines = board.line_score.get_data_frame()
            result = []
            
            for _, game in headers.iterrows():
                home_id = game['HOME_TEAM_ID']
                away_id = game['VISITOR_TEAM_ID']
                
                home_rows = lines[lines['TEAM_ID'] == home_id]
                away_rows = lines[lines['TEAM_ID'] == away_id]
                
                if home_rows.empty or away_rows.empty:
                    continue
                    
                home_line = home_rows.iloc[0]
                away_line = away_rows.iloc[0]
                
                home_pts = home_line['PTS'] if pd.notna(home_line['PTS']) else 0
                away_pts = away_line['PTS'] if pd.notna(away_line['PTS']) else 0
                
                result.append({
                    "home_abrv": home_line['TEAM_ABBREVIATION'],
                    "home_name": f"{home_line['TEAM_CITY_NAME']} {home_line['TEAM_NAME']}",
                    "home_pts": int(home_pts),
                    "away_abrv": away_line['TEAM_ABBREVIATION'],
                    "away_name": f"{away_line['TEAM_CITY_NAME']} {away_line['TEAM_NAME']}",
                    "away_pts": int(away_pts),
                    "status": game['GAME_STATUS_TEXT']
                })
            return result
            
        return {"error": "Sem jogos agendados para os próximos dias."}
    except Exception as e:
        return {"error": str(e)}

@app.get("/player/{player_name}/stats")
def get_player_stats(player_name: str, opponent: str = None, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.full_name.ilike(f"%{player_name}%")).first()
    if not player:
        return {"error": f"Jogador '{player_name}' não encontrado."}
    
    latest_date = db.query(func.max(PlayerGameStat.game_date))\
                    .filter(PlayerGameStat.player_id == player.id).scalar()
                    
    if should_update_entity(f"P_{player.id}", latest_date):
        fetch_player_gamelogs(player.id, db)
        LAST_FETCHED[f"P_{player.id}"] = datetime.now()
            
    stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).all()
    if not stats:
        return {"error": "Não foram encontrados jogos."}
        
    return {
        "player_name": player.full_name,
        "stats": calculate_player_stats(stats, target_opponent=opponent)
    }

@app.get("/team/{team_name}/stats")
def get_team_stats(team_name: str, opponent: str = None, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.full_name.ilike(f"%{team_name}%")).first()
    if not team:
        return {"error": f"Equipa '{team_name}' não encontrada."}
    
    latest_team_date = db.query(func.max(TeamGameStat.game_date))\
                         .filter(TeamGameStat.team_id == team.id).scalar()
                         
    if should_update_entity(f"T_{team.id}", latest_team_date):
        fetch_team_gamelogs(team.id, db)
        LAST_FETCHED[f"T_{team.id}"] = datetime.now()

    if opponent and opponent != "Todos":
        opp_team = db.query(Team).filter(Team.full_name == opponent).first()
        if opp_team:
            latest_opp_date = db.query(func.max(TeamGameStat.game_date))\
                                .filter(TeamGameStat.team_id == opp_team.id).scalar()
            if should_update_entity(f"T_{opp_team.id}", latest_opp_date):
                fetch_team_gamelogs(opp_team.id, db)
                LAST_FETCHED[f"T_{opp_team.id}"] = datetime.now()

    stats = db.query(TeamGameStat).filter(TeamGameStat.team_id == team.id).all()
    if not stats:
        return {"error": "Não foram encontrados jogos para esta equipa."}
    
    game_ids = [g.game_id for g in stats]
    opp_stats = db.query(TeamGameStat.game_id, TeamGameStat.pts).filter(
        TeamGameStat.game_id.in_(game_ids),
        TeamGameStat.team_id != team.id
    ).all()
    opp_pts_map = {row.game_id: row.pts for row in opp_stats}
        
    processed_stats = calculate_team_stats(stats, opp_pts_map, target_opponent=opponent)
    
    if not processed_stats:
        return {"error": f"Sem dados H2H contra {opponent}."}
        
    return {
        "team_name": team.full_name,
        "stats": processed_stats
    }


# ==========================================
# ROTA: SCANNER DE SUGESTÕES DO DIA (Unders Fixos & Overs por Patamares)
# ==========================================
@app.get("/scout/nuggets")
def get_golden_nuggets(db: Session = Depends(get_db)):
    games = get_todays_games()
    if isinstance(games, dict) and "error" in games:
        return {"nuggets": []}
        
    team_to_game = {}
    playing_abrvs = []
    
    for g in games:
        game_title = f"{g['away_abrv']} @ {g['home_abrv']}"
        team_to_game[g['away_abrv']] = game_title
        team_to_game[g['home_abrv']] = game_title
        playing_abrvs.extend([g['away_abrv'], g['home_abrv']])
        
    teams = db.query(Team).filter(Team.abbreviation.in_(playing_abrvs)).all()
    team_id_to_abrv = {t.id: t.abbreviation for t in teams}
    team_ids = list(team_id_to_abrv.keys())
    
    players = db.query(Player).filter(Player.team_id.in_(team_ids), Player.is_active == 1).all()
    
    game_nuggets = {team_to_game[abrv]: [] for abrv in playing_abrvs}
    
    target_stats = {
        "pts": "Pontos", "reb": "Ressaltos", "ast": "Assistências", 
        "pra": "Pontos + Ressaltos + Assistências", "pr": "Pontos + Ressaltos", 
        "pa": "Pontos + Assistências", "ar": "Assistências + Ressaltos",
        "fg3m": "Triplos Marcados"
    }
    
    min_thresholds = {
        "pts": 8.0, "reb": 3.5, "ast": 2.5, "pra": 15.0, 
        "pr": 10.0, "pa": 10.0, "ar": 8.0, "fg3m": 2.2
    }
    
    for p in players:
        p_stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == p.id).all()
        if not p_stats or len(p_stats) < 10:
            continue
            
        processed = calculate_player_stats(p_stats)
        if not processed or "games_log" not in processed:
            continue
            
        if processed["season_avg"].get("minutes", 0) < 20:
            continue
            
        df = pd.DataFrame(processed["games_log"])
        total_games = len(df)
        
        p_team_abrv = team_id_to_abrv.get(p.team_id)
        if not p_team_abrv:
            continue
        game_title = team_to_game[p_team_abrv]
        
        for stat_key, stat_name in target_stats.items():
            season_avg = processed["season_avg"].get(stat_key, 0)
            
            if season_avg < min_thresholds.get(stat_key, 0):
                continue
                
            if stat_key not in processed.get("ou_analysis", {}):
                continue
            
            link_url = f"/?player={urllib.parse.quote(p.full_name)}"
            player_link_md = f"[{p.full_name}]({link_url})"
            
            default_line = float(processed["ou_analysis"][stat_key]["default_line"])
            
            # ==========================================
            # 1. LOGICA DOS UNDERS (Sempre baseada na Média/Main Line)
            # ==========================================
            unders = int((df[stat_key] < default_line).sum())
            under_rate = unders / total_games
            if under_rate >= 0.75:
                text = f"- 🔴 **{player_link_md}** ({p_team_abrv}) | {stat_name}: **UNDER {default_line}** *(Acertou {unders}/{total_games} → {under_rate*100:.1f}%)*"
                game_nuggets[game_title].append((under_rate, text))

            # ==========================================
            # 2. LOGICA DOS OVERS (Patamares/Alternate Lines)
            # ==========================================
            over_lines_to_check = []
            
            if stat_key == "pts":
                if season_avg >= 24.5: over_lines_to_check = [19.5, 24.5, 29.5]
                elif season_avg >= 19.5: over_lines_to_check = [14.5, 19.5, 24.5]
                elif season_avg >= 14.5: over_lines_to_check = [9.5, 14.5, 19.5]
                elif season_avg >= 9.5: over_lines_to_check = [9.5, 14.5]
            elif stat_key in ["reb", "ast"]:
                if season_avg >= 10.5: over_lines_to_check = [8.5, 10.5, 12.5]
                elif season_avg >= 8.5: over_lines_to_check = [6.5, 8.5, 10.5]
                elif season_avg >= 6.5: over_lines_to_check = [4.5, 6.5, 8.5]
                elif season_avg >= 4.5: over_lines_to_check = [2.5, 4.5, 6.5]
                elif season_avg >= 2.5: over_lines_to_check = [2.5, 4.5]
            else:
                # Combinadas mantêm a default_line
                over_lines_to_check = [default_line]
                
            valid_overs = []
            best_over_rate = 0
            
            for line in over_lines_to_check:
                overs = int((df[stat_key] > line).sum())
                rate = overs / total_games
                if rate >= 0.75:
                    valid_overs.append(f"**OVER {line}** *({overs}/{total_games} → {rate*100:.1f}%)*")
                    if rate > best_over_rate:
                        best_over_rate = rate
                        
            if valid_overs:
                tiers_str = " | ".join(valid_overs)
                text = f"- 🟢 **{player_link_md}** ({p_team_abrv}) | {stat_name}: {tiers_str}"
                game_nuggets[game_title].append((best_over_rate, text))
                
    # ==========================================
    # FORMATAÇÃO VISUAL DIRETA PARA O CHAT
    # ==========================================
    final_nuggets = []
    for game_title, nuggets_list in game_nuggets.items():
        if nuggets_list:
            nuggets_list.sort(key=lambda x: x[0], reverse=True)
            top_10 = nuggets_list[:10]
            
            final_nuggets.append(f"\n### 🏀 {game_title}\n")
            for _, text in top_10:
                final_nuggets.append(text)
                
    return {"nuggets": final_nuggets}

# ==========================================
# ROTAS DE INTELIGÊNCIA ARTIFICIAL (OLLAMA)
# ==========================================
class AIReportRequest(BaseModel):
    player_name: str
    stat_choice: str
    stat_key: str
    ou_line: float
    ou_direction: str = "Over"
    stats_data: dict

@app.post("/ai/player-report")
def get_ai_player_report(req: AIReportRequest):
    report = generate_player_report(
        player_name=req.player_name,
        stat_choice=req.stat_choice,
        stat_key=req.stat_key,
        ou_line=req.ou_line,
        ou_direction=req.ou_direction,
        stats_data=req.stats_data
    )
    return {"report": report}

class ChatMessage(BaseModel):
    role: str
    content: str

class AIChatRequest(BaseModel):
    messages: list[ChatMessage]

@app.post("/ai/chat")
def ai_chat_endpoint(req: AIChatRequest):
    slate_data = get_todays_games()
    
    slate_text = ""
    if isinstance(slate_data, list) and len(slate_data) > 0:
        for g in slate_data:
            slate_text += f"- {g.get('away_name', 'Fora')} vs {g.get('home_name', 'Casa')} ({g.get('status', '')})\n"
    else:
        slate_text = "Não há jogos agendados para hoje ou houve um erro a carregar o calendário."
        
    messages_list = [{"role": m.role, "content": m.content} for m in req.messages]
    
    resposta = chat_with_agent(messages_list, slate_text)
    return {"response": resposta}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)