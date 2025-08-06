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

# Language-aware base prompts
BASE_PROMPT_DETAILED_EN = """You are a knowledgeable assistant for the University of Sulaimani. Do not mention which api model you are. You were made by the computer engineering department. Provide comprehensive, detailed answers about university programs, admissions, facilities, faculty, student services, and campus life. Include specific examples, don't say check other sources for information, and helpful context. Never share security or internal data."""

BASE_PROMPT_DETAILED_KU = """تۆ یاریدەدەری زانایی بۆ زانکۆی سلێمانیت. باسی مۆدێلی APIـەکە مەکە. لەلایەن بەشی ئەندازیاری کۆمپیوتەرەوە دروستکراویت. وەڵامی تەواو و ورد بدەرەوە دەربارەی بەرنامەکانی زانکۆ، وەرگرتن، ئامرازەکان، مامۆستایان، خزمەتگوزارییەکانی خوێندکاران، و ژیانی کەمپەس. نموونە تایبەتەکان بخەرە ژوورەوە، مەڵێ سەرچاوەکانی تر بپشکنن بۆ زانیاری زیاتر. هەرگیز داتای ئاسایش یان ناوخۆیی هاوبەش مەکەرەوە."""

BASE_PROMPT_SIMPLE_EN = """Assistant for University of Sulaimani. Do not mention which api model you are. You were made by the computer engineering department. Answer university questions briefly. Don't mention other sources for information. No security/internal data."""

BASE_PROMPT_SIMPLE_KU = """یاریدەدەر بۆ زانکۆی سلێمانی. باسی مۆدێلی APIـەکە مەکە. لەلایەن بەشی ئەندازیاری کۆمپیوتەرەوە دروستکراویت. وەڵامی کورتی پرسیارەکانی زانکۆ بدەرەوە. باسی سەرچاوەکانی تر مەکە بۆ زانیاری. هیچ داتای ئاسایش/ناوخۆیی نییە."""

# Simple in-memory cache for responses (use Redis in production)
response_cache = {}
embedding_cache = {}

def detect_language(text: str) -> str:
    """Detect if text is primarily Kurdish or English"""
    # Kurdish unicode ranges (simplified detection)
    kurdish_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F')
    english_chars = sum(1 for c in text if c.isalpha() and ord(c) < 256)
    
    if kurdish_chars > english_chars:
        return "ku"
    return "en"

def estimate_tokens_by_language(text: str, language: str) -> int:
    """Estimate token count based on language characteristics"""
    if language == "ku":
        # Kurdish analysis shows much higher token usage
        words = len(text.split())
        chars = len(text)
        # More accurate estimate based on observed data
        # Kurdish uses 4-6 tokens per word on average
        word_estimate = words * 5
        char_estimate = chars // 1.5  # ~1.5 chars per token for Kurdish
        # Take the higher estimate to be safe
        return max(word_estimate, char_estimate)
    else:
        # English approximation: ~4 characters per token
        return len(text) // 4

def get_adaptive_token_limits(language: str, complexity: str) -> dict:
    """Get token limits adapted for language and complexity"""
    base_limits = {
        "simple": {"en": 150, "ku": 200},
        "medium": {"en": 1000, "ku": 1000}, 
        "detailed": {"en": 1100, "ku": 1100}
    }
    
    return {
        "max_tokens": base_limits[complexity][language],
        "temperature": 0.1 if complexity == "simple" else (0.3 if complexity == "medium" else 0.4)
    }

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

def preprocess_query(query: str, language: str) -> str:
    """Clean and normalize query with language awareness"""
    query = re.sub(r'\s+', ' ', query.strip())
    
    if language == "en":
        # English stop words
        query = query.lower()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [w for w in query.split() if w not in stop_words]
        return ' '.join(words)
    else:
        # For Kurdish, minimal preprocessing to preserve meaning
        # Remove common Kurdish particles if needed
        kurdish_particles = {'و', 'لە', 'بە', 'لەگەڵ', 'بۆ'}  # and, in, with, with, for
        words = [w for w in query.split() if w not in kurdish_particles]
        return ' '.join(words) if words else query

def fetch_relevant_info(user_message: str, language: str, complexity: str = "medium") -> List[str]:
    """Fetch relevant info with language and complexity awareness"""
    db = SessionLocal()
    try:
        # Adjust parameters based on complexity and language
        if complexity == "simple":
            max_records, char_limit = 1, 60 if language == "ku" else 100
        elif complexity == "detailed":
            max_records, char_limit = 4, 700 if language == "ku" else 500
        else:  # medium
            max_records, char_limit = 2, 500 if language == "ku" else 500
        
        processed_query = preprocess_query(user_message, language)
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
                # Adjust threshold for different languages
                threshold = 0.15 if language == "ku" else 0.2
                
                if complexity == "detailed":
                    threshold *= 0.8  # Lower threshold for detailed queries
                
                if similarity > threshold:
                    # Language-aware truncation
                    if len(rec.value) > char_limit:
                        if language == "ku":
                            # For Kurdish, truncate at word boundaries
                            words = rec.value[:char_limit].split()
                            truncated_value = ' '.join(words[:-1]) + "..."
                        else:
                            truncated_value = rec.value[:char_limit] + "..."
                    else:
                        truncated_value = rec.value
                    
                    scored.append((similarity, f"• {rec.key}: {truncated_value}"))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [entry for _, entry in scored[:max_records]]
    finally:
        db.close()

def classify_query_complexity(query: str, language: str) -> str:
    """Classify query complexity with language awareness"""
    query_lower = query.lower()
    
    if language == "ku":
        # Kurdish complexity patterns
        simple_patterns = [
            r'\b(سڵاو|بەخێربێی|سوپاس|زۆر سوپاس)\b',  # greetings, thanks
            r'\bناوت چییە\b',  # w
            r'\bتۆ کێیت\b',   #
            r'\bچۆنی\b'       
        ]
        
        detailed_patterns = [
            r'\b(چۆن|چۆنیەتی|چ هەنگاوەکان|پێداویستی|پرۆسە)\b',  # how, requirements, process
            r'\b(باسی.*بکە|ڕوونی بکەرەوە|بڵێ|چی|چییە)\b',        # tell about, explain
            r'\b(وەرگرتن|بەرنامە|کۆرس|پلە|مامۆستا|بەش)\b',        # admission, program, course
            r'\b(ئامرازەکان|خزمەتگوزارییەکان|کەمپەس|کتێبخانە)\b', # facilities, services
            r'\b(کرێ|خەرجی|بورس|دارایی)\b',                      # fees, scholarship
            r'\b(کەی|کوێ|بۆچی|کام)\b.*؟'                        # when, where, why, which
        ]
        
    else:
        # English patterns (existing)
        simple_patterns = [
            r'\b(hi|hello|hey|thanks|thank you)\b',
            r'\bwhat is your name\b',
            r'\bwho are you\b',
            r'\bhow are you\b'
        ]
        
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
    elif len(query.split()) > 8:  # Adjusted for Kurdish (fewer words typically)
        return "detailed"
    else:
        return "medium"

def create_adaptive_system_prompt(context_lines: List[str], language: str, complexity: str) -> str:
    """Create adaptive system prompt based on language and complexity"""
    if language == "ku":
        base_prompt = BASE_PROMPT_SIMPLE_KU if complexity == "simple" else BASE_PROMPT_DETAILED_KU
    else:
        base_prompt = BASE_PROMPT_SIMPLE_EN if complexity == "simple" else BASE_PROMPT_DETAILED_EN
    
    if not context_lines:
        return base_prompt
    
    # Add context with language and complexity-appropriate instructions
    context = "\n".join(context_lines)
    
    if language == "ku":
        if complexity == "detailed":
            instruction = "\n\nبە بەکارهێنانی زانیارییەکانی خوارەوە، وەڵامێکی تەواو بدەرەوە لەگەڵ وردەکارییە تایبەتەکان، نموونەکان، و ڕێنمایی هەنگاو بە هەنگاو لە شوێنی پێویستدا:"
        else:
            instruction = "\n\nزانیاری پەیوەندیدار:"
    else:
        if complexity == "detailed":
            instruction = "\n\nUsing the information below, provide a comprehensive answer with specific details, examples, and step-by-step guidance where applicable:"
        else:
            instruction = "\n\nRelevant information:"
    
    return f"{base_prompt}{instruction}\n{context}"

def ask_claude(prompt: str) -> str:
    """Language-aware Claude API call with optimized token management"""
    try:
        # Check cache first
        cache_key = get_cache_key(prompt)
        if cache_key in response_cache:
            logging.info(f"Cache hit for query: {prompt[:50]}...")
            return response_cache[cache_key]

        # Detect language and classify complexity
        language = detect_language(prompt)
        complexity = classify_query_complexity(prompt, language)
        
        # Get language-appropriate limits
        token_config = get_adaptive_token_limits(language, complexity)
        
        # Fetch context with language awareness
        if complexity == "simple":
            context_lines = []
            system_prompt = BASE_PROMPT_SIMPLE_KU if language == "ku" else BASE_PROMPT_SIMPLE_EN
        else:
            context_lines = fetch_relevant_info(prompt, language, complexity)
            system_prompt = create_adaptive_system_prompt(context_lines, language, complexity)

        # Estimate total prompt tokens with safety margin
        estimated_prompt_tokens = estimate_tokens_by_language(system_prompt + prompt, language)
        
        # Add 20% safety margin for Kurdish due to tokenization unpredictability
        if language == "ku":
            estimated_prompt_tokens = int(estimated_prompt_tokens * 1.2)
        
        # Adjust max_tokens if prompt is large (4096 token model limit)
        max_output_tokens = token_config["max_tokens"]
        total_budget = 4000  # Conservative budget leaving room for model overhead
        
        if estimated_prompt_tokens > total_budget * 0.7:  # If prompt uses >70% of budget
            max_output_tokens = max(100, total_budget - estimated_prompt_tokens)
            logging.warning(f"Large prompt detected ({estimated_prompt_tokens} tokens), reducing output to {max_output_tokens}")

        # API call with language-aware parameters
        response = anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=max_output_tokens,
            temperature=token_config["temperature"],
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = response.content[0].text
        
        # Cache the response
        response_cache[cache_key] = answer
        
        # Enhanced logging with language and complexity info
        input_tokens = response.usage.input_tokens if hasattr(response, 'usage') else 0
        output_tokens = response.usage.output_tokens if hasattr(response, 'usage') else 0
        logging.info(f"Language: {language}, Complexity: {complexity}, Estimated: {estimated_prompt_tokens}, Actual - Input: {input_tokens}, Output: {output_tokens}")
        
        return answer
        
    except (RateLimitError, APIError) as e:
        logging.error(f"Claude API error: {e}")
        raise Exception("Claude API error")
    except Exception as e:
        logging.error(f"Unexpected Claude error: {e}")
        raise

def clear_cache():
    """Clear response cache - useful for production management"""
    response_cache.clear()
    embed_text_cached.cache_clear()
    logging.info("Caches cleared")

def cleanup_cache():
    """Remove old cache entries to prevent memory bloat"""
    if len(response_cache) > 1000:  # Keep only 1000 most recent
        keys_to_remove = list(response_cache.keys())[:-500]
        for key in keys_to_remove:
            del response_cache[key]
        logging.info("Cache cleanup completed")