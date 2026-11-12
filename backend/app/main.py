import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.core.database import engine, Base, get_db
from app.db.models import Player, Team, PlayerGameStat, TeamGameStat
from app.ingestion.nba_fetcher import sync_teams_and_players, fetch_player_gamelogs, fetch_team_gamelogs
from app.stats.stats_engine import calculate_player_stats, calculate_team_stats

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Sports Scout API")

LAST_FETCHED = {}

@app.post("/sync/rosters")
def sync_rosters(db: Session = Depends(get_db)):
    sync_teams_and_players(db)
    return {"message": "Jogadores e Equipas sincronizados com sucesso."}

@app.get("/players")
def get_all_players(db: Session = Depends(get_db)):
    players = db.query(Player.full_name).filter(Player.is_active == 1).order_by(Player.full_name).all()
    return [p[0] for p in players]

@app.get("/teams")
def get_all_teams(db: Session = Depends(get_db)):
    teams = db.query(Team.full_name).order_by(Team.full_name).all()
    return [t[0] for t in teams]

@app.get("/player/{player_name}/stats")
def get_player_stats(player_name: str, opponent: str = None, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.full_name.ilike(f"%{player_name}%")).first()
    if not player:
        return {"error": f"Jogador '{player_name}' não encontrado."}
    
    stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).all()
    
    needs_update = False
    if not stats:
        needs_update = True
    else:
        last_update = LAST_FETCHED.get(f"P_{player.id}")
        if not last_update or datetime.now() - last_update > timedelta(hours=6):
            needs_update = True
            
    if needs_update:
        try:
            db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).delete()
            db.commit()
            fetch_player_gamelogs(player.id, db)
            LAST_FETCHED[f"P_{player.id}"] = datetime.now()
            stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).all()
        except Exception as e:
            db.rollback()
            
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
    
    stats = db.query(TeamGameStat).filter(TeamGameStat.team_id == team.id).all()
    
    needs_update = False
    if not stats:
        needs_update = True
    else:
        last_update = LAST_FETCHED.get(f"T_{team.id}")
        if not last_update or datetime.now() - last_update > timedelta(hours=6):
            needs_update = True
            
    if needs_update:
        try:
            db.query(TeamGameStat).filter(TeamGameStat.team_id == team.id).delete()
            db.commit()
            fetch_team_gamelogs(team.id, db)
            LAST_FETCHED[f"T_{team.id}"] = datetime.now()
            stats = db.query(TeamGameStat).filter(TeamGameStat.team_id == team.id).all()
        except Exception as e:
            db.rollback()
            
    if not stats:
        return {"error": "Não foram encontrados jogos para esta equipa."}
        
    # --- NOVO: Encontrar os pontos da equipa adversária cruzando o Game ID ---
    game_ids = [g.game_id for g in stats]
    opp_stats = db.query(TeamGameStat.game_id, TeamGameStat.pts).filter(
        TeamGameStat.game_id.in_(game_ids),
        TeamGameStat.team_id != team.id
    ).all()
    # Criamos um dicionário rápido {game_id: pontos_do_adversario}
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