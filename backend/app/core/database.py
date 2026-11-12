from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Configuração da BD Local (Muda o user, password e nome da BD)
# Formato: postgresql://user:password@localhost:5432/nome_da_bd
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://postgres:admin@localhost:5432/ai_sports_scout"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()