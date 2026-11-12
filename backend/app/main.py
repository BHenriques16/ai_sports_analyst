from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.core.database import engine, Base, get_db
from app.db.models import Player, PlayerGameStat
from app.ingestion.nba_fetcher import sync_teams_and_players, fetch_player_gamelogs

# Cria as tabelas na BD caso não existam
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Sports Scout API")

@app.get("/")
def read_root():
    return {"status": "AI Sports Scout Backend is Running"}

@app.post("/sync/rosters")
def sync_rosters(db: Session = Depends(get_db)):
    """Faz fetch das equipas e jogadores da API da NBA"""
    sync_teams_and_players(db)
    return {"message": "Jogadores e Equipas sincronizados com sucesso."}

@app.post("/sync/player_stats/{player_id}")
def sync_player(player_id: int, db: Session = Depends(get_db)):
    """Faz fetch dos stats da época para um jogador específico"""
    fetch_player_gamelogs(player_id, db)
    return {"message": f"Stats importadas para o player {player_id}"}

@app.get("/player/{player_name}/stats")
def get_player_stats(player_name: str, db: Session = Depends(get_db)):
    """Exemplo de rota para o Streamlit/Frontend consumir"""
    player = db.query(Player).filter(Player.full_name.ilike(f"%{player_name}%")).first()
    if not player:
        return {"error": "Jogador não encontrado"}
    
    stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).order_by(PlayerGameStat.game_date.desc()).limit(10).all()
    return {"player": player.full_name, "last_10_games": stats}