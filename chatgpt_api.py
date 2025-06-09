client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


university_knowledge_base = {
    "What is the Computer Engineering department known for?":
        "The Computer Engineering department at the University of Sulaimani offers cutting-edge courses in AI, networking, and software engineering.",
    "What are the requirements for admission to the Computer Engineering department?":
        "To be admitted to the Computer Engineering department, you must have a high school diploma with strong performance in math and science courses.",
    "Who is the head of the Computer Engineering department?":
        "The current head of the Computer Engineering department is Dr. Shwan Chatto.",
    
}

def ask_openai(prompt: str) -> str:
    
    if prompt in university_knowledge_base:
        return university_knowledge_base[prompt]

   
    system_message = (
        "You are a virtual assistant for the University of Sulaimani. "
        "Keep answers short, clear, and specific about the university, including departments, courses, faculty, and campus info. "
        "If asked about department heads, mention Dr. Shwan Chatto as head of Computer Engineering. "
        "You were created by the Computer Engineering department. "
        "Engineering departments include Civil, Architectural, Electrical, Computer, and Water Resources Engineering. "
        "Only talk more if explicitly asked."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()
