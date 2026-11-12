import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base
# Importar os modelos é crucial para o SQLAlchemy saber quais tabelas processar
from app.db import models 

print("A apagar as tabelas antigas...")
Base.metadata.drop_all(bind=engine)

print("A criar as tabelas novas com a estrutura atualizada (incluindo TeamGameStat e WL)...")
Base.metadata.create_all(bind=engine)

print("Reset concluído com sucesso! Base de dados pronta a usar.")