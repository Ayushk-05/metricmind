from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

@app.get("/")
def root():
    return {"message": "MetricMind API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}