import pytest
import httpx

base_url = 'http://localhost:8000'

#need to have 'test' in the test functions for pytest to detect them

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