from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from claude_api import ask_claude

from chatgpt_api import ask_openai  

app = FastAPI()

# Templates and static files setup
templates = Jinja2Templates(directory="templates")
#app.mount("/static", StaticFiles(directory="static"), name="static")



@app.get("/", )
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

#@app.post("/ask", response_class=HTMLResponse)
#async def ask(request: Request, question: str ):
    answer = ask_claude(question)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "question": question,
        "answer": answer
    })



class ChatMessage(BaseModel):
    message: str

@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        answer = ask_claude(msg.message)
        return {"response": answer}
    except Exception as e:
        return {"error": str(e)}


