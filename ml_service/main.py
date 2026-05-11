"""
ML Service – FastAPI entry point.

Standalone microservice for demand prediction model training and serving.
Run with:  uvicorn main:app --port 8100 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import router
from portfolio_routes import router as portfolio_router

app = FastAPI(
    title="WMS ML Service",
    description="On-demand demand prediction for warehouse products",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(portfolio_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ml-service"}
