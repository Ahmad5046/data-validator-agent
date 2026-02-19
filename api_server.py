# api_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aiohttp
import asyncio
import os

app = FastAPI(title="Data Validator Agent", description="AI agent that validates data for other AI agents", version="1.0.0")

# Request body ka format define karo
class DataRequest(BaseModel):
    data: str  # User jo data check karwana chahta hai

# Response body ka format
class DataResponse(BaseModel):
    result: str  # Agent ka jawab
    price: float  # Kitne paise lagay

# OpenRouter API key environment variable se lo (secure rakho)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
PRICE_PER_REQUEST = 0.01  # $0.01 per request

async def check_data(data: str) -> str:
    """Tera original agent ka logic yahan copy karo"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",  # Apni website dalo
        "X-Title": "Data Validator Agent"
    }
    
    prompt = f"""
    You are an expert data checker agent. Your task is to verify the given data.
    Data: {data}
    Is this data correct? If not, what is the error?
    Reply only with "CORRECT" or "WRONG: describe the error".
    """
    
    payload = {
        "model": "mistralai/mixtral-8x7b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"OpenRouter Error: {resp.status}: {text}")
            result = await resp.json()
            return result['choices'][0]['message']['content']

@app.get("/")
def home():
    return {"message": "Data Validator Agent is running!", "price_per_request": f"${PRICE_PER_REQUEST}"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/check", response_model=DataResponse)
async def check_data_endpoint(request: DataRequest):
    """
    Yeh main API endpoint hai. Yahan POST request bhejni hai data ke saath.
    """
    try:
        result = await check_data(request.data)
        return DataResponse(result=result, price=PRICE_PER_REQUEST)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Local run karne ke liye (terminal mein: uvicorn api_server:app --reload)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)