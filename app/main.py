"""
app/main.py — FastAPI entry point. Keep this minimal.
All routes live in app/routers/
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers import chat, ingest, mindmap, revision, documents
from app.routers import detailed_mindmap

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
load_dotenv()

app = FastAPI(title="AI Research Helper", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(chat.router)
app.include_router(ingest.router)
app.include_router(mindmap.router)
app.include_router(revision.router)
app.include_router(documents.router)
app.include_router(detailed_mindmap.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}