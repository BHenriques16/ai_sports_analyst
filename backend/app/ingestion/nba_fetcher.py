import time
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, teamgamelog
from sqlalchemy.orm import Session
from app.db.models import Player, Team, PlayerGameStat, TeamGameStat
from datetime import datetime

def sync_teams_and_players(db: Session):
    nba_teams = teams.get_teams()
    for t in nba_teams:
        team_obj = db.query(Team).filter(Team.id == t['id']).first()
        if not team_obj:
            team_obj = Team(id=t['id'], full_name=t['full_name'], abbreviation=t['abbreviation'])
            db.add(team_obj)
    db.commit()

    nba_players = players.get_active_players()
    for p in nba_players:
        player_obj = db.query(Player).filter(Player.id == p['id']).first()
        if not player_obj:
            player_obj = Player(id=p['id'], full_name=p['full_name'], is_active=1)
            db.add(player_obj)
    db.commit()

# CORRIGIDO: season alterado para '2026-27'
def fetch_player_gamelogs(player_id: int, db: Session, season='2026-27'):
    try:
        gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season, season_type_all_star='Regular Season')
        df = gamelog.get_data_frames()[0]
        
        for _, row in df.iterrows():
            stat_id = f"{player_id}_{row['Game_ID']}"
            existing = db.query(PlayerGameStat).filter(PlayerGameStat.id == stat_id).first()
            
            if not existing:
                game_date_obj = datetime.strptime(row['GAME_DATE'], '%b %d, %Y').date()
                
                new_stat = PlayerGameStat(
                    id=stat_id,
                    player_id=player_id,
                    game_id=row['Game_ID'],
                    game_date=game_date_obj,
                    matchup=row['MATCHUP'],
                    wl=row['WL'],
                    minutes=row['MIN'],
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
                db.add(new_stat)
        db.commit()
        time.sleep(0.5) 
    except Exception as e:
        print(f"Erro ao buscar dados do jogador {player_id}: {e}")

# CORRIGIDO: season alterado para '2026-27'
def fetch_team_gamelogs(team_id: int, db: Session, season='2026-27'):
    try:
        gamelog = teamgamelog.TeamGameLog(team_id=team_id, season=season, season_type_all_star='Regular Season')
        df = gamelog.get_data_frames()[0]
        
        for _, row in df.iterrows():
            stat_id = f"{team_id}_{row['Game_ID']}"
            existing = db.query(TeamGameStat).filter(TeamGameStat.id == stat_id).first()
            
            if not existing:
                game_date_obj = datetime.strptime(row['GAME_DATE'], '%b %d, %Y').date()
                
                new_stat = TeamGameStat(
                    id=stat_id,
                    team_id=team_id,
                    game_id=row['Game_ID'],
                    game_date=game_date_obj,
                    matchup=row['MATCHUP'],
                    wl=row['WL'],
                    pts=row['PTS'],
                    reb=row['REB'],
                    ast=row['AST'],
                    stl=row['STL'],
                    blk=row['BLK'],
                    fgm=row['FGM'],
                    fga=row['FGA'],
                    fg3m=row['FG3M'],
                    fg3a=row['FG3A'],
                    tov=row['TOV']
                )
                db.add(new_stat)
        db.commit()
        time.sleep(0.5)
    except Exception as e:
        print(f"Erro ao buscar dados da equipa {team_id}: {e}")