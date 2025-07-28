from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from datetime import datetime
import os
import logging
from typing import Literal
from dotenv import load_dotenv
from backend.database import SessionLocal, Info, init_db
from backend.claude_api import ask_claude
from chatgpt_api import ask_openai
from email_service import send_feedback_email

load_dotenv()
logging.basicConfig(filename='logs/chat_logs.txt', level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

# CORS middleware - Fixed missing import and closing parenthesis
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="/app/frontend/static"), name="static")

# Security setup for admin routes
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

# Fixed indentation and added missing import
class FeedbackMessage(BaseModel):
    name: str
    email: str
    category: Literal["feedback", "suggestion", "bug", "feature", "other"]
    subject: str
    message: str
    
    @validator('name', 'email', 'subject', 'message')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
    
    @validator('email')
    def validate_email_format(cls, v):
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v

@app.on_event("startup")
async def startup():
    init_db()
    for folder in ["logs"]:
        os.makedirs(folder, exist_ok=True)
    
    # Test logging - Fixed indentation
    logging.info("=== SYSTEM STARTUP ===")
    logging.info("System initialized successfully")
    logging.info("Available endpoints:")
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            logging.info(f"  {list(route.methods)} {route.path}")
    logging.info("=== STARTUP COMPLETE ===")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

# Chat endpoint
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
            logging.info(f"OpenAI: {response}")
            return {"response": response, "source": "openai"}
        except Exception:
            raise HTTPException(status_code=500, detail="Both AI services failed")

# Feedback endpoint with error handling - Fixed indentation and structure
@app.post("/feedback")
async def submit_feedback(request: Request, feedback: FeedbackMessage):
    try:
        # Logging for debugging
        logging.info(f"=== FEEDBACK SUBMISSION START ===")
        logging.info(f"Raw request body: {await request.body()}")
        logging.info(f"Parsed feedback data: {feedback.dict()}")
        logging.info(f"Received feedback from: {feedback.name} ({feedback.email})")
        logging.info(f"Category: '{feedback.category}', Subject: '{feedback.subject}'")
        
        # Validate category explicitly (though Pydantic should handle this now)
        valid_categories = ["feedback", "suggestion", "bug", "feature", "other"]
        if feedback.category not in valid_categories:
            error_msg = f"Invalid category '{feedback.category}'. Must be one of: {valid_categories}"
            logging.error(error_msg)
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": error_msg
                }
            )
        
        # Attempt to send email with detailed error handling
        try:
            logging.info("Attempting to send feedback email...")
            send_feedback_email(
                name=feedback.name,
                email=feedback.email,
                category=feedback.category,
                subject=feedback.subject,
                message=feedback.message
            )
            logging.info("Email sent successfully!")
        except Exception as email_error:
            error_msg = f"Failed to send email: {str(email_error)}"
            logging.error(error_msg)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"Email service error: {str(email_error)}"
                }
            )
        
        logging.info(f"Feedback process completed successfully for {feedback.name}")
        logging.info(f"=== FEEDBACK SUBMISSION END ===")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True, 
                "message": "Feedback sent successfully and confirmation email sent to you!"
            }
        )
        
    except HTTPException as http_error:
        logging.error(f"HTTP Exception: {http_error.detail}")
        raise http_error
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Unexpected error in feedback submission: {error_msg}")
        logging.error(f"Error type: {type(e).__name__}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False, 
                "message": f"Server error: {error_msg}",
                "error_type": type(e).__name__
            }
        )

# Add a test endpoint for debugging
@app.get("/test")
async def test_endpoint():
    return {
        "status": "test_successful",
        "timestamp": datetime.now(),
        "message": "API is working correctly"
    }

# Enhanced error handler for better debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Global exception handler: {type(exc).__name__}: {str(exc)}")
    logging.error(f"Request: {request.method} {request.url}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error occurred",
            "error_type": type(exc).__name__,
            "path": str(request.url.path)
        }
    )

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

# Admin endpoints to manage info data
@app.post("/admin/info/add")
async def add_info(data: InfoCreate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    db = SessionLocal()
    try:
        record = Info(category=data.category, key=data.key, value=data.value)
        db.add(record)
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