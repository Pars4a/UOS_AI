from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from datetime import datetime, timedelta
from typing import Literal, Dict
import logging
import os
import hashlib

from dotenv import load_dotenv
from backend.database import SessionLocal, Info, init_db
from backend.claude_api import ask_claude, clear_cache, cleanup_cache
from chatgpt_api import ask_openai
from email_service import send_feedback_email

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

def check_rate_limit(client_ip: str, limit: int = 30, window: int = 3600) -> bool:
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
async def chat_api(request: Request, msg: ChatMessage):
    try:
        # Rate limiting
        client_ip = get_client_ip(request)
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, 
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Check for duplicate recent requests
        message_hash = hashlib.md5(msg.message.encode()).hexdigest()
        
        response = ask_claude(msg.message)
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

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

# Admin endpoints with additional optimizations
@app.post("/admin/info/add")
async def add_info(data: InfoCreate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
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
async def list_info(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    db = SessionLocal()
    try:
        results = db.query(Info).all()
        return [{"id": r.id, "category": r.category, "key": r.key, "value": r.value} for r in results]
    finally:
        db.close()

@app.delete("/admin/info/{info_id}")
async def delete_info(info_id: int, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
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
async def update_info(info_id: int, data: InfoCreate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
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
async def clear_cache_endpoint(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    clear_cache()
    return {"status": "cache cleared"}

@app.post("/admin/cache/cleanup") 
async def cleanup_cache_endpoint(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    cleanup_cache()
    return {"status": "cache cleanup completed"}

# Periodic cleanup task (run this via cron or scheduler in production)
@app.get("/admin/stats")
async def get_stats(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    return {
        "rate_limit_entries": len(rate_limit_storage),
        "timestamp": datetime.now()
    }