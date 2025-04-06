from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import quiz

app = FastAPI(
    title="Quiz API",
    description="API for quiz questions and recommendations",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(quiz.router)