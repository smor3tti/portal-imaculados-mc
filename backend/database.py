"""
Portal Imaculados M.C. - Conexão com o banco de dados

Por padrão usa PostgreSQL (produção). Para desenvolvimento local sem
Postgres instalado, defina DATABASE_URL como sqlite:///./imaculados.db
no arquivo .env
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Ex.: postgresql://usuario:senha@localhost:5432/imaculados_mc
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./imaculados.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency do FastAPI: abre e fecha a sessão do banco por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cria todas as tabelas definidas em models.py, se ainda não existirem."""
    import models  # noqa: F401  (garante que os modelos sejam registrados)
    Base.metadata.create_all(bind=engine)
