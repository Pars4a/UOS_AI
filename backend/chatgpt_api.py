import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    		model="fake-model",
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
