from fastapi import FastAPI

app = FastAPI(title="OpenAI Stream Mocker")

from app.api import router as api_router
app.include_router(api_router)
