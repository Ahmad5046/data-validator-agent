"""
Complete Data Validator Agent API
Price: $0.10 per request
Includes: OpenAPI spec, Terms, Skyfire webhook
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------- Configuration ----------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ OPENROUTER_API_KEY not set in environment variables")

PRICE_PER_REQUEST = 0.10  # $0.10 per request (premium pricing)
TIMEOUT_SECONDS = 30

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Lifespan for shared session ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create session and semaphore
    app.state.session = aiohttp.ClientSession()
    app.state.semaphore = asyncio.Semaphore(100)  # max 100 concurrent outgoing
    logger.info("🚀 Server starting up...")
    yield
    # Shutdown: close session
    await app.state.session.close()
    logger.info("🛑 Server shut down.")

# ---------- FastAPI App ----------
app = FastAPI(
    title="Data Validator Agent",
    description="AI agent that validates data for other AI agents. $0.10 per request.",
    version="1.0.0",
    lifespan=lifespan
)

# ---------- Pydantic Models ----------
class DataRequest(BaseModel):
    data: str = Field(..., description="The data to validate", example="Bitcoin price is $100,000")

class DataResponse(BaseModel):
    result: str = Field(..., description="Validation result (CORRECT or WRONG with explanation)")
    price: float = Field(..., description="Cost in USD")

# ---------- Helper: Call OpenRouter ----------
async def check_data(data: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("APP_URL", "https://your-app.com"),
        "X-Title": "Data Validator Agent"
    }
    prompt = f"""You are an expert data checker agent. Your task is to verify the given data.
Data: {data}
Is this data correct? If not, what is the error?
Reply only with "CORRECT" or "WRONG: describe the error"."""
    payload = {
        "model": "mistralai/mixtral-8x7b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200
    }
    async with app.state.semaphore:
        try:
            async with app.state.session.post(url, headers=headers, json=payload, timeout=TIMEOUT_SECONDS) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"OpenRouter error {resp.status}: {text[:200]}")
                    raise HTTPException(status_code=502, detail="AI service error")
                result = await resp.json()
                return result['choices'][0]['message']['content'].strip()
        except asyncio.TimeoutError:
            logger.error("OpenRouter timeout")
            raise HTTPException(status_code=504, detail="AI service timeout")
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {str(e)}")
            raise HTTPException(status_code=503, detail="AI service unavailable")

# ---------- API Endpoints ----------
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Data Validator Agent is running!", "price_per_request": f"${PRICE_PER_REQUEST}"}

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "healthy"}

@app.post("/check", response_model=DataResponse)
async def check_data_endpoint(request: DataRequest):
    """Validate the provided data."""
    try:
        result = await check_data(request.data)
        return DataResponse(result=result, price=PRICE_PER_REQUEST)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# ---------- OpenAPI JSON (explicit) ----------
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_json():
    """Return OpenAPI specification in JSON format."""
    return get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

# ---------- Terms of Service (HTML) ----------
TERMS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Terms of Service - Data Validator Agent</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
    </style>
</head>
<body>
    <h1>Terms of Service</h1>
    <p><strong>Last updated:</strong> Feb 21, 2026</p>
    
    <h2>1. Service Description</h2>
    <p>Data Validator Agent provides AI-powered data validation services. It checks facts, logical errors, and misinformation for other AI agents and applications.</p>
    
    <h2>2. Pricing</h2>
    <p>$0.10 per successful request. Payments are processed through Skyfire protocol.</p>
    
    <h2>3. Usage</h2>
    <p>This service is intended for AI agents and developers. You agree not to misuse the API or attempt to reverse-engineer it.</p>
    
    <h2>4. Disclaimer</h2>
    <p>The service provides validation based on AI models. Accuracy is not guaranteed 100%. Use at your own discretion.</p>
    
    <h2>5. Contact</h2>
    <p>Email: your-email@example.com</p>
</body>
</html>
"""

@app.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms():
    return TERMS_HTML

# ---------- Skyfire Webhook (optional) ----------
@app.post("/skyfire-webhook", include_in_schema=False)
async def skyfire_webhook(request: Request):
    """Receive payment notifications from Skyfire."""
    payload = await request.json()
    logger.info(f"Skyfire webhook received: {payload}")
    # Verify signature if needed, then process payment
    # For now, just acknowledge
    return {"status": "received"}

# ---------- Run (for local development) ----------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
