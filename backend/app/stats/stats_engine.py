import pandas as pd
import numpy as np

NBA_TEAMS_MAP = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
}

def calculate_player_stats(games, target_opponent=None):
    if not games:
        return None
    
    data = [{
        "game_date": g.game_date,
        "matchup": g.matchup,
        "wl": getattr(g, 'wl', 'U'), 
        "minutes": g.minutes,
        "pts": g.pts,
        "reb": g.reb,
        "ast": g.ast,
        "stl": g.stl,
        "blk": g.blk,
        "fgm": getattr(g, 'fgm', 0),
        "fga": getattr(g, 'fga', 0),
        "fg3m": getattr(g, 'fg3m', 0),
        "fg3a": getattr(g, 'fg3a', 0)
    } for g in games]
    
    df_full = pd.DataFrame(data)
    df_full['game_date'] = pd.to_datetime(df_full['game_date'])
    df_full = df_full.sort_values(by="game_date", ascending=True)
    df_full['days_rest'] = (df_full['game_date'] - df_full['game_date'].shift(1)).dt.days
    df_full['is_b2b'] = df_full['days_rest'] == 1
    df_full = df_full.sort_values(by="game_date", ascending=False)
    
    df_full['opp_abrv'] = df_full['matchup'].apply(lambda x: str(x).split(' ')[-1] if pd.notnull(x) else "")
    df_full['opp_name'] = df_full['opp_abrv'].map(NBA_TEAMS_MAP).fillna(df_full['opp_abrv'])
    
    unique_opponents = sorted([x for x in df_full['opp_name'].unique() if x])

    if target_opponent and target_opponent in unique_opponents:
        df = df_full[df_full['opp_name'] == target_opponent].copy()
    else:
        df = df_full.copy()

    if df.empty:
        return None

    df['home_away'] = df['matchup'].apply(lambda x: 'Home' if 'vs.' in str(x) else 'Away')
    df['pra'] = df['pts'] + df['reb'] + df['ast']
    df['pa'] = df['pts'] + df['ast']
    df['pr'] = df['pts'] + df['reb']
    df['ar'] = df['ast'] + df['reb']
    df['bs'] = df['blk'] + df['stl']
    
    stats_cols = ['minutes', 'pts', 'reb', 'ast', 'stl', 'blk', 'fg3m', 'pra', 'pa', 'pr', 'ar', 'bs']
    
    season_avg = df[stats_cols].mean().fillna(0).round(1).to_dict()
    last_10_avg = df.head(10)[stats_cols].mean().fillna(0).round(1).to_dict()
    last_5_avg = df.head(5)[stats_cols].mean().fillna(0).round(1).to_dict()
    
    total_fgm, total_fga = df['fgm'].sum(), df['fga'].sum()
    total_fg3m, total_fg3a = df['fg3m'].sum(), df['fg3a'].sum()
    
    season_avg['fg_pct'] = round((total_fgm / total_fga * 100), 1) if total_fga > 0 else 0
    season_avg['fg3_pct'] = round((total_fg3m / total_fg3a * 100), 1) if total_fg3a > 0 else 0
    
    home_df = df[df['home_away'] == 'Home']
    away_df = df[df['home_away'] == 'Away']
    splits = {
        "Home": home_df[stats_cols].mean().fillna(0).round(1).to_dict() if not home_df.empty else {c: 0 for c in stats_cols},
        "Away": away_df[stats_cols].mean().fillna(0).round(1).to_dict() if not away_df.empty else {c: 0 for c in stats_cols}
    }
    
    ou_cols = ['pts', 'reb', 'ast', 'stl', 'blk', 'fg3m', 'pra', 'pa', 'pr', 'ar', 'bs']
    ou_analysis = {}
    for col in ou_cols:
        base_line = round(season_avg[col]) + 0.5 
        recent_10 = df.head(10)[col]
        overs = int((recent_10 > base_line).sum())
        
        ou_analysis[col] = {
            "default_line": base_line,
            "over_10g": overs,
            "under_10g": len(recent_10) - overs,
            "hit_rate_10g": (overs / len(recent_10)) * 100 if len(recent_10) > 0 else 0
        }
    
    df['game_date'] = df['game_date'].dt.strftime('%Y-%m-%d')
    df = df.fillna({"is_b2b": False, "days_rest": 99})
    
    return {
        "unique_opponents": unique_opponents,
        "season_avg": season_avg,
        "last_10_avg": last_10_avg,
        "last_5_avg": last_5_avg,
        "splits": splits,
        "ou_analysis": ou_analysis,
        "games_log": df.to_dict(orient="records")
    }

# --- NOVO: Aceita o mapa de pontos do adversário (opp_pts_map) ---
def calculate_team_stats(games, opp_pts_map=None, target_opponent=None):
    if not games:
        return None
    
    if opp_pts_map is None:
        opp_pts_map = {}
        
    data = [{
        "game_id": g.game_id,
        "game_date": g.game_date,
        "matchup": g.matchup,
        "wl": getattr(g, 'wl', 'U'),
        "pts": g.pts,
        "opp_pts": opp_pts_map.get(g.game_id, 0), # Vai buscar os pontos sofridos
        "reb": g.reb,
        "ast": g.ast,
        "stl": g.stl,
        "blk": g.blk,
        "fg3m": getattr(g, 'fg3m', 0),
        "tov": getattr(g, 'tov', 0)
    } for g in games]
    
    df_full = pd.DataFrame(data)
    df_full['game_date'] = pd.to_datetime(df_full['game_date'])
    df_full = df_full.sort_values(by="game_date", ascending=False)
    
    # Calcular Totais do Jogo
    df_full['total_pts'] = df_full['pts'] + df_full['opp_pts']
    
    df_full['opp_abrv'] = df_full['matchup'].apply(lambda x: str(x).split(' ')[-1] if pd.notnull(x) else "")
    df_full['opp_name'] = df_full['opp_abrv'].map(NBA_TEAMS_MAP).fillna(df_full['opp_abrv'])
    
    unique_opponents = sorted([x for x in df_full['opp_name'].unique() if x])

    if target_opponent and target_opponent in unique_opponents:
        df = df_full[df_full['opp_name'] == target_opponent].copy()
    else:
        df = df_full.copy()

    if df.empty:
        return None
        
    df['home_away'] = df['matchup'].apply(lambda x: 'Home' if 'vs.' in str(x) else 'Away')
    
    stats_cols = ['pts', 'reb', 'ast', 'stl', 'blk', 'fg3m', 'tov', 'opp_pts', 'total_pts']
    
    season_avg = df[stats_cols].mean().fillna(0).round(1).to_dict()
    last_10_avg = df.head(10)[stats_cols].mean().fillna(0).round(1).to_dict()
    
    total_games = len(df)
    wins = (df['wl'] == 'W').sum()
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    season_avg['win_rate'] = round(win_rate, 1)
    
    home_df = df[df['home_away'] == 'Home']
    away_df = df[df['home_away'] == 'Away']
    
    home_win_rate = ((home_df['wl'] == 'W').sum() / len(home_df) * 100) if len(home_df) > 0 else 0
    away_win_rate = ((away_df['wl'] == 'W').sum() / len(away_df) * 100) if len(away_df) > 0 else 0
    
    splits = {
        "Home": {"pts": home_df['pts'].mean() if not home_df.empty else 0, "win_rate": round(home_win_rate, 1)},
        "Away": {"pts": away_df['pts'].mean() if not away_df.empty else 0, "win_rate": round(away_win_rate, 1)}
    }
    
    df['game_date'] = df['game_date'].dt.strftime('%Y-%m-%d')
    
    return {
        "unique_opponents": unique_opponents,
        "season_avg": season_avg,
        "last_10_avg": last_10_avg,
        "splits": splits,
        "games_log": df.to_dict(orient="records")
    }