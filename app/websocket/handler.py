import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.services.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class WebSocketHandler:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator
        self._connection: WebSocket | None = None

    async def _send_json(self, data: dict) -> None:
        if self._connection is not None:
            try:
                await self._connection.send_json(data)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")

    async def handle(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connection = websocket
        self._orchestrator.set_send_callback(self._send_json)

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_json({"type": "error", "message": "Invalid JSON"})
                    continue

                msg_type = data.get("type")

                if msg_type == "start_session":
                    topic = data.get("topic", "").strip()
                    personality_ids = data.get("personalities", [])
                    if not topic:
                        await self._send_json({"type": "error", "message": "Topic is required"})
                        continue
                    if not personality_ids:
                        await self._send_json({"type": "error", "message": "Select at least one personality"})
                        continue

                    session = await self._orchestrator.start_session(topic, personality_ids)
                    await self._send_json({
                        "type": "session_started",
                        "session_id": session.id,
                        "topic": session.topic,
                    })

                elif msg_type == "message":
                    content = data.get("content", "").strip()
                    if not content:
                        continue
                    await self._orchestrator.handle_human_message(content)

                elif msg_type == "mute":
                    pid = data.get("personality_id")
                    if pid:
                        self._orchestrator.mute_personality(pid)
                        await self._send_json({"type": "muted", "personality_id": pid})

                elif msg_type == "unmute":
                    pid = data.get("personality_id")
                    if pid:
                        self._orchestrator.unmute_personality(pid)
                        await self._send_json({"type": "unmuted", "personality_id": pid})

                elif msg_type == "end_session":
                    await self._orchestrator.end_session()
                    await self._send_json({"type": "session_ended"})

                elif msg_type == "pause":
                    self._orchestrator.pause()
                    await self._send_json({"type": "paused"})

                elif msg_type == "resume":
                    self._orchestrator.resume()
                    await self._send_json({"type": "resumed"})

                else:
                    await self._send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self._connection = None
