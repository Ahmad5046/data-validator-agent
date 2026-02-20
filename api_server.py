# api_server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aiohttp
import asyncio
import os
from contextlib import asynccontextmanager

# Lifespan handler for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create a reusable session
    app.state.session = aiohttp.ClientSession()
    # Optional: semaphore to limit concurrent requests to OpenRouter
    app.state.semaphore = asyncio.Semaphore(100)  # max 100 concurrent outgoing requests
    yield
    # Shutdown: close the session
    await app.state.session.close()

app = FastAPI(
    title="Data Validator Agent",
    description="AI agent that validates data for other AI agents",
    version="1.0.0",
    lifespan=lifespan
)

# Request/Response models
class DataRequest(BaseModel):
    data: str

class DataResponse(BaseModel):
    result: str
    price: float

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
PRICE_PER_REQUEST = 0.01
TIMEOUT_SECONDS = 30  # Timeout for each OpenRouter call

async def check_data(data: str) -> str:
    """Use shared session to call OpenRouter API"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",
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
    
    # Use semaphore to limit concurrent requests if needed
    async with app.state.semaphore:
        try:
            async with app.state.session.post(
                url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"OpenRouter Error: {resp.status}: {text}")
                result_json = await resp.json()
                return result_json['choices'][0]['message']['content']
        except asyncio.TimeoutError:
            raise Exception("OpenRouter request timed out")
        except aiohttp.ClientError as e:
            raise Exception(f"Network error: {str(e)}")

@app.get("/")
def home():
    return {"message": "Data Validator Agent is running!", "price_per_request": f"${PRICE_PER_REQUEST}"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/check", response_model=DataResponse)
async def check_data_endpoint(request: DataRequest):
    try:
        result = await check_data(request.data)
        return DataResponse(result=result, price=PRICE_PER_REQUEST)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# For local run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
