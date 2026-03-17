"""
main.py

FastAPI application — exposes a WebSocket endpoint for Flutter and REST
endpoints for the web dashboard to manage live prompt overrides.

WebSocket endpoints:
  /ws       — Flutter driver app (intent packets in, JSON responses out)
  /ws/log   — Dashboard live log feed (broadcast-only, read-only for clients)

The LogBroadcaster class keeps a set of connected dashboard clients and
fans out every inbound intent and outbound response as a JSON message so
the dashboard LiveLog component can display them in real time.
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator.intent_handler import HANDLERS
from orchestrator.prompt_manager import (
    get_full_prompt,
    add_override,
    clear_overrides,
    active_overrides,
)
from orchestrator.reasoning import classify_and_execute
from orchestrator.schemas import IntentPacket, DashboardCommand, ServerPushMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Log broadcaster — fan-out to all connected dashboard /ws/log clients
# ---------------------------------------------------------------------------

class LogBroadcaster:
    """Thread-safe set of active dashboard WebSocket connections."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to every connected dashboard client."""
        if not self._clients:
            return
        text = json.dumps(message, default=str)
        dead: set[WebSocket] = set()
        for client in self._clients:
            try:
                await client.send_text(text)
            except Exception:
                dead.add(client)
        self._clients -= dead


log_broadcaster = LogBroadcaster()


# ---------------------------------------------------------------------------
# Driver registry — tracks which driver_id owns which live WebSocket
# ---------------------------------------------------------------------------

class DriverRegistry:
    """Maps driver_id (int) → active Flutter WebSocket connection.

    Filled when a driver_login intent succeeds (response.driver is set).
    Cleared when the WebSocket disconnects.
    """

    def __init__(self) -> None:
        self._connections: dict[int, WebSocket] = {}

    def register(self, driver_id: int, ws: WebSocket) -> None:
        self._connections[driver_id] = ws

    def unregister_ws(self, ws: WebSocket) -> None:
        """Remove any driver whose connection matches *ws*."""
        dead = [did for did, w in self._connections.items() if w is ws]
        for did in dead:
            del self._connections[did]

    def online_driver_ids(self) -> list[int]:
        return list(self._connections.keys())

    async def send_to(self, driver_id: int, message: dict) -> bool:
        """Push *message* to a single driver. Returns False if not connected."""
        ws = self._connections.get(driver_id)
        if ws is None:
            return False
        try:
            await ws.send_text(json.dumps(message, default=str))
            return True
        except Exception:
            del self._connections[driver_id]
            return False

    async def broadcast(self, message: dict) -> list[int]:
        """Push *message* to all connected drivers. Returns list of reached IDs."""
        reached: list[int] = []
        dead: list[int] = []
        text = json.dumps(message, default=str)
        for driver_id, ws in self._connections.items():
            try:
                await ws.send_text(text)
                reached.append(driver_id)
            except Exception:
                dead.append(driver_id)
        for did in dead:
            del self._connections[did]
        return reached


driver_registry = DriverRegistry()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="GSC AI Orchestrator", version="0.1.0")

# Allow the web dashboard (any origin in POC) to call the REST endpoints.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _on_startup() -> None:
    print("\n" + "=" * 60)
    print("GSC AI Orchestrator started")
    print("=" * 60)
    print(get_full_prompt())
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# WebSocket — Flutter connects here
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    logger.info("WebSocket client connected: %s", ws.client)

    try:
        while True:
            raw = await ws.receive_text()

            # --- parse envelope ---
            try:
                data = json.loads(raw)

                # Normalise Flutter's flat event format to the standard envelope.
                # Flutter map screens send:
                #   { "event": "stop_map_opened", "driver_id": "1", ... }
                # The rest of the app sends:
                #   { "intent_type": "driver_login", "payload": { ... } }
                # Both are accepted; flat format is lifted into the standard shape.
                if "event" in data and "intent_type" not in data:
                    _ENVELOPE_KEYS = {"event", "session_id", "timestamp"}
                    data = {
                        "intent_type": data["event"],
                        "payload": {k: v for k, v in data.items()
                                    if k not in _ENVELOPE_KEYS},
                    }

                packet = IntentPacket(**data)
            except Exception as exc:
                await ws.send_text(json.dumps({
                    "error": f"Invalid packet: {exc}"
                }))
                continue

            logger.info("Received intent: %s", packet.intent_type)

            # --- validate payload ---
            try:
                typed_payload = packet.parsed_payload()
            except ValueError as exc:
                await ws.send_text(json.dumps({
                    "error": str(exc)
                }))
                continue

            # --- route to handler ---
            handler = HANDLERS.get(packet.intent_type)
            if handler is None:
                await ws.send_text(json.dumps({
                    "error": f"No handler for intent_type '{packet.intent_type}'"
                }))
                continue

            try:
                response = handler(typed_payload)
                # Merge intent_type into the response so Flutter can match it
                response_dict = response.model_dump(exclude_none=True)
                response_dict["intent_type"] = packet.intent_type
                response_json = json.dumps(response_dict, default=str)
                await ws.send_text(response_json)

                # Register driver on successful login so we can push to them later
                if packet.intent_type == "driver_login" and response.driver is not None:
                    driver_registry.register(response.driver.id, ws)
                    logger.info("Driver %s registered (id=%d)", response.driver.name, response.driver.id)

                # Broadcast inbound intent and outbound response to dashboard
                await log_broadcaster.broadcast({
                    "direction": "in",
                    "intent": packet.intent_type,
                    "payload": data,
                })
                await log_broadcaster.broadcast({
                    "direction": "out",
                    "intent": packet.intent_type,
                    "payload": json.loads(response_json),
                })

            except Exception as exc:
                logger.exception("Handler error for intent '%s'", packet.intent_type)
                error_msg = json.dumps({"error": f"Handler failed: {exc}"})
                await ws.send_text(error_msg)
                await log_broadcaster.broadcast({
                    "direction": "out",
                    "intent": packet.intent_type,
                    "error": f"Handler failed: {exc}",
                })

    except WebSocketDisconnect:
        driver_registry.unregister_ws(ws)
        logger.info("WebSocket client disconnected: %s", ws.client)


# ---------------------------------------------------------------------------
# WebSocket — dashboard live log feed
# ---------------------------------------------------------------------------

@app.websocket("/ws/log")
async def log_endpoint(ws: WebSocket) -> None:
    """Read-only broadcast endpoint. Dashboard clients connect here to
    receive a copy of every Flutter intent and AI response in real time."""
    await log_broadcaster.connect(ws)
    logger.info("Log client connected: %s", ws.client)
    try:
        # Keep the connection open; we don't expect messages from the dashboard.
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        log_broadcaster.disconnect(ws)
        logger.info("Log client disconnected: %s", ws.client)


# ---------------------------------------------------------------------------
# REST — dashboard override management
# ---------------------------------------------------------------------------

class OverrideRequest(BaseModel):
    rule: str


@app.post("/override", status_code=201)
async def post_override(body: OverrideRequest) -> dict:
    """Append a live rule override to the active prompt."""
    rule = body.rule.strip()
    if not rule:
        raise HTTPException(status_code=422, detail="rule must not be empty")
    add_override(rule)
    logger.info("Override added: %s", rule)
    return {"status": "added", "rule": rule, "total_overrides": len(active_overrides)}


@app.delete("/overrides", status_code=200)
async def delete_overrides() -> dict:
    """Remove all active overrides and restore base rules."""
    clear_overrides()
    logger.info("All overrides cleared")
    return {"status": "cleared"}


@app.get("/overrides")
async def get_overrides() -> dict:
    """Return the current list of active override rules."""
    return {"overrides": list(active_overrides)}


# ---------------------------------------------------------------------------
# REST — live driver push notifications
# ---------------------------------------------------------------------------

@app.get("/drivers/online")
async def get_online_drivers() -> dict:
    """Return the list of driver IDs that currently have an active WebSocket."""
    return {"driver_ids": driver_registry.online_driver_ids()}


@app.post("/command", status_code=200)
async def post_command(body: DashboardCommand) -> dict:
    """
    Unified Command Centre endpoint.

    The AI classifies the plain-English command as either:
      - "override" → adds a rule to the live system prompt
      - "popup"    → pushes a ServerPushMessage to relevant connected drivers

    Returns a dict with a "type" field so the dashboard can show the
    correct toast without needing to know which path was taken.
    """
    command = body.command.strip()
    if not command:
        raise HTTPException(status_code=422, detail="command must not be empty")

    connected_ids = driver_registry.online_driver_ids()
    result = classify_and_execute(command, connected_ids)

    if result["type"] == "override":
        rule = result["rule"]
        add_override(rule)
        logger.info("Command classified as override: %s", rule)
        return {"type": "override", "rule": rule}

    # popup path
    popup_data = result.get("popup", {})
    target      = result.get("target", "all")
    driver_ids  = result.get("driver_ids", [])

    push = ServerPushMessage(popup=popup_data)
    message = push.model_dump()

    if target == "all":
        reached = await driver_registry.broadcast(message)
        not_connected: list = []
    else:
        reached = []
        not_connected = []
        for did in driver_ids:
            ok = await driver_registry.send_to(int(did), message)
            (reached if ok else not_connected).append(did)

    logger.info("Popup push — target=%s reached=%s not_connected=%s", target, reached, not_connected)
    return {
        "type": "popup",
        "status": "sent",
        "target": target,
        "reached": reached,
        "not_connected": not_connected,
    }
