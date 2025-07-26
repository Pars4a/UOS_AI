from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from claude_api import ask_claude, reload_university_info, get_info_stats
from chatgpt_api import ask_openai
from datetime import datetime
from pathlib import Path
import logging
import os
import yaml
from typing import List, Dict

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

class KeywordUpdate(BaseModel):
    category: str
    files: List[str]
    keywords: Dict[str, List[str]]

@app.get('/health')
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

# ==================== ADMIN ENDPOINTS ====================

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

@app.get("/admin/keywords")
async def get_keywords(credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    """Get current keyword configuration"""
    try:
        config_file = Path("config/keywords.yaml")
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return {"status": "success", "config": config}
        else:
            return {"status": "error", "message": "Keywords config file not found"}
    except Exception as e:
        logging.error(f"Error getting keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get keywords: {str(e)}")

@app.post("/admin/keywords/reload")
async def reload_keywords(credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    """Reload keyword configuration"""
    try:
        from claude_api import smart_info_loader
        smart_info_loader.reload_keywords()
        logging.info("Keywords reloaded by admin")
        return {
            "status": "success",
            "message": "Keywords reloaded successfully",
            "timestamp": datetime.now()
        }
    except Exception as e:
        logging.error(f"Error reloading keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload keywords: {str(e)}")

@app.post("/admin/keywords/add-category")
async def add_keyword_category(
    keyword_data: KeywordUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)
):
    """Add a new keyword category"""
    try:
        config_file = Path("config/keywords.yaml")
        
        # Load existing config
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        
        # Add new category
        config[keyword_data.category] = {
            "files": keyword_data.files,
            "keywords": keyword_data.keywords
        }
        
        # Save updated config
        config_file.parent.mkdir(exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        # Reload keywords
        from claude_api import smart_info_loader
        smart_info_loader.reload_keywords()
        
        logging.info(f"Added keyword category: {keyword_data.category}")
        return {
            "status": "success",
            "message": f"Category '{keyword_data.category}' added successfully",
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logging.error(f"Error adding keyword category: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add category: {str(e)}")

@app.put("/admin/keywords/update-category/{category}")
async def update_keyword_category(
    category: str,
    keyword_data: KeywordUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)
):
    """Update an existing keyword category"""
    try:
        config_file = Path("config/keywords.yaml")
        
        if not config_file.exists():
            raise HTTPException(status_code=404, detail="Keywords config file not found")
        
        # Load existing config
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if category not in config:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
        
        # Update category
        config[category] = {
            "files": keyword_data.files,
            "keywords": keyword_data.keywords
        }
        
        # Save updated config
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        # Reload keywords
        from claude_api import smart_info_loader
        smart_info_loader.reload_keywords()
        
        logging.info(f"Updated keyword category: {category}")
        return {
            "status": "success",
            "message": f"Category '{category}' updated successfully",
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating keyword category: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update category: {str(e)}")

@app.delete("/admin/keywords/delete-category/{category}")
async def delete_keyword_category(
    category: str,
    credentials: HTTPAuthorizationCredentials = Depends(verify_admin_token)
):
    """Delete a keyword category"""
    try:
        config_file = Path("config/keywords.yaml")
        
        if not config_file.exists():
            raise HTTPException(status_code=404, detail="Keywords config file not found")
        
        # Load existing config
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if category not in config:
            raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
        
        # Delete category
        del config[category]
        
        # Save updated config
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        # Reload keywords
        from claude_api import smart_info_loader
        smart_info_loader.reload_keywords()
        
        logging.info(f"Deleted keyword category: {category}")
        return {
            "status": "success",
            "message": f"Category '{category}' deleted successfully",
            "timestamp": datetime.now()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting keyword category: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete category: {str(e)}")

# ==================== MAIN ENDPOINTS ====================

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

# Startup event to initialize the system
@app.on_event("startup")
async def startup_event():
    """Initialize the system on startup"""
    try:
        # Create necessary directories
        Path("logs").mkdir(exist_ok=True)
        Path("config").mkdir(exist_ok=True)
        Path("university_info").mkdir(exist_ok=True)
        
        # The smart loader initializes on first use
        logging.info("Smart university information system initialized")
    except Exception as e:
        logging.error(f"Failed to initialize system: {e}")