from anthropic import Anthropic, APIError, RateLimitError
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv
import os, logging, hashlib, json
from backend.database import SessionLocal, Info
import numpy as np
from functools import lru_cache
from typing import List, Tuple, Optional
import re

load_dotenv()

logging.basicConfig(filename="logs/chat_logs.txt", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Adaptive base prompts for different query types
BASE_PROMPT_DETAILED = """You are a knowledgeable assistant for the University of Sulaimani. Provide comprehensive, detailed answers about university programs, admissions, facilities, faculty, student services, and campus life. Include specific examples, procedures, and helpful context. If unsure about details, say "I'm still learning about this topic." Never share security or internal data."""

BASE_PROMPT_SIMPLE = """Assistant for University of Sulaimani. Answer university questions briefly. If unsure, say "I'm still learning about this topic." No security/internal data."""

# Simple in-memory cache for responses (use Redis in production)
response_cache = {}
embedding_cache = {}

def get_cache_key(text: str) -> str:
    """Generate cache key for text"""
    return hashlib.md5(text.encode()).hexdigest()

@lru_cache(maxsize=1000)
def embed_text_cached(text: str) -> Tuple[float, ...]:
    """Cached embedding with LRU eviction"""
    cache_key = get_cache_key(text)
    if cache_key in embedding_cache:
        return tuple(embedding_cache[cache_key])
    
    try:
        resp = openai_client.embeddings.create(model="text-embedding-3-small", input=text)
        embedding = resp.data[0].embedding
        embedding_cache[cache_key] = embedding
        return tuple(embedding)
    except OpenAIError as e:
        logging.error(f"Embedding error: {e}")
        return tuple()

def cosine_similarity(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    """Optimized cosine similarity"""
    if not a or not b:
        return 0.0
    a_arr, b_arr = np.array(a), np.array(b)
    return np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-9)

def preprocess_query(query: str) -> str:
    """Clean and normalize query"""
    # Remove extra whitespace, convert to lowercase
    query = re.sub(r'\s+', ' ', query.lower().strip())
    # Remove common filler words that don't add semantic value
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    words = [w for w in query.split() if w not in stop_words]
    return ' '.join(words)

def fetch_relevant_info(user_message: str, complexity: str = "medium") -> List[str]:
    """Fetch relevant info with adaptive context based on query complexity"""
    db = SessionLocal()
    try:
        # Adjust parameters based on complexity
        if complexity == "simple":
            max_records, char_limit = 1, 100
        elif complexity == "detailed":
            max_records, char_limit = 5, 400
        else:  # medium
            max_records, char_limit = 3, 200
        
        processed_query = preprocess_query(user_message)
        query_embedding = embed_text_cached(processed_query)
        
        if not query_embedding:
            return []

        all_entries = db.query(Info).all()
        scored = []

        for rec in all_entries:
            text = f"{rec.key}: {rec.value}"
            text_embedding = embed_text_cached(text)
            
            if text_embedding:
                similarity = cosine_similarity(text_embedding, query_embedding)
                # Lower threshold for detailed queries to get more context
                threshold = 0.2 if complexity == "detailed" else 0.3
                
                if similarity > threshold:
                    # Adaptive truncation based on complexity
                    if len(rec.value) > char_limit:
                        truncated_value = rec.value[:char_limit] + "..."
                    else:
                        truncated_value = rec.value
                    
                    scored.append((similarity, f"• {rec.key}: {truncated_value}"))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [entry for _, entry in scored[:max_records]]
    finally:
        db.close()

def classify_query_complexity(query: str) -> str:
    """Classify query complexity to determine appropriate response style"""
    query_lower = query.lower()
    
    # Simple greetings and basic questions
    simple_patterns = [
        r'\b(hi|hello|hey|thanks|thank you)\b',
        r'\bwhat is your name\b',
        r'\bwho are you\b',
        r'\bhow are you\b'
    ]
    
    # Complex informational queries that need detailed responses
    detailed_patterns = [
        r'\b(how to|how do i|what are the steps|procedure|process|requirements)\b',
        r'\b(tell me about|explain|describe|what is|what are)\b',
        r'\b(admission|program|course|degree|faculty|department)\b',
        r'\b(facilities|services|campus|library|dormitory)\b',
        r'\b(fees|tuition|scholarship|financial)\b',
        r'\b(when|where|why|which)\b.*\?',
        r'\b(difference between|compare|versus|vs)\b'
    ]
    
    if any(re.search(pattern, query_lower) for pattern in simple_patterns):
        return "simple"
    elif any(re.search(pattern, query_lower) for pattern in detailed_patterns):
        return "detailed"
    elif len(query.split()) > 10:  # Long queries usually need detailed responses
        return "detailed"
    else:
        return "medium"

def create_adaptive_system_prompt(context_lines: List[str], complexity: str) -> str:
    """Create adaptive system prompt based on query complexity"""
    if complexity == "simple":
        base_prompt = BASE_PROMPT_SIMPLE
    else:
        base_prompt = BASE_PROMPT_DETAILED
    
    if not context_lines:
        return base_prompt
    
    # Add context with complexity-appropriate instructions
    context = "\n".join(context_lines)
    
    if complexity == "detailed":
        instruction = "\n\nUsing the information below, provide a comprehensive answer with specific details, examples, and step-by-step guidance where applicable:"
    else:
        instruction = "\n\nRelevant information:"
    
    return f"{base_prompt}{instruction}\n{context}"

def ask_claude(prompt: str) -> str:
    """Adaptive Claude API call that balances token efficiency with response quality"""
    try:
        # Check cache first
        cache_key = get_cache_key(prompt)
        if cache_key in response_cache:
            logging.info(f"Cache hit for query: {prompt[:50]}...")
            return response_cache[cache_key]

        # Classify query complexity
        complexity = classify_query_complexity(prompt)
        
        # Adjust parameters based on complexity
        if complexity == "simple":
            max_tokens = 150
            temperature = 0.1
            context_lines = []
            system_prompt = BASE_PROMPT_SIMPLE
        elif complexity == "detailed":
            max_tokens = 800
            temperature = 0.4
            context_lines = fetch_relevant_info(prompt, complexity)
            system_prompt = create_adaptive_system_prompt(context_lines, complexity)
        else:  # medium
            max_tokens = 400
            temperature = 0.3
            context_lines = fetch_relevant_info(prompt, complexity)
            system_prompt = create_adaptive_system_prompt(context_lines, complexity)

        # API call with adaptive parameters
        response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = response.content[0].text
        
        # Cache the response
        response_cache[cache_key] = answer
        
        # Enhanced logging with complexity info
        input_tokens = response.usage.input_tokens if hasattr(response, 'usage') else 0
        output_tokens = response.usage.output_tokens if hasattr(response, 'usage') else 0
        logging.info(f"Query complexity: {complexity}, Tokens - Input: {input_tokens}, Output: {output_tokens}")
        
        return answer
        
    except (RateLimitError, APIError) as e:
        logging.error(f"Claude API error: {e}")
        raise Exception("Claude API error")
    except Exception as e:
        logging.error(f"Unexpected Claude error: {e}")
        raise

def clear_cache():
    """Clear response cache - useful for production management"""
    global response_cache
    response_cache.clear()
    embed_text_cached.cache_clear()
    logging.info("Caches cleared")

# Optional: Periodic cache cleanup
def cleanup_cache():
    """Remove old cache entries to prevent memory bloat"""
    global response_cache
    if len(response_cache) > 1000:  # Keep only 1000 most recent
        # In production, implement LRU or TTL-based cleanup
        keys_to_remove = list(response_cache.keys())[:-500]
        for key in keys_to_remove:
            del response_cache[key]
        logging.info("Cache cleanup completed")