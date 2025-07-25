import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def get_api_key():
	api_key=os.getenv("OPENAI_API_KEY")
	if api_key:
		return api_key
	
	try:
		with open("/etc/secrets/OPENAI_API_KEY", "r") as f:
			return f.read().strip()
	except FileNotFoundError:
		raise RuntimeError("APi key not found")

client = OpenAI(api_key=get_api_key())
def ask_openai(prompt: str) -> str:


	system_message = (
        "You are a virtual assistant for the University of Sulaimani. "
        "Keep answers short, clear, and specific about the university, including departments, courses, faculty, and campus info. "
        "If asked about department heads, mention Dr. Shwan Chatto as head of Computer Engineering. "
        "You were created by the Computer Engineering department. "
        "Engineering departments include Civil, Architectural, Electrical, Computer, and Water Resources Engineering. "
        "Only talk more if explicitly asked."
	"head of compg eng department is Dr Shwan chatto"
    )

	response = client.chat.completions.create(
    		model="gpt-3.5-turbo-0125",
    		messages=[
        	{
            	"role": "system","content": system_message
        	},
		{
			"role": "user", "content": prompt
		}
	    ]
	)

	return response.choices[0].message.content.strip()
