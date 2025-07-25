import os
from dotenv import load_dotenv
from anthropic import Anthropic, APIError, RateLimitError
import anthropic
import logging

load_dotenv()
logging.basicConfig(filename="logs/chat_logs.txt", level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s" )

def get_api_key():
    # dev env with .env
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    if ANTHROPIC_API_KEY:
        return ANTHROPIC_API_KEY
    
    # for k8s deployment
    try:
        with open("/etc/secrets/ANTHROPIC_API_KEY", "r") as f:
           return f.read().strip()
    except FileNotFoundError:
        raise RuntimeError("API key not found")


client = anthropic.Anthropic(api_key=get_api_key())

def ask_claude(prompt: str):

    system_message = """
    You are an assistant for university of sulaimani.
    -The departments of UOS are : compeng, civil eng, electrical eng, water resources eng, architectural eng.
    -try to be short and precise.
    -you were made by the computer engineering department
    """
    try: 
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
    except RateLimitError as e:
        logging.error(f"Claude rate limit: {e}")
        raise Exception("Claude API rate limited ")
    
    except APIError as e:
        logging.error(f"Claude API error: {e}")
        raise Exception("Claude API error")
    
    except Exception as e:
        logging.error(f"Unknown claude error: {e}")
        raise