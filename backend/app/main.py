import sys
import os
from datetime import datetime, timedelta

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

# Dicionário em memória para registar quando atualizámos cada jogador
# Formato: {player_id: datetime_da_ultima_atualizacao}
LAST_FETCHED = {}

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
    
    # --- LÓGICA DE ATUALIZAÇÃO INTELIGENTE (ON-DEMAND) ---
    needs_update = False
    
    if not stats:
        needs_update = True
    else:
        # Se já passaram mais de 6 horas desde a última vez que fomos à API, atualiza.
        last_update = LAST_FETCHED.get(player.id)
        if not last_update or datetime.now() - last_update > timedelta(hours=6):
            needs_update = True
            
    if needs_update:
        print(f"A atualizar dados frescos na API para {player.full_name}...")
        try:
            # Limpa os jogos antigos deste jogador na base de dados para evitar duplicados
            db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).delete()
            db.commit()
            
            # Vai buscar os dados atualizados incluindo os jogos de ontem à noite
            fetch_player_gamelogs(player.id, db)
            
            # Regista a hora exata da atualização para trancar a API nas próximas 6h
            LAST_FETCHED[player.id] = datetime.now()
            
            # Volta a carregar os dados atualizados para a memória
            stats = db.query(PlayerGameStat).filter(PlayerGameStat.player_id == player.id).all()
        except Exception as e:
            print(f"Erro ao atualizar {player.full_name}: {e}")
            db.rollback()
            
    if not stats:
        return {"error": "Não foram encontrados jogos para este jogador nesta época."}
        
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