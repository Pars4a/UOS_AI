from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)  # Set echo=True if you want SQL logs

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Info(Base):
    __tablename__ = "info"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(255), index=True)
    key = Column(String(255), index=True)
    value = Column(Text)

def init_db():
    Base.metadata.create_all(bind=engine)
