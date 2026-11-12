from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True) # ID oficial da NBA
    full_name = Column(String, unique=True, index=True)
    abbreviation = Column(String)
    
    players = relationship("Player", back_populates="team")

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True) # ID oficial da NBA
    full_name = Column(String, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    is_active = Column(Integer, default=1)
    
    team = relationship("Team", back_populates="players")
    stats = relationship("PlayerGameStat", back_populates="player")

class PlayerGameStat(Base):
    __tablename__ = "player_game_stats"
    id = Column(String, primary_key=True) # Ex: "PlayerID_GameID"
    player_id = Column(Integer, ForeignKey("players.id"), index=True)
    game_id = Column(String, index=True)
    game_date = Column(Date, index=True)
    matchup = Column(String) # Ex: "BOS vs. LAL"
    
    # Estatísticas
    minutes = Column(Float)
    pts = Column(Integer)
    reb = Column(Integer)
    ast = Column(Integer)
    stl = Column(Integer)
    blk = Column(Integer)
    fgm = Column(Integer)
    fga = Column(Integer)
    fg3m = Column(Integer)
    fg3a = Column(Integer)
    
    player = relationship("Player", back_populates="stats")