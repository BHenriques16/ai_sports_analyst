import sys
import os
from datetime import datetime, timedelta
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import engine, Base, get_db
from app.db.models import Player, Team, PlayerGameStat, TeamGameStat
from app.ingestion.nba_fetcher import sync_teams_and_players, fetch_player_gamelogs, fetch_team_gamelogs
from app.stats.stats_engine import calculate_player_stats, calculate_team_stats
from nba_api.stats.endpoints import scoreboardv2

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Sports Scout API")

LAST_FETCHED = {}

def should_update_entity(entity_key: str, latest_game_date, hours_cooldown: int = 6) -> bool:
    """Verifica se é necessário ir à API da NBA com base na cache e na data do último jogo na BD."""
    now = datetime.now()
    last_fetch = LAST_FETCHED.get(entity_key)
    
    if last_fetch and (now - last_fetch < timedelta(hours=hours_cooldown)):
        return False
        
    if not latest_game_date:
        return True
        
    # Se já temos o jogo de hoje ou de ontem na BD, marcamos como atualizado sem chamar a API
    if latest_game_date >= (now.date() - timedelta(days=1)):
        LAST_FETCHED[entity_key] = now
        return False
        
    return True

@app.post("/sync/rosters")
def sync_rosters(db: Session = Depends(get_db)):
    sync_teams_and_players(db)
    print("A atualizar de forma incremental os calendários das 30 equipas da NBA...")
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

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)