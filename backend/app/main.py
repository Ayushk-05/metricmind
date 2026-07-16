from fastapi import FastAPI

app = FastAPI(
    title="MetricMind API",
    version="0.1.0"
)

@app.get("/")
def root():
    return {
        "message": "MetricMind API is running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }