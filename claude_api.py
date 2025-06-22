import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = anthropic.Anthropic()

def ask_claude(prompt: str):

    system_message = """
    You are an assistant for university of sulaimani.
    -The departments of UOS are : compeng, civil eng, electrical eng, water resources eng, architectural eng.
    -try to be short and precise.
    -you were made by the computer engineering department
    """

    message = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=1000,
    temperature=1,
    system= system_message,
    messages=[
        {
            "role": "user","content": prompt
                
        }
    ]
)
    return message.content[0].text
