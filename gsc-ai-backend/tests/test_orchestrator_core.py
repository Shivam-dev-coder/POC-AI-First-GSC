import pytest

from orchestrator import prompt_manager
from orchestrator import intent_handler
from orchestrator import schemas
from orchestrator.main import DriverRegistry


def test_prompt_manager_add_and_clear_override():
    # Start from a clean state
    prompt_manager.clear_overrides()
    assert prompt_manager.active_overrides == []

    base = prompt_manager.get_full_prompt()
    assert "You are the AI assistant for GSC" in base

    # Add an override and ensure it appears in the full prompt
    prompt_manager.add_override("Remove the geofence")
    assert "Remove the geofence" in prompt_manager.active_overrides
    full = prompt_manager.get_full_prompt()
    assert "LIVE DASHBOARD OVERRIDES" in full
    assert "1. Remove the geofence" in full

    # Clear and ensure the overrides list is emptied
    prompt_manager.clear_overrides()
    assert prompt_manager.active_overrides == []


def test_format_distance():
    # metres formatting
    assert intent_handler._format_distance(0.45) == "450 m"
    # kilometres formatting
    assert intent_handler._format_distance(1.8) == "1.8 km"


def test_haversine_zero_distance():
    # identical points → zero distance
    assert intent_handler._haversine(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-9)


def test_intentpacket_parsed_payload_unknown_raises():
    pkt = schemas.IntentPacket(intent_type="no_such", payload={})
    with pytest.raises(ValueError):
        pkt.parsed_payload()


def test_driver_registry_register_unregister():
    reg = DriverRegistry()

    class DummyWS:
        pass

    ws = DummyWS()
    reg.register(42, ws)
    assert 42 in reg.online_driver_ids()

    reg.unregister_ws(ws)
    assert 42 not in reg.online_driver_ids()
