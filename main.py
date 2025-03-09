from fastapi import FastAPI
import uvicorn
from app.api import router, add_cors_middleware, add_cors_headers_middleware
from app.config import init_config

app = FastAPI(
    title="OpenAI Stream Mocker",
    description="A service that mocks OpenAI streaming responses for testing",
    version="1.0.0"
)

# Add CORS middleware
add_cors_middleware(app)

# Add middleware to add CORS headers to all responses
add_cors_headers_middleware(app)

# Include the API router
app.include_router(router)

# Initialize configuration at startup
@app.on_event("startup")
async def startup_event():
    """Initialize configuration when the application starts"""
    init_config()
    print("Configuration initialized")

if __name__ == "__main__":
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
    print("OpenAI Stream Mocker started at http://localhost:8000")
