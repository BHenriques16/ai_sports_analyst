import time
import pandas as pd
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, teamgamelog, commonallplayers
from sqlalchemy.orm import Session
from app.db.models import Player, Team, PlayerGameStat, TeamGameStat
from datetime import datetime

def sync_teams_and_players(db: Session, season='2026-27'):
    nba_teams = teams.get_teams()
    existing_teams = {t.id: t for t in db.query(Team).all()}
    
    for t in nba_teams:
        if t['id'] not in existing_teams:
            team_obj = Team(id=t['id'], full_name=t['full_name'], abbreviation=t['abbreviation'])
            db.add(team_obj)
    db.commit()

    # Atualiza jogadores e respetivas equipas numa única transação em memória
    try:
        all_players_df = commonallplayers.CommonAllPlayers(is_only_current_season=1, season=season).get_data_frames()[0]
        existing_players = {p.id: p for p in db.query(Player).all()}
        
        for _, row in all_players_df.iterrows():
            p_id = int(row['PERSON_ID'])
            p_name = row['DISPLAY_FIRST_LAST']
            t_id = row['TEAM_ID']
            
            t_id = int(t_id) if pd.notnull(t_id) and int(t_id) > 0 else None
            
            if p_id not in existing_players:
                player_obj = Player(id=p_id, full_name=p_name, team_id=t_id, is_active=1)
                db.add(player_obj)
            else:
                existing_players[p_id].team_id = t_id
                existing_players[p_id].is_active = 1
        
        db.commit()
    except Exception as e:
        print(f"Erro ao sincronizar equipas dos jogadores: {e}")
        db.rollback()
        nba_players = players.get_active_players()
        existing_players = {p.id: p for p in db.query(Player).all()}
        for p in nba_players:
            if p['id'] not in existing_players:
                player_obj = Player(id=p['id'], full_name=p['full_name'], is_active=1)
                db.add(player_obj)
        db.commit()

def fetch_player_gamelogs(player_id: int, db: Session, season='2026-27'):
    try:
        gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season, season_type_all_star='Regular Season')
        df = gamelog.get_data_frames()[0]
        
        # Carrega IDs existentes numa única query (evita N+1 queries)
        existing_ids = {
            row[0] for row in db.query(PlayerGameStat.id)
            .filter(PlayerGameStat.player_id == player_id).all()
        }
        
        for _, row in df.iterrows():
            stat_id = f"{player_id}_{row['Game_ID']}"
            if stat_id not in existing_ids:
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
        db.rollback()
        print(f"Erro ao buscar dados do jogador {player_id}: {e}")

def fetch_team_gamelogs(team_id: int, db: Session, season='2026-27'):
    try:
        gamelog = teamgamelog.TeamGameLog(team_id=team_id, season=season, season_type_all_star='Regular Season')
        df = gamelog.get_data_frames()[0]
        
        # Carrega IDs existentes numa única query (evita N+1 queries)
        existing_ids = {
            row[0] for row in db.query(TeamGameStat.id)
            .filter(TeamGameStat.team_id == team_id).all()
        }
        
        for _, row in df.iterrows():
            stat_id = f"{team_id}_{row['Game_ID']}"
            if stat_id not in existing_ids:
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
        db.rollback()
        print(f"Erro ao buscar dados da equipa {team_id}: {e}")