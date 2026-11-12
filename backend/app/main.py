import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.core.database import engine, Base, get_db
from app.db.models import Player, PlayerGameStat
from app.ingestion.nba_fetcher import sync_teams_and_players, fetch_player_gamelogs
from app.stats.stats_engine import calculate_player_stats

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Sports Scout API")

@app.post("/sync/rosters")
def sync_rosters(db: Session = Depends(get_db)):
    sync_teams_and_players(db)
    return {"message": "Jogadores e Equipas sincronizados com sucesso."}

@app.get("/players")
def get_all_players(db: Session = Depends(get_db)):
    players = db.query(Player.full_name).filter(Player.is_active == 1).order_by(Player.full_name).all()
    return [p[0] for p in players]

@app.get("/player/{player_name}/stats")
def get_player_stats(player_name: str, opponent: str = None, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.full_name.ilike(f"%{player_name}%")).first()
    if not player:
        return {"error": f"Jogador '{player_name}' não encontrado. Sincroniza as equipas."}
    
    stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).all()
    
    if not stats:
        print(f"Sem dados para {player.full_name}. A descarregar da API...")
        fetch_player_gamelogs(player.id, db)
        stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).all()
        
    if not stats:
        return {"error": "Não foram encontrados jogos para este jogador nesta época."}
        
    # Passamos o target_opponent para filtrar apenas se o utilizador quiser
    processed_stats = calculate_player_stats(stats, target_opponent=opponent)
    
    if not processed_stats:
        return {"error": f"Sem dados contra o adversário {opponent}."}
    
    return {
        "player_id": player.id,
        "player_name": player.full_name,
        "stats": processed_stats
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)