import pytest
import httpx

base_url = 'http://127.0.0.1:8000'

def test_home():
    r = httpx.get(f"{base_url}/")
    assert r.status_code == 200
    
def test_about():
    r = httpx.get(f"{base_url}/about")
    assert r.status_code == 200

def test_contactus():
    r = httpx.get(f"{base_url}/contact")
    assert r.status_code == 200

def test_chat_post():
    r = httpx.post(f"{base_url}/chat", json={"message": "hello"})
    assert r.status_code == 200
    return "response" in r.json()