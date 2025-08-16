from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from datetime import datetime, timedelta
from typing import Literal, Dict, Optional, List
from typing import Literal, Dict, Optional, List
import logging
import os
import hashlib
import uuid
from fastapi import status
import uuid
from fastapi import status

from dotenv import load_dotenv
from backend.database import (
    SessionLocal, Info, User, ChatSession, ChatMessage, init_db,
    get_user_by_email, create_user, create_chat_session, create_chat_message
)
from backend.database import (
    SessionLocal, Info, User, ChatSession, ChatMessage, init_db,
    get_user_by_email, create_user, create_chat_session, create_chat_message
)
from backend.claude_api import ask_claude, clear_cache, cleanup_cache
from backend.auth import (
    authenticate_user, create_access_token, get_password_hash, 
    get_current_user, get_current_admin_user, create_guest_token,
    UserCreate, UserLogin, Token, UserUpdate
)
from backend.chatgpt_api import ask_openai
from backend.email_service import send_feedback_email
from backend.auth import (
    authenticate_user, create_access_token, get_password_hash, 
    get_current_user, get_current_admin_user, create_guest_token,
    UserCreate, UserLogin, Token, UserUpdate
)
from backend.chatgpt_api import ask_openai
from backend.email_service import send_feedback_email

load_dotenv()

logging.basicConfig(filename='logs/chat_logs.txt', level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="/app/frontend/static"), name="static")

security = HTTPBearer()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

# Simple rate limiting (use Redis in production)
rate_limit_storage: Dict[str, Dict] = {}

def get_client_ip(request: Request) -> str:
    """Get client IP for rate limiting"""
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host

def check_rate_limit(client_ip: str, limit: int = 50, window: int = 3600) -> bool:
    """Check if client has exceeded rate limit (30 requests per hour)"""
    now = datetime.now()
    
    if client_ip not in rate_limit_storage:
        rate_limit_storage[client_ip] = {"count": 1, "window_start": now}
        return True
    
    client_data = rate_limit_storage[client_ip]
    
    # Reset window if expired
    if now - client_data["window_start"] > timedelta(seconds=window):
        client_data["count"] = 1
        client_data["window_start"] = now
        return True
    
    # Check if within limit
    if client_data["count"] >= limit:
        return False
    
    client_data["count"] += 1
    return True

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return credentials

class ChatMessage(BaseModel):
    message: str
    
    @validator('message')
    def validate_message(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) > 1000:  # Increased limit for detailed queries
            raise ValueError("Message too long (max 1000 characters)")
        return v

class GuestLogin(BaseModel):
    session_id: Optional[str] = None

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    
    @validator('new_password')
    def validate_new_password(cls, v, values):
        if v and len(v) < 6:
            raise ValueError("New password must be at least 6 characters long")
        return v

class GuestLogin(BaseModel):
    session_id: Optional[str] = None

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    
    @validator('new_password')
    def validate_new_password(cls, v, values):
        if v and len(v) < 6:
            raise ValueError("New password must be at least 6 characters long")
        return v

class InfoCreate(BaseModel):
    category: str
    key: str
    value: str

class FeedbackMessage(BaseModel):
    name: str
    email: str
    category: Literal["feedback", "suggestion", "bug", "feature", "other"]
    subject: str
    message: str

    @validator('name', 'email', 'subject', 'message')
    def validate_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @validator('email')
    def validate_email_format(cls, v):
        import re
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError("Invalid email format")
        return v

@app.on_event("startup")
async def startup():
    init_db()
    os.makedirs("logs", exist_ok=True)
    logging.info("=== SYSTEM STARTUP COMPLETE ===")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    clear_cache()
    logging.info("=== SYSTEM SHUTDOWN COMPLETE ===")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/chat")
async def chat_api(request: Request, msg: ChatMessage, current_user: dict = Depends(get_current_user)):
async def chat_api(request: Request, msg: ChatMessage, current_user: dict = Depends(get_current_user)):
    try:
        # Rate limiting
        client_ip = get_client_ip(request)
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, 
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Handle chat session for different user types
        db = SessionLocal()
        try:
            chat_session = None
            
            if current_user and current_user.get("user_type") in ["user", "admin"]:
                # Registered user - create or get session
                existing_session = db.query(ChatSession).filter(
                    ChatSession.user_id == current_user["user_id"]
                ).order_by(ChatSession.created_at.desc()).first()
                
                if not existing_session or (datetime.utcnow() - existing_session.created_at).days > 1:
                    chat_session = create_chat_session(db, user_id=current_user["user_id"])
                else:
                    chat_session = existing_session
            elif current_user and current_user.get("user_type") == "guest":
                # Guest user - create session with session_id
                session_id = current_user.get("email", "").replace("guest_", "")
                existing_session = db.query(ChatSession).filter(
                    ChatSession.session_id == session_id
                ).first()
                
                if not existing_session:
                    chat_session = create_chat_session(db, session_id=session_id)
                else:
                    chat_session = existing_session
        finally:
            db.close()
        # Handle chat session for different user types
        db = SessionLocal()
        try:
            chat_session = None
            
            if current_user and current_user.get("user_type") in ["user", "admin"]:
                # Registered user - create or get session
                existing_session = db.query(ChatSession).filter(
                    ChatSession.user_id == current_user["user_id"]
                ).order_by(ChatSession.created_at.desc()).first()
                
                if not existing_session or (datetime.utcnow() - existing_session.created_at).days > 1:
                    chat_session = create_chat_session(db, user_id=current_user["user_id"])
                else:
                    chat_session = existing_session
            elif current_user and current_user.get("user_type") == "guest":
                # Guest user - create session with session_id
                session_id = current_user.get("email", "").replace("guest_", "")
                existing_session = db.query(ChatSession).filter(
                    ChatSession.session_id == session_id
                ).first()
                
                if not existing_session:
                    chat_session = create_chat_session(db, session_id=session_id)
                else:
                    chat_session = existing_session
        finally:
            db.close()
        
        response = ask_claude(msg.message)
        
        # Save chat message to database
        if chat_session:
            db = SessionLocal()
            try:
                create_chat_message(
                    db, 
                    session_id=chat_session.id,
                    message=msg.message,
                    response=response,
                    message_type="conversation"
                )
            finally:
                db.close()
        
        
        # Save chat message to database
        if chat_session:
            db = SessionLocal()
            try:
                create_chat_message(
                    db, 
                    session_id=chat_session.id,
                    message=msg.message,
                    response=response,
                    message_type="conversation"
                )
            finally:
                db.close()
        
        logging.info(f"User: {msg.message[:100]}{'...' if len(msg.message) > 100 else ''}")
        logging.info(f"Claude: {response[:100]}{'...' if len(response) > 100 else ''}")
        
        return {"response": response, "source": "claude"}
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logging.error(f"Chat error: {str(e)}")
        try:
            response = ask_openai(msg.message)
            return {"response": response, "source": "openai"}
        except Exception as openai_error:
            logging.error(f"OpenAI fallback error: {str(openai_error)}")
            raise HTTPException(status_code=500, detail="AI services temporarily unavailable")

# Authentication endpoints
@app.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, user.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = get_password_hash(user.password)
        db_user = create_user(
            db, 
            email=user.email, 
            hashed_password=hashed_password, 
            full_name=user.full_name
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email, "user_type": "user", "user_id": db_user.id},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_type": "user",
            "user_id": db_user.id
        }
    finally:
        db.close()

@app.post("/auth/login", response_model=Token)
async def login(user: UserLogin):
    authenticated_user = authenticate_user(user.email, user.password)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": authenticated_user.email, "user_type": authenticated_user.user_type, "user_id": authenticated_user.id},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": authenticated_user.user_type,
        "user_id": authenticated_user.id
    }

@app.post("/auth/guest", response_model=Token)
async def guest_login(guest: GuestLogin):
    session_id = guest.session_id or str(uuid.uuid4())
    access_token = create_guest_token(session_id)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": "guest"
    }

@app.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    if not current_user:
        return {"user_type": "anonymous"}
    return current_user

# User profile and chat history endpoints
@app.get("/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "user_type": user.user_type,
            "created_at": user.created_at.isoformat()
        }
    finally:
        db.close()

@app.put("/user/profile")
async def update_user_profile(profile_data: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update full name if provided
        if profile_data.full_name:
            user.full_name = profile_data.full_name
        
        # Update password if provided
        if profile_data.new_password and profile_data.current_password:
            from backend.auth import verify_password
            if not verify_password(profile_data.current_password, user.hashed_password):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
            user.hashed_password = get_password_hash(profile_data.new_password)
        
        db.commit()
        return {"message": "Profile updated successfully"}
    finally:
        db.close()

@app.get("/user/chat-history")
async def get_user_chat_history(
    page: int = 1, 
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        offset = (page - 1) * limit
        
        # Get user's chat sessions
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user["user_id"]
        ).order_by(ChatSession.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for session in sessions:
            messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            session_data = {
                "session_id": session.id,
                "created_at": session.created_at.isoformat(),
                "messages": [
                    {
                        "id": msg.id,
                        "message": msg.message,
                        "response": msg.response,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            }
            result.append(session_data)
        
        # Get total count
        total_sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user["user_id"]
        ).count()
        
        return {
            "sessions": result,
            "total": total_sessions,
            "page": page,
            "limit": limit,
            "total_pages": (total_sessions + limit - 1) // limit
        }
    finally:
        db.close()

@app.delete("/user/chat-session/{session_id}")
async def delete_user_chat_session(session_id: int, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        # Verify session belongs to user
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user["user_id"]
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Delete messages first
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        
        # Delete session
        db.delete(session)
        db.commit()
        
        return {"message": "Chat session deleted successfully"}
    finally:
        db.close()

@app.post("/auth/logout")
async def logout():
    return {"message": "Logged out successfully"}

# Admin dashboard endpoints
@app.get("/admin/chat-history")
async def get_chat_history(
    page: int = 1, 
    limit: int = 50,
    current_user: dict = Depends(get_current_admin_user)
):
    db = SessionLocal()
    try:
        offset = (page - 1) * limit
        
        # Get chat sessions with messages
        sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for session in sessions:
            messages = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).all()
            
            user_info = "Guest"
            if session.user:
                user_info = f"{session.user.full_name} ({session.user.email})"
            elif session.session_id:
                user_info = f"Guest ({session.session_id[:8]}...)"
            
            session_data = {
                "session_id": session.id,
                "user_info": user_info,
                "created_at": session.created_at.isoformat(),
                "messages": [
                    {
                        "id": msg.id,
                        "message": msg.message,
                        "response": msg.response,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            }
            result.append(session_data)
        
        # Get total count
        total_sessions = db.query(ChatSession).count()
        
        return {
            "sessions": result,
            "total": total_sessions,
            "page": page,
            "limit": limit,
            "total_pages": (total_sessions + limit - 1) // limit
        }
    finally:
        db.close()

@app.get("/admin/users")
async def get_users(current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return [
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat()
            }
            for user in users
        ]
    finally:
        db.close()

@app.delete("/admin/chat-session/{session_id}")
async def delete_chat_session(session_id: int, current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        # Delete messages first
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        
        # Delete session
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        db.delete(session)
        db.commit()
        
        return {"message": "Chat session deleted successfully"}
    finally:
        db.close()

# Authentication endpoints
@app.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, user.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = get_password_hash(user.password)
        db_user = create_user(
            db, 
            email=user.email, 
            hashed_password=hashed_password, 
            full_name=user.full_name
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email, "user_type": "user", "user_id": db_user.id},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_type": "user",
            "user_id": db_user.id
        }
    finally:
        db.close()

@app.post("/auth/login", response_model=Token)
async def login(user: UserLogin):
    authenticated_user = authenticate_user(user.email, user.password)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": authenticated_user.email, "user_type": authenticated_user.user_type, "user_id": authenticated_user.id},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": authenticated_user.user_type,
        "user_id": authenticated_user.id
    }

@app.post("/auth/guest", response_model=Token)
async def guest_login(guest: GuestLogin):
    session_id = guest.session_id or str(uuid.uuid4())
    access_token = create_guest_token(session_id)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": "guest"
    }

@app.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    if not current_user:
        return {"user_type": "anonymous"}
    return current_user

# User profile and chat history endpoints
@app.get("/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "user_type": user.user_type,
            "created_at": user.created_at.isoformat()
        }
    finally:
        db.close()

@app.put("/user/profile")
async def update_user_profile(profile_data: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update full name if provided
        if profile_data.full_name:
            user.full_name = profile_data.full_name
        
        # Update password if provided
        if profile_data.new_password and profile_data.current_password:
            from backend.auth import verify_password
            if not verify_password(profile_data.current_password, user.hashed_password):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
            user.hashed_password = get_password_hash(profile_data.new_password)
        
        db.commit()
        return {"message": "Profile updated successfully"}
    finally:
        db.close()

@app.get("/user/chat-history")
async def get_user_chat_history(
    page: int = 1, 
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        offset = (page - 1) * limit
        
        # Get user's chat sessions
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user["user_id"]
        ).order_by(ChatSession.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for session in sessions:
            messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            session_data = {
                "session_id": session.id,
                "created_at": session.created_at.isoformat(),
                "messages": [
                    {
                        "id": msg.id,
                        "message": msg.message,
                        "response": msg.response,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            }
            result.append(session_data)
        
        # Get total count
        total_sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user["user_id"]
        ).count()
        
        return {
            "sessions": result,
            "total": total_sessions,
            "page": page,
            "limit": limit,
            "total_pages": (total_sessions + limit - 1) // limit
        }
    finally:
        db.close()

@app.delete("/user/chat-session/{session_id}")
async def delete_user_chat_session(session_id: int, current_user: dict = Depends(get_current_user)):
    if not current_user or current_user.get("user_type") == "guest":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = SessionLocal()
    try:
        # Verify session belongs to user
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user["user_id"]
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Delete messages first
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        
        # Delete session
        db.delete(session)
        db.commit()
        
        return {"message": "Chat session deleted successfully"}
    finally:
        db.close()

@app.post("/auth/logout")
async def logout():
    return {"message": "Logged out successfully"}

# Admin dashboard endpoints
@app.get("/admin/chat-history")
async def get_chat_history(
    page: int = 1, 
    limit: int = 50,
    current_user: dict = Depends(get_current_admin_user)
):
    db = SessionLocal()
    try:
        offset = (page - 1) * limit
        
        # Get chat sessions with messages
        sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for session in sessions:
            messages = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).all()
            
            user_info = "Guest"
            if session.user:
                user_info = f"{session.user.full_name} ({session.user.email})"
            elif session.session_id:
                user_info = f"Guest ({session.session_id[:8]}...)"
            
            session_data = {
                "session_id": session.id,
                "user_info": user_info,
                "created_at": session.created_at.isoformat(),
                "messages": [
                    {
                        "id": msg.id,
                        "message": msg.message,
                        "response": msg.response,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            }
            result.append(session_data)
        
        # Get total count
        total_sessions = db.query(ChatSession).count()
        
        return {
            "sessions": result,
            "total": total_sessions,
            "page": page,
            "limit": limit,
            "total_pages": (total_sessions + limit - 1) // limit
        }
    finally:
        db.close()

@app.get("/admin/users")
async def get_users(current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return [
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat()
            }
            for user in users
        ]
    finally:
        db.close()

@app.delete("/admin/chat-session/{session_id}")
async def delete_chat_session(session_id: int, current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        # Delete messages first
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        
        # Delete session
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        db.delete(session)
        db.commit()
        
        return {"message": "Chat session deleted successfully"}
    finally:
        db.close()

@app.post("/feedback")
async def submit_feedback(request: Request, feedback: FeedbackMessage):
    try:
        # Rate limiting for feedback
        client_ip = get_client_ip(request)
        if not check_rate_limit(client_ip, limit=5, window=3600):  # 5 feedback per hour
            raise HTTPException(
                status_code=429, 
                detail="Too many feedback submissions. Please try again later."
            )
        
        send_feedback_email(
            name=feedback.name,
            email=feedback.email,
            category=feedback.category,
            subject=feedback.subject,
            message=feedback.message
        )
        return JSONResponse(status_code=200, content={
            "success": True,
            "message": "Feedback sent successfully."
        })
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Feedback error: {str(e)}")
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": "Unable to send feedback. Please try again later.",
            "error_type": type(e).__name__
        })

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    # Remove the admin check here - we'll do it in JavaScript
    return templates.TemplateResponse("dashboard.html", {"request": request})

# Add this test endpoint for debugging:
@app.get("/test-admin")  # REMOVE AFTER TESTING
async def test_admin(current_user: dict = Depends(get_current_admin_user)):
    return {"message": "Admin access working!", "user": current_user}

# Add this debug endpoint to check auth status:
@app.get("/debug-auth")  # REMOVE AFTER TESTING
async def debug_auth(current_user: dict = Depends(get_current_user)):
    return {
        "current_user": current_user,
        "is_admin": current_user.get("user_type") == "admin" if current_user else False,
        "token_received": current_user is not None
    }

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

# Admin endpoints with additional optimizations
@app.post("/admin/info/add")
async def add_info(data: InfoCreate, current_user: dict = Depends(get_current_admin_user)):
async def add_info(data: InfoCreate, current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        # Clear cache when new info is added
        clear_cache()
        
        db.add(Info(category=data.category, key=data.key, value=data.value))
        db.commit()
        return {"status": "success"}
    finally:
        db.close()

@app.get("/admin/info")
async def list_info(current_user: dict = Depends(get_current_admin_user)):
async def list_info(current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        results = db.query(Info).all()
        return [{"id": r.id, "category": r.category, "key": r.key, "value": r.value} for r in results]
    finally:
        db.close()

@app.delete("/admin/info/{info_id}")
async def delete_info(info_id: int, current_user: dict = Depends(get_current_admin_user)):
async def delete_info(info_id: int, current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        record = db.query(Info).filter(Info.id == info_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        
        # Clear cache when info is deleted
        clear_cache()
        
        db.delete(record)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()

@app.put("/admin/info/{info_id}")
async def update_info(info_id: int, data: InfoCreate, current_user: dict = Depends(get_current_admin_user)):
async def update_info(info_id: int, data: InfoCreate, current_user: dict = Depends(get_current_admin_user)):
    db = SessionLocal()
    try:
        record = db.query(Info).filter(Info.id == info_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        
        # Clear cache when info is updated
        clear_cache()
        
        record.category = data.category
        record.key = data.key
        record.value = data.value
        db.commit()
        
        return {"status": "updated"}
    finally:
        db.close()

# Admin cache management endpoints
@app.post("/admin/cache/clear")
async def clear_cache_endpoint(current_user: dict = Depends(get_current_admin_user)):
async def clear_cache_endpoint(current_user: dict = Depends(get_current_admin_user)):
    clear_cache()
    return {"status": "cache cleared"}

@app.post("/admin/cache/cleanup") 
async def cleanup_cache_endpoint(current_user: dict = Depends(get_current_admin_user)):
async def cleanup_cache_endpoint(current_user: dict = Depends(get_current_admin_user)):
    cleanup_cache()
    return {"status": "cache cleanup completed"}

# Periodic cleanup task (run this via cron or scheduler in production)
@app.get("/admin/stats")
async def get_stats(current_user: dict = Depends(get_current_admin_user)):
    return {
        "rate_limit_entries": len(rate_limit_storage),
        "total_users": SessionLocal().query(User).count(),
        "total_chat_sessions": SessionLocal().query(ChatSession).count(),
        "timestamp": datetime.now()
    }


    # ... all your existing code ...

@app.get("/admin/stats")
async def get_stats(current_user: dict = Depends(get_current_admin_user)):
    return {
        "rate_limit_entries": len(rate_limit_storage),
        "total_users": SessionLocal().query(User).count(),
        "total_chat_sessions": SessionLocal().query(ChatSession).count(),
        "total_users": SessionLocal().query(User).count(),
        "total_chat_sessions": SessionLocal().query(ChatSession).count(),
        "timestamp": datetime.now()
    }

# ADD THE NEW CODE HERE ↓↓↓
@app.get("/debug-users")  # REMOVE AFTER USE
async def debug_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return {
            "total_users": len(users),
            "users": [
                {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "user_type": user.user_type,
                    "is_active": user.is_active
                }
                for user in users
            ]
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/create-admin-now")  # CHANGED TO GET - REMOVE AFTER USE
async def create_admin_now():
    db = SessionLocal()
    try:
        admin_email = "admin@yoursite.com"  # CHANGE THIS
        admin_password = "admin123456"      # CHANGE THIS TO SOMETHING SECURE
        
        # Check if admin exists
        existing = get_user_by_email(db, admin_email)
        if existing:
            if existing.user_type == "admin":
                return {"message": "Admin already exists!", "email": admin_email, "password": admin_password}
            else:
                # Upgrade existing user to admin
                existing.user_type = "admin"
                db.commit()
                return {"message": "User upgraded to admin!", "email": admin_email}
        
        # Create new admin user
        from backend.auth import get_password_hash
        hashed_password = get_password_hash(admin_password)
        admin_user = create_user(
            db, 
            email=admin_email, 
            hashed_password=hashed_password, 
            full_name="Administrator",
            user_type="admin"
        )
        
        return {
            "message": "✅ SUCCESS! Admin created!",
            "email": admin_email,
            "password": admin_password,
            "next_step": "Go to /login and use these credentials"
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()