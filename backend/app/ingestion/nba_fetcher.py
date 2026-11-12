import time
from datetime import datetime
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import playergamelog
from sqlalchemy.orm import Session
from app.db.models import Team, Player, PlayerGameStat

def sync_teams_and_players(db: Session):
    """Sincroniza equipas e jogadores ativos para a base de dados."""
    print("A sincronizar equipas...")
    nba_teams = teams.get_teams()
    for t in nba_teams:
        team_db = db.query(Team).filter(Team.id == t['id']).first()
        if not team_db:
            team_db = Team(id=t['id'], full_name=t['full_name'], abbreviation=t['abbreviation'])
            db.add(team_db)
    db.commit()

    print("A sincronizar jogadores ativos...")
    active_players = players.get_active_players()
    for p in active_players:
        player_db = db.query(Player).filter(Player.id == p['id']).first()
        if not player_db:
            # Assumindo que não sabemos a team_id de momento (pode ser atualizado depois)
            player_db = Player(id=p['id'], full_name=p['full_name'], is_active=1)
            db.add(player_db)
    db.commit()
    print("Equipas e jogadores sincronizados com sucesso!")

def fetch_player_gamelogs(player_id: int, db: Session, season='2026-27'):
    """Vai buscar os jogos todos de um jogador na época atual."""
    print(f"A descarregar jogos para o player_id {player_id}...")
    try:
        gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season)
        df = gamelog.get_data_frames()[0]
        
        for index, row in df.iterrows():
            stat_id = f"{player_id}_{row['Game_ID']}"
            existing = db.query(PlayerGameStat).filter(PlayerGameStat.id == stat_id).first()
            
            if not existing:
                # Converter data "NOV 10, 2026" para objecto Date
                g_date = datetime.strptime(row['GAME_DATE'], '%b %d, %Y').date()
                
                stat = PlayerGameStat(
                    id=stat_id,
                    player_id=player_id,
                    game_id=row['Game_ID'],
                    game_date=g_date,
                    matchup=row['MATCHUP'],
                    minutes=float(row['MIN']),
                    pts=row['PTS'],
                    reb=row['REB'],
                    ast=row['AST'],
                    stl=row['STL'],
                    blk=row['BLK'],
                    fgm=row['FGM'],
                    fga=row['FGA'],
                    fg3m=row['FG3M'],
                    fg3a=row['FG3A']
                )
                db.add(stat)
        db.commit()
        print(f"Jogos importados com sucesso!")
        # Sleep recomendado para não levar ban da API da NBA
        time.sleep(1)
    except Exception as e:
        print(f"Erro ao importar dados: {e}")