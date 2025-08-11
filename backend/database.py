from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy import DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Info(Base):
    __tablename__ = "info"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(255), index=True)
    key = Column(String(255), index=True)
    value = Column(Text)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(255))
    user_type = Column(String(50), default="user")  # user, admin, guest
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to chat history
    chat_sessions = relationship("ChatSession", back_populates="user")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for guest users
    session_id = Column(String(255), index=True)  # For guest users
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session")
def init_db():
    Base.metadata.create_all(bind=engine)

# User helper functions
def get_user_by_email(db, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def create_user(db, email: str, hashed_password: str, full_name: str, user_type: str = "user"):
    db_user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        user_type=user_type
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_chat_session(db, user_id: int = None, session_id: str = None):
    db_session = ChatSession(user_id=user_id, session_id=session_id)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def create_chat_message(db, session_id: int, message: str, response: str, message_type: str):
    db_message = ChatMessage(
        session_id=session_id,
        message=message,
        response=response,
        message_type=message_type
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    message = Column(Text)
    response = Column(Text)
    message_type = Column(String(50))  # user, assistant
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("ChatSession", back_populates="messages")
