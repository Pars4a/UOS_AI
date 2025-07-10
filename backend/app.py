from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from claude_api import ask_claude
from chatgpt_api import ask_openai  
import logging


logging.basicConfig(filename='logs/chat_logs.txt',level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")






class ChatMessage(BaseModel):
    message: str

#dont touch these
@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        answer = ask_claude(msg.message)
        logging.info(msg.message)
        logging.info(answer)
        return {"response": answer}
    except Exception as e:
        answer = ask_openai(msg.message)
        logging.info(msg.message)
        logging.info(answer)
        return {"response": answer}


@app.get("/")
async def about(request: Request):
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

