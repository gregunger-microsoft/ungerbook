import json
import logging
import os
import sys

from fastapi import FastAPI, WebSocket, Request, Cookie
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
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

from app.repositories.guestbook_repository import GuestbookRepository
guestbook_repo = GuestbookRepository(config.database_path)

from app.services.email_service import EmailService
email_service = EmailService(config)

# --- Services ---
personality_engine = PersonalityEngine(config, openai_client)
memory_service = MemoryService(config, memory_repo, message_repo, openai_client)
orchestrator = Orchestrator(
    config, personality_engine, memory_service, session_repo, message_repo, all_personalities
)

# --- WebSocket handler ---
ws_handler = WebSocketHandler(orchestrator, guestbook_repo=guestbook_repo)

# --- Version ---
_version_file = os.path.join(os.path.dirname(__file__), "VERSION")
APP_VERSION = open(_version_file).read().strip() if os.path.exists(_version_file) else "dev"

# --- FastAPI app ---
app = FastAPI(title="Ungerbook", version=APP_VERSION)

# --- Guestbook middleware ---
EXEMPT_PATHS = {"/guestbook", "/guestbook.html", "/admin", "/admin.html",
                "/api/version", "/api/guestbook/register", "/api/guestbook/activate",
                "/api/guestbook/enter", "/api/guestbook/admin", "/ws"}


class GuestbookGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in EXEMPT_PATHS):
            return await call_next(request)
        # Check for guestbook_token cookie
        token = request.cookies.get("guestbook_token")
        if not token:
            return RedirectResponse(url="/guestbook", status_code=302)
        is_valid = await guestbook_repo.validate_code(token)
        if not is_valid:
            response = RedirectResponse(url="/guestbook", status_code=302)
            response.delete_cookie("guestbook_token")
            return response
        return await call_next(request)


app.add_middleware(GuestbookGateMiddleware)

# --- Frontend dir (used by guestbook/admin routes and static mount) ---
frontend_dir = os.path.join(os.path.dirname(__file__), "app", "frontend-dist")


@app.get("/api/version")
async def get_version() -> JSONResponse:
    return JSONResponse({"version": APP_VERSION})


# --- Guestbook endpoints ---
@app.get("/guestbook")
async def guestbook_page() -> HTMLResponse:
    guestbook_path = os.path.join(frontend_dir, "guestbook.html")
    with open(guestbook_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/admin")
async def admin_page() -> HTMLResponse:
    admin_path = os.path.join(frontend_dir, "admin.html")
    with open(admin_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/api/guestbook/register")
async def guestbook_register(request: Request) -> JSONResponse:
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not email or "@" not in email:
        return JSONResponse({"detail": "Valid email required."}, status_code=400)
    if not email.endswith("@microsoft.com"):
        return JSONResponse({"detail": "Only @microsoft.com email addresses are allowed."}, status_code=403)
    entry = await guestbook_repo.register(email)
    sent = email_service.send_activation_email(email, entry.activation_code)
    if not sent:
        return JSONResponse({"detail": "Failed to send activation email. Try again."}, status_code=500)
    return JSONResponse({
        "status": "email_sent",
        "message": f"Activation link sent to {email}. Check your inbox.",
    })


@app.post("/api/guestbook/activate")
async def guestbook_activate(request: Request) -> JSONResponse:
    body = await request.json()
    code = body.get("code", "").strip().upper()
    if not code or len(code) != 6:
        return JSONResponse({"detail": "6-character activation code required."}, status_code=400)
    entry = await guestbook_repo.activate(code)
    if not entry:
        return JSONResponse({"detail": "Invalid or expired activation code."}, status_code=401)
    response = JSONResponse({"status": "activated", "expires_at": entry.expires_at})
    response.set_cookie(
        key="guestbook_token",
        value=entry.activation_code,
        max_age=3600,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/api/guestbook/enter")
async def guestbook_enter(code: str = "") -> RedirectResponse:
    code = code.strip().upper()
    if not code or len(code) != 6:
        return RedirectResponse(url="/guestbook", status_code=302)
    entry = await guestbook_repo.activate(code)
    if not entry:
        return RedirectResponse(url="/guestbook", status_code=302)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="guestbook_token",
        value=entry.activation_code,
        max_age=3600,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/api/guestbook/me")
async def guestbook_me(request: Request) -> JSONResponse:
    token = request.cookies.get("guestbook_token")
    if not token:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    async with __import__("aiosqlite").connect(config.database_path) as db:
        db.row_factory = __import__("aiosqlite").Row
        cursor = await db.execute(
            "SELECT * FROM guestbook WHERE activation_code = ? AND is_active = 1", (token,)
        )
        row = await cursor.fetchone()
    if not row:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return JSONResponse({
        "activation_code": row["activation_code"],
        "email": row["email"],
        "activated_at": row["activated_at"],
        "expires_at": row["expires_at"],
        "tokens_used": row["tokens_used"] if "tokens_used" in row.keys() else 0,
        "max_tokens": row["max_tokens"] if "max_tokens" in row.keys() else 100000,
    })


@app.get("/api/guestbook/admin")
async def guestbook_admin() -> JSONResponse:
    entries = await guestbook_repo.list_all()
    return JSONResponse([
        {
            "id": e.id,
            "email": e.email,
            "activation_code": e.activation_code,
            "created_at": e.created_at,
            "activated_at": e.activated_at,
            "expires_at": e.expires_at,
            "is_active": e.is_active,
            "tokens_used": e.tokens_used,
            "max_tokens": e.max_tokens,
        }
        for e in entries
    ])


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
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
