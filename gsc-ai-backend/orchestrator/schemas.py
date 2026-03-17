"""
schemas.py

Pydantic models for every intent packet Flutter can send over WebSocket,
and for the structured JSON response the orchestrator always returns.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union  # noqa: F401 (Optional used below)
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Intent payload models (one per intent type)
# ---------------------------------------------------------------------------

class DriverLoginPayload(BaseModel):
    driver_id: Optional[int] = None
    name: Optional[str] = None      # Flutter can send driver name instead of ID
    username: Optional[str] = None  # alias accepted from the login form


class StopSelectedPayload(BaseModel):
    stop_id: int
    driver_id: int


class MapLoadedPayload(BaseModel):
    stop_id: int
    driver_id: int
    distance_m: float
    lat: float
    lng: float


class ProductScreenLoadedPayload(BaseModel):
    stop_id: int
    driver_id: int
    scanned_items: list[str] = Field(default_factory=list)


class ItemScannedPayload(BaseModel):
    stop_id: int
    item_id: int
    driver_id: int
    scanned_items: list[str] = Field(default_factory=list)


class DeliverTappedPayload(BaseModel):
    stop_id: int
    driver_id: int
    scanned_items: list[str] = Field(default_factory=list)


class CountScreenLoadedPayload(BaseModel):
    stop_id: int
    driver_id: int


class UserIdlePayload(BaseModel):
    screen: str
    driver_id: int
    idle_seconds: int


class RouteMapPayload(BaseModel):
    """Driver opened the full-route map (tapped route name on stops list)."""
    driver_id: int
    route_id: int
    driver_lat: float
    driver_lng: float


class StopMapPayload(BaseModel):
    """Driver opened the single-stop map (tapped a specific stop card)."""
    driver_id: int
    route_id: int
    stop_id: int
    driver_lat: float
    driver_lng: float


class StartDeliveryPayload(BaseModel):
    """Driver initiates a delivery for a specific stop."""
    driver_id: int
    route_id: int
    stop_id: int


class FinishDeliveryPayload(BaseModel):
    """Driver taps Deliver after completing all items at a stop."""
    driver_id: int
    route_id: int
    stop_id: int
    scanned_barcodes: list[str] = Field(default_factory=list)
    counted_items: list[dict] = Field(default_factory=list)
    # Each dict in counted_items must have: barcode (str), count_entered (int)


# ---------------------------------------------------------------------------
# Inbound WebSocket packet envelope
# ---------------------------------------------------------------------------

# Discriminated union so callers can validate the full packet in one step.
PayloadUnion = Union[
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
]

INTENT_PAYLOAD_MAP: dict[str, type[PayloadUnion]] = {
    "driver_login":          DriverLoginPayload,
    "stop_selected":         StopSelectedPayload,
    "map_loaded":            MapLoadedPayload,
    "product_screen_loaded": ProductScreenLoadedPayload,
    "item_scanned":          ItemScannedPayload,
    "deliver_tapped":        DeliverTappedPayload,
    "count_screen_loaded":   CountScreenLoadedPayload,
    "user_idle":             UserIdlePayload,
    "route_map_opened":      RouteMapPayload,
    "stop_map_opened":       StopMapPayload,
    "start_delivery":        StartDeliveryPayload,
    "finish_delivery":       FinishDeliveryPayload,
}


class IntentPacket(BaseModel):
    """
    Top-level envelope for every message Flutter sends over WebSocket.

    Flutter sends:
        { "intent_type": "driver_login", "payload": { "driver_id": 1 } }
    """
    intent_type: str
    payload: dict[str, Any]

    def parsed_payload(self) -> PayloadUnion:
        """
        Validate and return the payload as the correct typed Pydantic model
        for this intent_type. Raises ValueError for unknown intent types.
        """
        model_class = INTENT_PAYLOAD_MAP.get(self.intent_type)
        if model_class is None:
            raise ValueError(f"Unknown intent_type: '{self.intent_type}'")
        return model_class(**self.payload)


# ---------------------------------------------------------------------------
# Response schema — what the orchestrator always returns to Flutter
# ---------------------------------------------------------------------------

class DeliverButton(BaseModel):
    color: str = "#DC2626"  # red=#DC2626 | amber=#F59E0B | green=#16A34A


class ResponseItem(BaseModel):
    id: str
    name: str
    isRequired: bool = True
    interactionType: Literal["scan", "count", "photo"]
    scanCount: int = 1
    photoMandatory: bool = False


class Section(BaseModel):
    title: str
    icon: str
    items: list[ResponseItem] = Field(default_factory=list)


class PopupButton(BaseModel):
    label: str = ""
    action: str
    visible: bool = True

    model_config = {"populate_by_name": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        # OpenAI sometimes returns 'text' instead of 'label' — normalise it
        if isinstance(obj, dict) and "label" not in obj and "text" in obj:
            obj = {**obj, "label": obj["text"]}
        return super().model_validate(obj, **kwargs)


class Popup(BaseModel):
    show: bool = False
    blocking: bool = False
    title: str = ""
    message: str = ""
    buttons: list[PopupButton] = Field(default_factory=list)


class Spotlight(BaseModel):
    show: bool = False
    target: str = ""   # Flutter widget key to highlight
    text: str = ""     # tooltip text shown next to the highlighted element


class DriverInfo(BaseModel):
    """Driver profile embedded in the driver_login response."""
    id: int
    name: str
    experience_level: str
    is_new_driver: bool


class StopSchema(BaseModel):
    """A single stop as returned inside a route on driver login."""
    id: int
    stop_number: int
    sequence: int
    name: str
    address: str
    lat: float
    lng: float
    status: str


class RouteSchema(BaseModel):
    """Full route data — metadata plus ordered stop list — sent on driver login."""
    route_id: Optional[int]
    route_name: Optional[str]
    route_status: Optional[str] = None
    stops: list[StopSchema] = Field(default_factory=list)


class ProductItemSchema(BaseModel):
    """A single product/item on the delivery manifest."""
    id: int
    barcode: str
    name: str
    section_tag: str                        # cig_tob|totes|boxes|returns|ice_cream|fridge
    item_type: str                          # count|scan|scan_and_count
    quantity: int
    required_tag: str                       # required_photo|required_no_photo|not_required
    icon_tag: str                           # cig|tob|ice_cream|fridge|totes|paper_box
    is_complete: bool = False               # set by reconciliation
    photo_added: bool = False


class SectionSchema(BaseModel):
    """A named section grouping related product items."""
    section_tag: str
    items: list[ProductItemSchema] = Field(default_factory=list)


class OrchestratorResponse(BaseModel):
    deliver_button: DeliverButton = Field(default_factory=DeliverButton)
    sections: list[Section] = Field(default_factory=list)
    product_sections: list[SectionSchema] = Field(default_factory=list)  # new rich sections
    popup: Popup = Field(default_factory=Popup)
    spotlight: Spotlight = Field(default_factory=Spotlight)
    driver: Optional[DriverInfo] = None    # populated only for driver_login
    route: Optional[RouteSchema] = None    # populated only for driver_login
    stop_status_update: Optional[str] = None  # "delivered" when finish_delivery succeeds

    # Map screen fields — populated only for route_map_opened / stop_map_opened
    map_mode: Optional[str] = None                                   # "full_route" | "single_stop"
    stat_cards: list["RouteStatCard"] = Field(default_factory=list)  # AI-generated summary cards
    ai_message: Optional[str] = None                                 # short AI insight string
    stops_coordinates: list[dict] = Field(default_factory=list)      # route_map_opened only
    stop: Optional[dict] = None                                      # stop_map_opened only
    next_stop: Optional[dict] = None                                 # stop_map_opened only
    start_delivery_enabled: Optional[bool] = None                    # stop_map_opened only
    distance_to_stop_km: Optional[float] = None                      # stop_map_opened only


# ---------------------------------------------------------------------------
# Map screen response models
# ---------------------------------------------------------------------------

class RouteStatCard(BaseModel):
    """A single summary stat card displayed on the map screen."""
    icon: str           # emoji chosen by the AI (e.g. "📍", "⛽", "⏱")
    label: str          # short title (e.g. "Total Distance")
    value: str          # formatted value (e.g. "24.3 km")
    sublabel: str = ""  # optional extra context (e.g. "at 30 km/h avg")


class RouteMapResponse(BaseModel):
    """
    Full-route map response — Flutter contract reference.
    The AI populates these fields inside OrchestratorResponse for route_map_opened.

    map_mode:           "full_route"
    stops_coordinates:  ordered list of { sequence, stop_id, name, lat, lng, status }
    stat_cards:         4–6 AI-generated summary cards
    ai_message:         short friendly route insight
    deliver_button / popup / spotlight: standard fields
    """
    map_mode: str = "full_route"
    stops_coordinates: list[dict] = Field(default_factory=list)
    stat_cards: list[RouteStatCard] = Field(default_factory=list)
    ai_message: str = ""
    deliver_button: DeliverButton = Field(default_factory=DeliverButton)
    popup: Popup = Field(default_factory=Popup)
    spotlight: Spotlight = Field(default_factory=Spotlight)


class StopMapResponse(BaseModel):
    """
    Single-stop map response — Flutter contract reference.
    The AI populates these fields inside OrchestratorResponse for stop_map_opened.

    map_mode:               "single_stop"
    stop:                   full details of the stop the driver tapped
    next_stop:              same as stop (the tapped stop IS the next)
    stat_cards:             3–5 AI-generated summary cards
    ai_message:             short contextual note about this stop
    start_delivery_enabled: true if driver ≤ 200 m from stop AND no hard block
    distance_to_stop_km:    straight-line distance from driver to stop
    deliver_button / popup / spotlight: standard fields
    """
    map_mode: str = "single_stop"
    stop: Optional[dict] = None
    next_stop: Optional[dict] = None
    stat_cards: list[RouteStatCard] = Field(default_factory=list)
    ai_message: str = ""
    start_delivery_enabled: bool = False
    distance_to_stop_km: float = 0.0
    deliver_button: DeliverButton = Field(default_factory=DeliverButton)
    popup: Popup = Field(default_factory=Popup)
    spotlight: Spotlight = Field(default_factory=Spotlight)


# Allow OrchestratorResponse to resolve the forward reference to RouteStatCard
OrchestratorResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Dashboard Command Centre — unified command endpoint
# ---------------------------------------------------------------------------

class DashboardCommand(BaseModel):
    """
    Body for POST /command — the single endpoint the Command Centre uses.
    The AI classifies the plain-English text as either a rule override or
    a popup push and acts accordingly.
    """
    command: str


# ---------------------------------------------------------------------------
# Server-push pop-up (server → Flutter via WebSocket)
# ---------------------------------------------------------------------------

class ServerPushMessage(BaseModel):
    """
    The JSON frame the server sends to Flutter over the /ws WebSocket
    when a dashboard operator pushes a notification.

    Flutter must check for  { "type": "server_push" }  on every incoming
    message and, when present, display popup immediately regardless of the
    current screen.

    Flutter contract:
      { "type": "server_push",
        "popup": {
          "show": true, "blocking": true|false,
          "title": "...", "message": "...",
          "buttons": [{"label": "...", "action": "...", "visible": true}]
        }
      }

    blocking true  = driver must tap a button; back button disabled
    blocking false = driver can tap outside to dismiss
    """
    type: Literal["server_push"] = "server_push"
    popup: Popup
