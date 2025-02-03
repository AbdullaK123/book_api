from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from book_api.models import Base
from book_api.settings import config
import os

# database url
DATABASE_URL = config.DATABASE_URL

# create the database engine and session maker
engine = create_engine(
    DATABASE_URL,
    pool_size=5,  # Maximum number of database connections in the pool
    max_overflow=10,  # Maximum number of connections that can be created beyond pool_size
    pool_timeout=30,  # Timeout for getting a connection from the pool
    pool_recycle=1800,  # Recycle connections after 30 minutes
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# get a session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()