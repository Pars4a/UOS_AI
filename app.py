from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from chatgpt_api import ask_openai  

app = FastAPI()

# Templates and static files setup
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/ask", response_class=HTMLResponse)
async def ask(request: Request, question: str = Form(...)):
    answer = ask_openai(question)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "question": question,
        "answer": answer
    })


@app.post("/test_openai")
async def test_openai(request: Request):
    data = await request.json()
    question = data.get("question")
    answer = ask_openai(question)
    return {"answer": answer}

class ChatMessage(BaseModel):
    message: str

@app.post("/chat")
async def chat_api(msg: ChatMessage):
    answer = ask_openai(msg.message)
    return {"response": answer}
