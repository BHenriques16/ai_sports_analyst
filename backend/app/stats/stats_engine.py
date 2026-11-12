import pandas as pd
import numpy as np

def calculate_player_stats(games, target_opponent=None):
    if not games:
        return None
    
    data = [{
        "game_date": g.game_date,
        "matchup": g.matchup,
        "minutes": g.minutes,
        "pts": g.pts,
        "reb": g.reb,
        "ast": g.ast,
        "stl": g.stl,
        "blk": g.blk
    } for g in games]
    
    df_full = pd.DataFrame(data)
    
    # 1. Tratar Datas e B2B no histórico completo (antes de filtrar adversário)
    df_full['game_date'] = pd.to_datetime(df_full['game_date'])
    df_full = df_full.sort_values(by="game_date", ascending=True)
    df_full['days_rest'] = (df_full['game_date'] - df_full['game_date'].shift(1)).dt.days
    df_full['is_b2b'] = df_full['days_rest'] == 1
    df_full = df_full.sort_values(by="game_date", ascending=False)
    
    # Extrair a lista de adversários únicos (ex: "LAL", "GSW")
    df_full['opp_abrv'] = df_full['matchup'].apply(lambda x: str(x).split(' ')[-1] if pd.notnull(x) else "")
    unique_opponents = sorted([x for x in df_full['opp_abrv'].unique() if x])

    # 2. Aplicar filtro de adversário (Head-to-Head) se solicitado
    if target_opponent and target_opponent in unique_opponents:
        df = df_full[df_full['opp_abrv'] == target_opponent].copy()
    else:
        df = df_full.copy()

    if df.empty:
        return None

    # 3. Identificar Casa vs Fora
    df['home_away'] = df['matchup'].apply(lambda x: 'Home' if 'vs.' in str(x) else 'Away')
    
    # 4. Calcular Mercados Combinados (Combos)
    df['pra'] = df['pts'] + df['reb'] + df['ast']
    df['pa'] = df['pts'] + df['ast']
    df['pr'] = df['pts'] + df['reb']
    df['ar'] = df['ast'] + df['reb']
    df['bs'] = df['blk'] + df['stl'] # Stocks
    
    stats_cols = ['minutes', 'pts', 'reb', 'ast', 'stl', 'blk', 'pra', 'pa', 'pr', 'ar', 'bs']
    
    season_avg = df[stats_cols].mean().fillna(0).round(1).to_dict()
    last_10_avg = df.head(10)[stats_cols].mean().fillna(0).round(1).to_dict()
    last_5_avg = df.head(5)[stats_cols].mean().fillna(0).round(1).to_dict()
    
    # Calcular Splits
    home_df = df[df['home_away'] == 'Home']
    away_df = df[df['home_away'] == 'Away']
    splits = {
        "Home": home_df[stats_cols].mean().fillna(0).round(1).to_dict() if not home_df.empty else {c: 0 for c in stats_cols},
        "Away": away_df[stats_cols].mean().fillna(0).round(1).to_dict() if not away_df.empty else {c: 0 for c in stats_cols}
    }
    
    # Calcular Over/Under default
    ou_cols = ['pts', 'reb', 'ast', 'stl', 'blk', 'pra', 'pa', 'pr', 'ar', 'bs']
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
    
    # Preparar a tabela para o frontend
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