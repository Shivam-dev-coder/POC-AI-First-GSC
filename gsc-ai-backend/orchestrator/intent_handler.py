"""
intent_handler.py

One handler function per Flutter intent type. Each handler fetches the
relevant data from the MCP tools and forwards it to reasoning.py.
"""

from __future__ import annotations

import math
from typing import Any

from orchestrator.schemas import (
    DriverLoginPayload,
    StopSelectedPayload,
    MapLoadedPayload,
    ProductScreenLoadedPayload,
    ItemScannedPayload,
    DeliverTappedPayload,
    CountScreenLoadedPayload,
    UserIdlePayload,
    RouteMapPayload,
    StopMapPayload,
    StartDeliveryPayload,
    FinishDeliveryPayload,
    OrchestratorResponse,
    DeliverButton,
    DriverInfo,
    RouteSchema,
    StopSchema,
    Popup,
    PopupButton,
    Spotlight,
    SectionSchema,
    ProductItemSchema,
)
from orchestrator.prompt_manager import get_full_prompt, active_overrides
from orchestrator import reasoning


# ---------------------------------------------------------------------------
# MCP tool adapter
#
# The MCP tools live inside register(mcp) as nested functions decorated with
# @mcp.tool(). We extract them without modifying the MCP server by passing a
# lightweight registry shim that captures each decorated function by name.
# ---------------------------------------------------------------------------

class _ToolRegistry:
    """Mimics just enough of FastMCP for register() to attach tools."""

    def tool(self):
        def decorator(fn):
            setattr(self, fn.__name__, fn)
            return fn
        return decorator


_registry = _ToolRegistry()

# Import and register all tool modules against our shim
from mcp_server.tools import driver as _driver_module
from mcp_server.tools import stops as _stops_module
from mcp_server.tools import products as _products_module

_driver_module.register(_registry)
_stops_module.register(_registry)
_products_module.register(_registry)

# Typed aliases for convenience and IDE support
_get_driver_profile    = _registry.get_driver_profile
_get_driver_by_name    = _registry.get_driver_by_name
_get_route_for_driver  = _registry.get_route_for_driver
_get_stop_details      = _registry.get_stop_details
_get_products          = _registry.get_products
_reconcile_inventory   = _registry.reconcile_inventory
_get_route_summary     = _registry.get_route_summary
_get_next_stop         = _registry.get_next_stop


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _reason(intent: str, context: dict[str, Any]) -> OrchestratorResponse:
    return reasoning.reason(intent, context, get_full_prompt())


def _build_route(route_data: dict) -> RouteSchema:
    """Convert raw dict from get_route_for_driver into a typed RouteSchema."""
    return RouteSchema(
        route_id=route_data.get("route_id"),
        route_name=route_data.get("route_name"),
        route_status=route_data.get("route_status"),
        stops=[StopSchema(**s) for s in route_data.get("stops", [])],
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometres between two points
    specified in decimal degrees using the Haversine formula.
    Sufficient precision for the 200 m start_delivery_enabled threshold.
    """
    R = 6371.0  # mean Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _format_distance(distance_km: float) -> str:
    """Return a human-readable distance string (metres below 1 km, km above)."""
    if distance_km < 1.0:
        return f"{int(distance_km * 1000)} m"
    return f"{distance_km:.1f} km"


# ---------------------------------------------------------------------------
# Handlers — one per intent type
# ---------------------------------------------------------------------------

def handle_driver_login(payload: DriverLoginPayload) -> OrchestratorResponse:
    """
    Resolves the driver by id, name, or username, then immediately fetches
    their full route so the app can display stops without a second request.

    Fast path (no active overrides): DB lookups only, no OpenAI call.
    Override path (overrides present): passes driver + route context to
    OpenAI so natural-language rules are respected.

    The driver profile and route are always attached to the response so
    Flutter can read them regardless of which path was taken.
    """
    from orchestrator.prompt_manager import active_overrides

    # Resolve profile: prefer driver_id, fall back to name / username
    profile: dict[str, Any] = {"error": "No driver_id or name provided"}
    if payload.driver_id is not None:
        profile = _get_driver_profile(payload.driver_id)
    elif payload.name:
        profile = _get_driver_by_name(payload.name)
    elif payload.username:
        profile = _get_driver_by_name(payload.username)

    # Driver not found → reject immediately, no AI needed
    if "error" in profile:
        return OrchestratorResponse(
            deliver_button=DeliverButton(color="#DC2626"),
            popup=Popup(
                show=True,
                blocking=True,
                title="Driver Not Found",
                message="Could not find your driver profile. Please check your ID or contact support.",
                buttons=[PopupButton(label="OK", action="dismiss", visible=True)],
            ),
        )

    # Fetch route for this driver
    driver_id  = profile["id"]
    route_data = _get_route_for_driver(driver_id)
    route      = _build_route(route_data)

    # Override path — let OpenAI evaluate dashboard rules against this driver
    if active_overrides:
        context: dict[str, Any] = {
            "driver_id":     driver_id,
            "driver_profile": profile,
            "route":          route_data,
        }
        ai_response = _reason("driver_login", context)
        # Always attach the resolved driver profile and route so Flutter can read them
        ai_response.driver = DriverInfo(**profile)
        ai_response.route  = route
        return ai_response

    # Fast path — no overrides active, build response directly
    spotlight = Spotlight()
    if profile.get("is_new_driver"):
        spotlight = Spotlight(
            show=True,
            target="route_list",
            text="Welcome! Tap a stop on your route to begin your first delivery.",
        )

    return OrchestratorResponse(
        deliver_button=DeliverButton(color="#16A34A"),  # green = authenticated
        spotlight=spotlight,
        driver=DriverInfo(**profile),
        route=route,
    )


def handle_stop_selected(payload: StopSelectedPayload) -> OrchestratorResponse:
    """
    Driver tapped a stop on the route list. Fetch stop details so reasoning
    can confirm status and advise on next steps.
    """
    stop = _get_stop_details(payload.stop_id)
    context: dict[str, Any] = {
        "driver_id": payload.driver_id,
        "stop_id": payload.stop_id,
        "stop_details": stop,
    }
    return _reason("stop_selected", context)


def handle_map_loaded(payload: MapLoadedPayload) -> OrchestratorResponse:
    """
    Map screen loaded. Pass distance so reasoning can enforce the 100 m rule.
    """
    stop = _get_stop_details(payload.stop_id)
    context: dict[str, Any] = {
        "driver_id": payload.driver_id,
        "stop_id": payload.stop_id,
        "stop_details": stop,
        "distance_m": payload.distance_m,
        "driver_lat": payload.lat,
        "driver_lng": payload.lng,
    }
    return _reason("map_loaded", context)


def handle_product_screen_loaded(
    payload: ProductScreenLoadedPayload,
) -> OrchestratorResponse:
    """
    Product checklist screen opened. Fetch the full item list and reconcile
    against anything already scanned so reasoning can build sections and set
    the deliver button colour.
    """
    products = _get_products(payload.stop_id)
    reconciliation = _reconcile_inventory(payload.stop_id, payload.scanned_items)
    context: dict[str, Any] = {
        "driver_id": payload.driver_id,
        "stop_id": payload.stop_id,
        "products": products,
        "reconciliation": reconciliation,
        "scanned_items": payload.scanned_items,
    }
    return _reason("product_screen_loaded", context)


def handle_item_scanned(payload: ItemScannedPayload) -> OrchestratorResponse:
    """
    Driver scanned an item. Reconcile the updated scanned_items list so
    reasoning can update the deliver button colour in real time.
    """
    reconciliation = _reconcile_inventory(payload.stop_id, payload.scanned_items)
    context: dict[str, Any] = {
        "driver_id": payload.driver_id,
        "stop_id": payload.stop_id,
        "item_id": payload.item_id,
        "scanned_items": payload.scanned_items,
        "reconciliation": reconciliation,
    }
    return _reason("item_scanned", context)


def handle_deliver_tapped(payload: DeliverTappedPayload) -> OrchestratorResponse:
    """
    Driver tapped the Deliver button. Reconcile inventory; if required items
    are missing reasoning will return a blocking popup.
    """
    reconciliation = _reconcile_inventory(payload.stop_id, payload.scanned_items)
    context: dict[str, Any] = {
        "driver_id": payload.driver_id,
        "stop_id": payload.stop_id,
        "scanned_items": payload.scanned_items,
        "reconciliation": reconciliation,
    }
    return _reason("deliver_tapped", context)


def handle_count_screen_loaded(
    payload: CountScreenLoadedPayload,
) -> OrchestratorResponse:
    """
    Count screen opened (cig_tob section). Fetch products filtered to the
    cig_tob section so reasoning can guide the driver through required scans.
    """
    all_products = _get_products(payload.stop_id)
    # Filter client-side to cig_tob — avoids a second DB round-trip
    cig_tob_items: list[dict] = []
    if "products" in all_products:
        cig_tob_items = [
            p for p in all_products["products"] if p["section_tag"] == "cig_tob"
        ]
    context: dict[str, Any] = {
        "driver_id": payload.driver_id,
        "stop_id": payload.stop_id,
        "cig_tob_items": cig_tob_items,
    }
    return _reason("count_screen_loaded", context)


def handle_user_idle(payload: UserIdlePayload) -> OrchestratorResponse:
    """
    Driver has been idle. Pass screen name and idle duration so reasoning
    can decide what spotlight guidance to show.
    """
    context: dict[str, Any] = {
        "driver_id": payload.driver_id,
        "screen": payload.screen,
        "idle_seconds": payload.idle_seconds,
    }
    return _reason("user_idle", context)


def handle_start_delivery(payload: StartDeliveryPayload) -> OrchestratorResponse:
    """
    Driver initiates delivery at a stop.

    Fetches all products for the stop and the driver profile, then lets
    reasoning apply any active dashboard overrides to required_tag values
    and set the initial deliver_button colour (always red at start).
    """
    products = _get_products(payload.stop_id)
    driver_profile = _get_driver_profile(payload.driver_id)
    context: dict[str, Any] = {
        "driver_id":      payload.driver_id,
        "route_id":       payload.route_id,
        "stop_id":        payload.stop_id,
        "driver_profile": driver_profile,
        "products":       products,
    }
    return _reason("start_delivery", context)


def handle_finish_delivery(payload: FinishDeliveryPayload) -> OrchestratorResponse:
    """
    Driver tapped Deliver at a stop.

    Runs a full reconciliation of scanned barcodes and counted items, then
    lets reasoning decide whether to block (required items missing), warn
    (only optional items missing), or approve (all required items complete).
    """
    reconciliation = _reconcile_inventory(
        payload.stop_id,
        payload.scanned_barcodes,
        payload.counted_items,
    )
    driver_profile = _get_driver_profile(payload.driver_id)
    context: dict[str, Any] = {
        "driver_id":        payload.driver_id,
        "route_id":         payload.route_id,
        "stop_id":          payload.stop_id,
        "driver_profile":   driver_profile,
        "reconciliation":   reconciliation,
        "scanned_barcodes": payload.scanned_barcodes,
        "counted_items":    payload.counted_items,
    }
    return _reason("finish_delivery", context)


def handle_route_map_opened(payload: RouteMapPayload) -> OrchestratorResponse:
    """
    Driver tapped the route name to open the full-route map view.

    Fetches aggregate route statistics and an ordered coordinate list, then
    passes everything — plus the driver's current position — to the AI.
    The AI returns stat_cards (e.g. total distance, ETA, fuel estimate) and
    an ai_message summarising route conditions.
    """
    summary = _get_route_summary(payload.route_id, payload.driver_id)
    context: dict[str, Any] = {
        "driver_id":        payload.driver_id,
        "route_id":         payload.route_id,
        "driver_lat":       payload.driver_lat,
        "driver_lng":       payload.driver_lng,
        "route_summary":    summary,
    }
    return _reason("route_map_opened", context)


# start_delivery_enabled is NOT calculated here.
# It is passed to OpenAI as a decision. The AI reads the distance and active
# dashboard overrides to determine whether delivery can start. This allows
# runtime rule changes without code deploys.
def handle_stop_map_opened(payload: StopMapPayload) -> OrchestratorResponse:
    """
    Driver tapped a specific stop card to open the single-stop map view.

    Fetches full stop details and calculates the raw Haversine distance from
    the driver's current location. The start_delivery_enabled flag is NOT
    calculated here — it is delegated to the AI, which reads distance_to_stop_km
    and any active dashboard overrides to make the geofence decision at runtime.
    """
    stop = _get_stop_details(payload.stop_id)

    distance_km: float = 0.0
    if "error" not in stop:
        distance_km = _haversine(
            payload.driver_lat, payload.driver_lng,
            stop["lat"],        stop["lng"],
        )

    context: dict[str, Any] = {
        "driver_id":              payload.driver_id,
        "route_id":               payload.route_id,
        "stop_id":                payload.stop_id,
        "driver_lat":             payload.driver_lat,
        "driver_lng":             payload.driver_lng,
        "stop_details":           stop,
        "distance_to_stop_km":    round(distance_km, 3),
        "distance_formatted":     _format_distance(distance_km),
        "active_overrides_count": len(active_overrides),
        "note": (
            "You must decide start_delivery_enabled based on distance_to_stop_km "
            "and any active dashboard overrides. Do not use a hardcoded threshold."
        ),
    }
    return _reason("stop_map_opened", context)


# ---------------------------------------------------------------------------
# Dispatch table — maps intent_type string → handler function
# ---------------------------------------------------------------------------

HANDLERS = {
    "driver_login":          handle_driver_login,
    "stop_selected":         handle_stop_selected,
    "map_loaded":            handle_map_loaded,
    "product_screen_loaded": handle_product_screen_loaded,
    "item_scanned":          handle_item_scanned,
    "deliver_tapped":        handle_deliver_tapped,
    "count_screen_loaded":   handle_count_screen_loaded,
    "user_idle":             handle_user_idle,
    "route_map_opened":      handle_route_map_opened,
    "stop_map_opened":       handle_stop_map_opened,
    "start_delivery":        handle_start_delivery,
    "finish_delivery":       handle_finish_delivery,
}
