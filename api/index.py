from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="HeatOps AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return HTMLResponse("<h1>HeatOps AI is live!</h1>")

@app.get("/health")
def health():
    return {"status": "ok"}