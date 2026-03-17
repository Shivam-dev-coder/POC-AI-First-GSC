"""
reasoning.py

Sends the current intent + MCP context data to OpenAI and parses the
structured JSON response back into an OrchestratorResponse object.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

from orchestrator.schemas import (
    OrchestratorResponse,
    DeliverButton,
    Popup,
    PopupButton,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Lazy-initialised on first call so the module loads cleanly without a key present.
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


_model = os.getenv("OPENAI_MODEL", "gpt-4o")

# ---------------------------------------------------------------------------
# Safe fallback — returned whenever OpenAI call or JSON parse fails
# ---------------------------------------------------------------------------

def _safe_default(reason: str) -> OrchestratorResponse:
    """Return a red, non-blocking error response the driver can dismiss."""
    return OrchestratorResponse(
        deliver_button=DeliverButton(color="#DC2626"),
        popup=Popup(
            show=True,
            blocking=False,
            title="Something went wrong",
            message="Unable to process your request. Please contact support.",
            buttons=[PopupButton(label="OK", action="dismiss", visible=True)],
        ),
    )


# ---------------------------------------------------------------------------
# Core reasoning function
# ---------------------------------------------------------------------------

def reason(
    intent: str,
    context_data: dict[str, Any],
    full_prompt: str,
) -> OrchestratorResponse:
    """
    Ask OpenAI to reason over the intent and MCP context, then return a
    validated OrchestratorResponse.

    Args:
        intent:       The intent_type string (e.g. "driver_login").
        context_data: Dict of everything fetched from MCP tools for this intent,
                      plus the original payload fields.
        full_prompt:  The complete system prompt from prompt_manager.get_full_prompt().

    Returns:
        A validated OrchestratorResponse, or a safe error default on failure.
    """
    user_message = json.dumps(
        {
            "intent": intent,
            "context": context_data,
        },
        indent=2,
        default=str,  # serialise any non-JSON-native types (e.g. Pydantic models)
    )

    try:
        response = _get_client().chat.completions.create(
            model=_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": full_prompt},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.2,   # low temperature — we want consistent, rule-following output
            max_tokens=2048,
        )

        raw_json = response.choices[0].message.content

        # Parse into dict first so we can log it cleanly before validation
        data = json.loads(raw_json)
        logger.debug("OpenAI raw response for intent '%s': %s", intent, raw_json)

        return OrchestratorResponse(**data)

    except json.JSONDecodeError as exc:
        logger.error("JSON parse failure for intent '%s': %s", intent, exc)
        return _safe_default("json_parse_error")

    except Exception as exc:  # noqa: BLE001 — intentional broad catch for POC resilience
        logger.error("OpenAI call failed for intent '%s': %s", intent, exc)
        return _safe_default("openai_error")


# ---------------------------------------------------------------------------
# Dashboard Command Centre — classify and execute
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM_PROMPT = """
You are a delivery operations AI assistant. You receive plain-English commands
from an operations manager in a web dashboard. You must classify the command as
either a RULE OVERRIDE or a POPUP MESSAGE and respond ONLY in valid JSON —
no markdown, no explanation, nothing else.

If the command changes how the delivery app behaves going forward (location
rules, scan requirements, required items, blocking drivers, delivery conditions):
{
  "type": "override",
  "rule": "a clear, concise instruction sentence cleaned up from the command"
}

Override classification examples — these MUST be classified as "override" not "popup":
  "Remove the geofence"                → override
  "Disable location check"             → override
  "Allow delivery from anywhere"       → override
  "Set geofence to 500 metres"         → override
  "Geofence warning only, don't block" → override
  "Hard block stop 4"                  → override
  "Change radius to 100m"              → override
  "Location is just a warning now"     → override

If the command is something to immediately notify drivers about (traffic,
route changes, urgent announcements, delivery updates, time-sensitive info):
{
  "type": "popup",
  "target": "all",
  "driver_ids": [],
  "popup": {
    "show": true,
    "blocking": false,
    "title": "short title you generate based on context",
    "message": "the message to show the driver, written clearly",
    "buttons": [
      { "label": "OK", "action": "acknowledge", "visible": true }
    ]
  }
}

Rules for popup classification:
- blocking: use true for urgent/safety messages, false for informational ones
- buttons — choose the most appropriate set:
    informational update        → [OK]
    action required             → [OK, Cancel]
    route or delivery override  → [Override, Cancel]
    critical safety/compliance  → [Override, OK, Cancel]
- Always generate a short, clear title even if the user did not specify one
- If the command mentions specific driver IDs (e.g. "driver 1", "driver id 2"),
  set target to "specific" and list those IDs as strings in driver_ids
- Otherwise set target to "all" and driver_ids to []
- Button actions must be lowercase strings:
    "acknowledge", "override", "cancel"
""".strip()


def classify_and_execute(command: str, connected_driver_ids: list) -> dict:
    """
    Ask OpenAI to classify a plain-English dashboard command as either a rule
    override or an immediate popup push.

    Args:
        command:              The raw text from the Command Centre textarea.
        connected_driver_ids: List of currently-online driver IDs (passed in
                              context so the AI can note who is reachable).

    Returns:
        dict with key "type" == "override" | "popup"

        Override:  { "type": "override", "rule": str }
        Popup:     { "type": "popup", "target": "all"|"specific",
                     "driver_ids": list, "popup": dict }

        Falls back to a safe override entry on any parsing failure.
    """
    context_note = (
        f"Currently connected driver IDs: {connected_driver_ids}"
        if connected_driver_ids
        else "No drivers are currently connected."
    )
    user_message = f"{command}\n\n[Context: {context_note}]"

    try:
        response = _get_client().chat.completions.create(
            model=_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.2,
            max_tokens=512,
        )

        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        logger.debug("classify_and_execute raw response: %s", raw_json)

        # Basic validation — ensure we got a known type
        if data.get("type") not in ("override", "popup"):
            raise ValueError(f"Unexpected classification type: {data.get('type')!r}")

        return data

    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("classify_and_execute parse failure: %s", exc)
        return {"type": "override", "rule": command}

    except Exception as exc:  # noqa: BLE001
        logger.error("classify_and_execute OpenAI call failed: %s", exc)
        return {"type": "override", "rule": command}
