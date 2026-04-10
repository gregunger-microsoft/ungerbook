import json
import logging
import os
import sys

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncAzureOpenAI

from app.config import load_config
from app.models.personality import Personality
from app.repositories.db import init_database
from app.repositories.session_repository import SessionRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.memory_repository import MemoryRepository
from app.services.personality_engine import PersonalityEngine
from app.services.memory_service import MemoryService
from app.services.orchestrator import Orchestrator
from app.websocket.handler import WebSocketHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Load config ---
try:
    config = load_config()
except ValueError as e:
    logger.error(str(e))
    sys.exit(1)

logger.info("Configuration loaded successfully")
logger.info(f"  Endpoint: {config.azure_openai_endpoint}")
logger.info(f"  Deployment: {config.azure_openai_deployment}")
logger.info(f"  Conversation mode: {config.conversation_mode}")
logger.info(f"  Streaming: {config.enable_streaming}")
logger.info(f"  Database: {config.database_path}")

# --- Load personalities ---
if not os.path.exists(config.personalities_file):
    logger.error(f"Personalities file not found: {config.personalities_file}")
    sys.exit(1)

with open(config.personalities_file, "r", encoding="utf-8") as f:
    raw_personalities = json.load(f)

all_personalities: dict[str, Personality] = {}
for p in raw_personalities:
    personality = Personality(
        id=p["id"],
        name=p["name"],
        role=p["role"],
        avatar_color=p["avatar_color"],
        expertise_domain=p["expertise_domain"],
        communication_style=p["communication_style"],
        system_prompt=p["system_prompt"],
    )
    all_personalities[personality.id] = personality

logger.info(f"  Loaded {len(all_personalities)} personalities")

# --- Azure OpenAI client (singleton) ---
openai_client = AsyncAzureOpenAI(
    azure_endpoint=config.azure_openai_endpoint,
    api_key=config.azure_openai_api_key,
    api_version=config.azure_openai_api_version,
)

# --- Repositories ---
session_repo = SessionRepository(config.database_path)
message_repo = MessageRepository(config.database_path)
memory_repo = MemoryRepository(config.database_path)

# --- Services ---
personality_engine = PersonalityEngine(config, openai_client)
memory_service = MemoryService(config, memory_repo, message_repo, openai_client)
orchestrator = Orchestrator(
    config, personality_engine, memory_service, session_repo, message_repo, all_personalities
)

# --- WebSocket handler ---
ws_handler = WebSocketHandler(orchestrator)

# --- FastAPI app ---
app = FastAPI(title="Ungerbook", version="1.0.0")


@app.on_event("startup")
async def startup() -> None:
    await init_database(config.database_path)
    os.makedirs(config.session_export_dir, exist_ok=True)
    logger.info("Database initialized")
    logger.info("Moltbook ready at http://localhost:8000")


@app.get("/api/personalities")
async def get_personalities() -> JSONResponse:
    return JSONResponse([
        {
            "id": p.id,
            "name": p.name,
            "role": p.role,
            "avatar_color": p.avatar_color,
            "expertise_domain": p.expertise_domain,
            "communication_style": p.communication_style,
        }
        for p in all_personalities.values()
    ])


@app.get("/api/sessions")
async def get_sessions() -> JSONResponse:
    sessions = await session_repo.list_all()
    return JSONResponse([
        {
            "id": s.id,
            "topic": s.topic,
            "created_at": s.created_at,
            "ended_at": s.ended_at,
            "personality_ids": s.personality_ids,
        }
        for s in sessions
    ])


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> JSONResponse:
    import os as _os
    await session_repo.delete(session_id)
    export_path = _os.path.join(config.session_export_dir, f"{session_id}.json")
    if _os.path.exists(export_path):
        _os.remove(export_path)
    return JSONResponse({"status": "deleted"})


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str) -> JSONResponse:
    messages = await message_repo.get_by_session(session_id)
    personality_map = {p.id: p for p in all_personalities.values()}
    return JSONResponse([
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": m.sender_name,
            "content": m.content,
            "timestamp": m.timestamp,
            "avatar_color": personality_map[m.sender_id].avatar_color if m.sender_id in personality_map else "#7f8c8d",
            "role": personality_map[m.sender_id].role if m.sender_id in personality_map else "Human",
        }
        for m in messages
    ])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_handler.handle(websocket)


# Mount static files last so API routes take priority
frontend_dir = os.path.join(os.path.dirname(__file__), "app", "frontend-dist")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=False)
