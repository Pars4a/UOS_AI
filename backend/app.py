from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from claude_api import ask_claude, reload_university_info, get_info_stats
from chatgpt_api import ask_openai
from datetime import datetime
import logging
import os

#watch out for the log files permissions when dealing with docker, CI , uvicorn,  
logging.basicConfig(filename='logs/chat_logs.txt', level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()
#need these mounted into the docker file
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="/app/frontend/static"), name="static")

# Security for admin endpoints
security = HTTPBearer()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "your-secret-admin-token")

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return credentials

class ChatMessage(BaseModel):
    message: str

class InfoUpdateResponse(BaseModel):
    status: str
    message: str
    timestamp: datetime

@app.get('/health')
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

# Admin endpoint to reload university information
@app.post("/admin/reload-info", response_model=InfoUpdateResponse)
async def reload_info(credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    """Admin endpoint to reload university information files"""
    try:
        reload_university_info()
        logging.info("University information reloaded by admin")
        return InfoUpdateResponse(
            status="success",
            message="University information has been reloaded successfully",
            timestamp=datetime.now()
        )
    except Exception as e:
        logging.error(f"Error reloading university info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload info: {str(e)}")

# Admin endpoint to check what information is currently loaded
@app.get("/admin/info-status")
async def get_info_status(credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    """Admin endpoint to check current university information status"""
    try:
        stats = get_info_stats()
        return {
            "status": "success",
            "stats": stats,
            "last_check": datetime.now()
        }
    except Exception as e:
        logging.error(f"Error getting info status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get info status: {str(e)}")

#dont touch these, redirects user msg to chatgpt api if claude doesnt work
@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        answer = ask_claude(msg.message)
        logging.info(f"User message: {msg.message}")
        logging.info(f"Claude response: {answer}")
        return {"response": answer, "source": "claude"}
    except Exception as e:
        logging.warning(f"Claude failed, falling back to OpenAI: {e}")
        try:
            answer = ask_openai(msg.message)
            logging.info(f"User message: {msg.message}")
            logging.info(f"OpenAI response: {answer}")
            return {"response": answer, "source": "openai"}
        except Exception as openai_error:
            logging.error(f"Both Claude and OpenAI failed: {openai_error}")
            raise HTTPException(status_code=500, detail="Both AI services are currently unavailable")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/index.html")
async def redirect_home():
    return RedirectResponse(url="/")

@app.get("/about")
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/about.html")
async def redirect_about():
    return RedirectResponse(url="/about")

@app.get("/contact")
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/contact.html")
async def redirect_contact():
    return RedirectResponse(url="/contact")

# Optional: Add a simple admin dashboard endpoint
@app.get("/admin")
async def admin_dashboard(request: Request, credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    """Simple admin dashboard"""
    return templates.TemplateResponse("admin.html", {"request": request})

# Startup event to load initial information
@app.on_event("startup")
async def startup_event():
    """Load university information on startup"""
    try:
        # The smart loader loads files on-demand, so just log startup
        logging.info("Smart university information loader initialized")
    except Exception as e:
        logging.error(f"Failed to initialize university information loader: {e}")