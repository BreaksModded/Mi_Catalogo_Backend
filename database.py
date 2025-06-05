from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

import os

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://media_0t7l_user:DAOS1Key0XhoQAd8G2DUcnWYjk4A0TF9@dpg-d0dku715pdvs739a5520-a.frankfurt-postgres.render.com/media_0t7l"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
