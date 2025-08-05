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

# Optimized base prompt - more concise
BASE_PROMPT = """Assistant for University of Sulaimani. Answer only university-related questions concisely. If unsure, say "I'm still learning about this topic." No security/internal data."""

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

def fetch_relevant_info(user_message: str, max_records: int = 3) -> List[str]:
    """Fetch most relevant info with reduced token usage"""
    db = SessionLocal()
    try:
        # Preprocess query for better matching
        processed_query = preprocess_query(user_message)
        query_embedding = embed_text_cached(processed_query)
        
        if not query_embedding:
            return []

        all_entries = db.query(Info).all()
        scored = []

        for rec in all_entries:
            # Create more concise text representation
            text = f"{rec.key}: {rec.value}"
            text_embedding = embed_text_cached(text)
            
            if text_embedding:
                similarity = cosine_similarity(text_embedding, query_embedding)
                # Only include high-confidence matches
                if similarity > 0.3:  # Threshold to filter irrelevant content
                    # Truncate long values to save tokens
                    truncated_value = rec.value[:200] + "..." if len(rec.value) > 200 else rec.value
                    scored.append((similarity, f"• {rec.key}: {truncated_value}"))

        # Sort by relevance and return top results
        scored.sort(reverse=True, key=lambda x: x[0])
        return [entry for _, entry in scored[:max_records]]
    finally:
        db.close()

def is_simple_query(query: str) -> bool:
    """Detect if query is simple enough to answer without context"""
    simple_patterns = [
        r'\b(hi|hello|hey|thanks|thank you)\b',
        r'\bwhat is your name\b',
        r'\bwho are you\b',
        r'\bhow are you\b'
    ]
    return any(re.search(pattern, query.lower()) for pattern in simple_patterns)

def create_optimized_system_prompt(context_lines: List[str]) -> str:
    """Create minimal system prompt"""
    if not context_lines:
        return BASE_PROMPT
    
    # Combine context more efficiently
    context = "\n".join(context_lines[:3])  # Limit context lines
    return f"{BASE_PROMPT}\n\nRelevant info:\n{context}"

def ask_claude(prompt: str) -> str:
    """Optimized Claude API call with caching and token reduction"""
    try:
        # Check cache first
        cache_key = get_cache_key(prompt)
        if cache_key in response_cache:
            logging.info(f"Cache hit for query: {prompt[:50]}...")
            return response_cache[cache_key]

        # Handle simple queries without context
        if is_simple_query(prompt):
            system_prompt = BASE_PROMPT
            context_lines = []
        else:
            context_lines = fetch_relevant_info(prompt, max_records=3)
            system_prompt = create_optimized_system_prompt(context_lines)

        # Use more efficient model and reduced max_tokens
        response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",  # Haiku is more token-efficient
            max_tokens=500,  # Reduced from 1000
            temperature=0.3,  # Lower temperature for more focused responses
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = response.content[0].text
        
        # Cache the response
        response_cache[cache_key] = answer
        
        # Log token usage info
        input_tokens = response.usage.input_tokens if hasattr(response, 'usage') else 0
        output_tokens = response.usage.output_tokens if hasattr(response, 'usage') else 0
        logging.info(f"Tokens used - Input: {input_tokens}, Output: {output_tokens}")
        
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