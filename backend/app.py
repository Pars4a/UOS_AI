from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from claude_api import ask_claude, reload_university_info, get_info_stats, smart_info_loader
from chatgpt_api import ask_openai
from datetime import datetime
from pathlib import Path
import logging, os, yaml
from typing import List, Dict

logging.basicConfig(filename='logs/chat_logs.txt', level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()
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

class KeywordUpdate(BaseModel):
    category: str
    files: List[str]
    keywords: Dict[str, List[str]]

@app.get('/health')
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/admin/reload-info")
async def reload_info(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        reload_university_info()
        return {"status": "success", "message": "Info reloaded", "timestamp": datetime.now()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/info-status")
async def get_info_status(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        return {"status": "success", "stats": get_info_stats(), "last_check": datetime.now()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/keywords")
async def get_keywords(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        config_file = Path("config/keywords.yaml")
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return {"status": "success", "config": yaml.safe_load(f)}
        return {"status": "error", "message": "File not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/keywords/reload")
async def reload_keywords(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        smart_info_loader.reload_keywords()
        return {"status": "success", "message": "Keywords reloaded", "timestamp": datetime.now()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/keywords/add-category")
async def add_category(data: KeywordUpdate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    return await modify_keywords(data, new=True)

@app.put("/admin/keywords/update-category/{category}")
async def update_category(category: str, data: KeywordUpdate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    return await modify_keywords(data, category=category)

@app.delete("/admin/keywords/delete-category/{category}")
async def delete_category(category: str, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        config_file = Path("config/keywords.yaml")
        if not config_file.exists(): raise HTTPException(status_code=404)
        with open(config_file, 'r+', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if category not in config: raise HTTPException(status_code=404)
            del config[category]
            f.seek(0); f.truncate(); yaml.dump(config, f, allow_unicode=True)
        smart_info_loader.reload_keywords()
        return {"status": "success", "message": f"Deleted {category}", "timestamp": datetime.now()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def modify_keywords(data: KeywordUpdate, new=False, category=None):
    try:
        config_file = Path("config/keywords.yaml")
        config = yaml.safe_load(config_file.read_text(encoding='utf-8')) if config_file.exists() else {}
        target = data.category if new else category
        config[target] = {"files": data.files, "keywords": data.keywords}
        config_file.write_text(yaml.dump(config, allow_unicode=True), encoding='utf-8')
        smart_info_loader.reload_keywords()
        return {"status": "success", "message": f"{target} saved", "timestamp": datetime.now()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        response = ask_claude(msg.message)
        return {"response": response, "source": "claude"}
    except:
        try:
            return {"response": ask_openai(msg.message), "source": "openai"}
        except Exception as e:
            raise HTTPException(status_code=500, detail="Both AI services failed")

@app.get("/")
@app.get("/index.html")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/about")
@app.get("/about.html")
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/contact")
@app.get("/contact.html")
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/admin")
async def admin_dashboard(request: Request, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.on_event("startup")
async def startup_event():
    try:
        for folder in ["logs", "config", "university_info"]:
            Path(folder).mkdir(exist_ok=True)
        logging.info("System initialized")
    except Exception as e:
        logging.error(f"Startup failed: {e}")
