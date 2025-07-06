from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from claude_api import ask_claude
import logging


logging.basicConfig(filename='chat_logs.log',level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from chatgpt_api import ask_openai  

app = FastAPI()

# Templates and static files setup
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")




@app.get("/health")
async def health_check():
    checks = {
        "status": "healthy",
    }
    return checks


class ChatMessage(BaseModel):
    message: str

@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        answer = ask_claude(msg.message)
        logging.info(msg.message)
        logging.info(answer)
        return {"response": answer}
    except Exception as e:
        return {"error": str(e)}

#app.get for aboutus.html 

@app.get("/")
async def about(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/index.html")
async def redirect_home():
    return RedirectResponse(url="/")
#app.get for aboutus.html

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

