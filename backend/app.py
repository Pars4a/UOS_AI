from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from datetime import datetime
from typing import Literal
import logging
import os

from dotenv import load_dotenv
from backend.database import SessionLocal, Info, init_db
from backend.claude_api import ask_claude
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

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return credentials

class ChatMessage(BaseModel):
    message: str

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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        response = ask_claude(msg.message)
        logging.info(f"User: {msg.message}")
        logging.info(f"Claude: {response}")
        return {"response": response, "source": "claude"}
    except Exception:
        try:
            response = ask_openai(msg.message)
            return {"response": response, "source": "openai"}
        except Exception:
            raise HTTPException(status_code=500, detail="Both AI services failed")

@app.post("/feedback")
async def submit_feedback(request: Request, feedback: FeedbackMessage):
    try:
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
    except Exception as e:
        logging.error(f"Feedback error: {str(e)}")
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": f"Server error: {str(e)}",
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

@app.post("/admin/info/add")
async def add_info(data: InfoCreate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    db = SessionLocal()
    try:
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
        
        record.category = data.category
        record.key = data.key
        record.value = data.value
        db.commit()
        
        return {"status": "updated"}
    finally:
        db.close()