from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api.routes.assistant import router as assistant_router
from app.api.routes.health import router as health_router
from app.core.config import settings

app = FastAPI(title="Blinkit AI Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(assistant_router)
