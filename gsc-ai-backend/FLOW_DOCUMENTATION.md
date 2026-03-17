# GSC AI Backend — Data Flow Documentation

> Generated from source code. Every function name, field name, and
> data structure in this document matches the actual code exactly.

---

## Section 1 — System Overview

The GSC AI Backend is an intelligent delivery assistant that sits between a mobile app used by delivery drivers and a SQLite database containing route, stop, and inventory information. When a driver opens their app and performs an action — such as logging in, opening a route map, scanning a product, or tapping the Deliver button — the app sends a structured message to this backend over a persistent WebSocket connection. The backend's AI Orchestrator receives that message, calls the appropriate database tools through an MCP (Model Context Protocol) server to fetch relevant data, assembles that data into a context package, and sends it to OpenAI's GPT-4o model along with a detailed system prompt encoding all delivery rules. OpenAI reasons over the data and returns a structured JSON response that tells the app exactly what to display: whether the Deliver button should be green, amber, or red; whether a popup warning should block the driver's progress; whether a spotlight should highlight a specific UI element; and what items appear in which sections of the product checklist. A separate web dashboard used by operations managers can send plain-English commands that are also classified by AI — some commands modify the live delivery rules injected into every future AI call (overrides), while others immediately push popup notifications to connected drivers' phones. The three main components are: the **MCP Server** (reads and writes the SQLite database through typed tool functions), the **AI Orchestrator** (a FastAPI application that receives Flutter events, calls MCP tools, calls OpenAI, and returns UI-driving JSON), and the **Web Dashboard API** (REST endpoints on the same FastAPI app that let operations managers manage override rules and push live notifications).

---

## Section 2 — Component Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Flutter Driver App                           │
│  Sends: IntentPacket JSON  ──────────────────────────────────────►  │
│  Receives: OrchestratorResponse JSON + "intent_type" field          │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  WebSocket /ws
          ┌───────────────▼──────────────────────────────────────────┐
          │              AI Orchestrator  (FastAPI  main.py)         │
          │                                                           │
          │  websocket_endpoint()  ──► HANDLERS[intent_type]()       │
          │  intent_handler.py  ──► reason()  ──► OpenAI GPT-4o      │
          │                                                           │
          │  POST /command  ──► classify_and_execute()  ──► OpenAI   │
          │  POST /override  ──► add_override()                       │
          │  GET  /overrides ──► active_overrides list                │
          │  DELETE /overrides ──► clear_overrides()                  │
          │  GET  /drivers/online ──► driver_registry                 │
          │                                                           │
          │  Driver pushes: driver_registry.broadcast() / send_to()  │
          │  Data pushed: ServerPushMessage JSON                      │
          │  ◄── {"type":"server_push", "popup":{...}}  ──────────── │
          └───────┬──────────────────────────────────────────────────┘
                  │  Direct Python function calls
                  │  (via _ToolRegistry shim — not over network)
          ┌───────▼───────────────────────────────────────────────────┐
          │                MCP Server tools                            │
          │  driver.py   :  get_driver_profile(), get_driver_by_name()│
          │  stops.py    :  get_route_for_driver(), get_stop_details() │
          │                 get_route_summary(), get_next_stop()       │
          │  products.py :  get_products(), reconcile_inventory()     │
          └───────┬───────────────────────────────────────────────────┘
                  │  sqlite3 SQL queries via get_db() context manager
          ┌───────▼───────────────────────────────────────────────────┐
          │              SQLite Database  (gsc_poc.db)                │
          │  Tables: drivers, stops, products, routes, route_stops    │
          └───────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                      Web Dashboard (Vite/React)                     │
│  POST /command  →  {"command": "plain English string"}             │
│  POST /override  →  {"rule": "rule string"}                        │
│  WebSocket /ws/log  ←  every inbound intent & outbound response    │
└──────────────┬─────────────────────────────────────────────────────┘
               │  HTTP REST  +  WebSocket /ws/log
   ┌───────────▼──────────────────────────────────────────────────┐
   │             AI Orchestrator  (same FastAPI app)               │
   └──────────────────────────────────────────────────────────────┘
```

**Arrow labels:**

| Arrow | What travels |
|---|---|
| Flutter → `/ws` | `IntentPacket` JSON: `{"intent_type": "...", "payload": {...}}` |
| `/ws` → Flutter | `OrchestratorResponse` JSON + `"intent_type"` field |
| Orchestrator → MCP tools | Direct Python function call with typed arguments |
| MCP tools → Orchestrator | Tool response `dict` (e.g. driver profile, stop list) |
| MCP tools → SQLite | SQL query string + bound parameters via `sqlite3` |
| SQLite → MCP tools | `sqlite3.Row` result set |
| Orchestrator → OpenAI | `{"role":"system", content: full prompt}` + `{"role":"user", content: intent+context JSON}` |
| OpenAI → Orchestrator | Raw JSON string parsed into `OrchestratorResponse` |
| Orchestrator → Flutter (push) | `ServerPushMessage` JSON: `{"type":"server_push","popup":{...}}` |
| Dashboard → `/command` | `DashboardCommand` JSON: `{"command": "..."}` |
| Dashboard → `/ws/log` | WebSocket subscription; receives broadcast of every in/out message |
| `/ws/log` → Dashboard | `{"direction":"in"/"out","intent":"...","payload":{...}}` |

---

## Section 3 — Database Tables

### `drivers`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | Unique driver ID |
| `name` | TEXT NOT NULL | Driver's full name (e.g. "Marcus Webb") |
| `experience_level` | TEXT NOT NULL | One of: `'junior'`, `'mid'`, `'senior'` |
| `is_new_driver` | INTEGER NOT NULL DEFAULT 0 | SQLite boolean: `0` = false, `1` = true. Triggers new-driver spotlight guidance |

**Foreign keys:** None  
**Plain English:** Stores the profiles of delivery drivers. The `is_new_driver` flag and `experience_level` are used by the AI to tailor how much guidance it shows.

---

### `stops`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | Unique stop ID |
| `stop_number` | INTEGER NOT NULL | Human-readable stop number shown in the app |
| `name` | TEXT NOT NULL | Store/location name (e.g. "Pink City Kirana Store") |
| `address` | TEXT NOT NULL | Full street address |
| `lat` | REAL NOT NULL | GPS latitude in decimal degrees |
| `lng` | REAL NOT NULL | GPS longitude in decimal degrees |
| `status` | TEXT NOT NULL DEFAULT `'pending'` | One of: `'pending'`, `'in_progress'`, `'completed'`. Enforced by CHECK constraint |

**Foreign keys:** None  
**Plain English:** Represents a physical delivery location. Coordinates are used to calculate whether a driver is close enough to start delivery. Status tracks delivery progress.

---

### `products`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | Unique product ID |
| `stop_id` | INTEGER NOT NULL | References `stops(id)` — which stop this item belongs to |
| `name` | TEXT NOT NULL | Product name (e.g. "Marlboro Red 20s") |
| `section_tag` | TEXT NOT NULL | UI grouping: one of `'overview'`, `'cig_tob'`, `'totes'`, `'boxes'`, `'returns'`, `'collection'` |
| `item_type` | TEXT NOT NULL | How driver interacts: `'scan'` (barcode), `'count'` (manual count), `'photo'` (camera) |
| `quantity` | INTEGER NOT NULL DEFAULT 1 | Expected quantity |

**Foreign keys:** `stop_id` → `stops(id)`  
**Plain English:** The delivery manifest for each stop. Every item a driver must scan, count, or photograph before delivery can be completed. The `section_tag` organises items into tabs in the mobile UI.

---

### `routes`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | Unique route ID |
| `route_name` | TEXT NOT NULL | Human-readable name (e.g. "Jaipur North Route") |
| `driver_id` | INTEGER NOT NULL | References `drivers(id)` — which driver is assigned this route |
| `route_status` | TEXT NOT NULL DEFAULT `'pending'` | One of: `'pending'`, `'in_progress'`, `'completed'` |

**Foreign keys:** `driver_id` → `drivers(id)`  
**Plain English:** A named collection of stops assigned to a specific driver for a shift. Each driver has exactly one route.

---

### `route_stops`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | Unique row ID |
| `route_id` | INTEGER NOT NULL | References `routes(id)` |
| `stop_id` | INTEGER NOT NULL | References `stops(id)` |
| `sequence` | INTEGER NOT NULL | The delivery order position (1 = first stop to visit) |

**Foreign keys:** `route_id` → `routes(id)`, `stop_id` → `stops(id)`  
**Unique constraint:** `(route_id, stop_id)` — a stop cannot appear twice in the same route  
**Plain English:** The join table that links routes to stops with an ordered sequence. This is what determines the order in which stores are visited.

---

## Section 4 — MCP Server Tools

> **Note:** In this codebase the MCP tools are called via a direct Python function adapter (`_ToolRegistry` shim in `intent_handler.py`) rather than over the MCP stdio protocol at runtime. The `server.py` file registers them with `FastMCP` for MCP protocol exposure; `intent_handler.py` re-registers the same functions locally for direct invocation.

---

### `get_driver_profile`

| | |
|---|---|
| **File** | `mcp_server/tools/driver.py` |
| **Input** | `driver_id: int` — primary key of the driver |
| **DB Query** | Selects `id`, `name`, `experience_level`, `is_new_driver` from `drivers` WHERE `id = driver_id` |
| **Returns** | `{"id": int, "name": str, "experience_level": str, "is_new_driver": bool}` or `{"error": str}` |
| **Called by** | `handle_driver_login()` in `intent_handler.py` when `payload.driver_id` is provided |

---

### `get_driver_by_name`

| | |
|---|---|
| **File** | `mcp_server/tools/driver.py` |
| **Input** | `name: str` — partial or full driver name (case-insensitive) |
| **DB Query** | Selects same columns from `drivers` WHERE `LOWER(name) LIKE LOWER('%name%')`, returns first match |
| **Returns** | Same dict shape as `get_driver_profile`, or `{"error": str}` |
| **Called by** | `handle_driver_login()` when `payload.name` or `payload.username` is provided instead of `driver_id` |

---

### `get_route_for_driver`

| | |
|---|---|
| **File** | `mcp_server/tools/stops.py` |
| **Input** | `driver_id: int` |
| **DB Query** | First checks `drivers` table for existence. Then fetches the route from `routes` WHERE `driver_id = ?`. Then joins `route_stops` with `stops` WHERE `route_id = ?`, ordered by `sequence ASC` |
| **Returns** | `{"route_id": int, "route_name": str, "route_status": str, "stops": [ {"id", "stop_number", "sequence", "name", "address", "lat", "lng", "status"}, ... ]}` or `{"route_id": null, ...}` if no route assigned, or `{"error": str}` |
| **Called by** | `handle_driver_login()` in `intent_handler.py` |

---

### `get_stop_details`

| | |
|---|---|
| **File** | `mcp_server/tools/stops.py` |
| **Input** | `stop_id: int` |
| **DB Query** | Selects `id`, `name`, `address`, `lat`, `lng`, `status` from `stops` WHERE `id = stop_id` |
| **Returns** | `{"id": int, "name": str, "address": str, "lat": float, "lng": float, "status": str}` or `{"error": str}` |
| **Called by** | `handle_stop_selected()`, `handle_map_loaded()`, `handle_stop_map_opened()` |

---

### `get_route_summary`

| | |
|---|---|
| **File** | `mcp_server/tools/stops.py` |
| **Input** | `route_id: int`, `driver_id: int` |
| **DB Query** | Verifies route belongs to driver. Then aggregates `COUNT`, `SUM(completed)`, `SUM(remaining)` from `route_stops JOIN stops`. Then fetches ordered coordinate list (`sequence`, `stop_id`, `name`, `lat`, `lng`, `status`) sorted by `sequence ASC` |
| **Returns** | `{"route_id": int, "route_name": str, "total_stops": int, "completed_stops": int, "remaining_stops": int, "stops_coordinates": [{"sequence", "stop_id", "name", "lat", "lng", "status"}, ...]}` or `{"error": str}` |
| **Called by** | `handle_route_map_opened()` in `intent_handler.py` |

---

### `get_next_stop`

| | |
|---|---|
| **File** | `mcp_server/tools/stops.py` |
| **Input** | `route_id: int` |
| **DB Query** | Counts total stops in route. Then joins `route_stops` with `stops` WHERE `route_id = ?` AND `status != 'completed'`, ordered by `sequence ASC`, limit 1 — the first pending stop |
| **Returns** | `{"stop_id": int, "stop_number": int, "sequence": int, "name": str, "address": str, "lat": float, "lng": float, "status": str, "is_last_stop": bool}` or `{"stop_id": null, "name": null, "is_last_stop": false, "message": "All stops completed"}` or `{"error": str}` |
| **Called by** | Not called by any intent handler in the current codebase (registered as MCP tool, available for future use) |

---

### `get_products`

| | |
|---|---|
| **File** | `mcp_server/tools/products.py` |
| **Input** | `stop_id: int` |
| **DB Query** | Verifies stop exists. Selects `id`, `name`, `section_tag`, `item_type`, `quantity` from `products` WHERE `stop_id = ?`, ordered by `section_tag, id` |
| **Returns** | `{"stop_id": int, "count": int, "products": [{"id", "name", "section_tag", "item_type", "quantity"}, ...]}` or `{"error": str}` |
| **Called by** | `handle_product_screen_loaded()`, `handle_count_screen_loaded()` |

---

### `reconcile_inventory`

| | |
|---|---|
| **File** | `mcp_server/tools/products.py` |
| **Input** | `stop_id: int`, `scanned_items: list[str]` (list of scanned product name strings) |
| **DB Query** | Verifies stop exists. Fetches all products for the stop. Classifies them in Python (no second SQL call): items in DB manifest that were scanned → `complete`; items in DB not scanned → `missing`; scanned names not in DB → `unrecognised` (case-insensitive matching) |
| **Returns** | `{"stop_id": int, "summary": {"total_expected": int, "total_scanned": int, "complete_count": int, "missing_count": int, "unrecognised_count": int}, "complete": [...], "missing": [...], "unrecognised": [{"scanned_name": str}]}` or `{"error": str}` |
| **Called by** | `handle_product_screen_loaded()`, `handle_item_scanned()`, `handle_deliver_tapped()` |

---

## Section 5 — Intent Flow

---

### INTENT: `driver_login`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
Endpoint: `/ws` in `main.py`  
Data sent:
```json
{
  "intent_type": "driver_login",
  "payload": {
    "driver_id": 1
  }
}
```
> Flutter may also send `"name"` or `"username"` instead of `"driver_id"`. All three fields are optional in `DriverLoginPayload`; at least one must be present to resolve a driver.

---

**Step 2 — `websocket_endpoint()` receives and routes the intent**  
Function: `websocket_endpoint()` in `main.py`  
What it does: Parses the raw text as JSON into an `IntentPacket`. Validates the payload using `packet.parsed_payload()` which instantiates a `DriverLoginPayload` Pydantic model. Looks up `HANDLERS["driver_login"]` in the dispatch table.

---

**Step 3 — Intent handler is called**  
Function: `handle_driver_login(payload: DriverLoginPayload)` in `intent_handler.py`  
What it does:
1. Checks which identifier was provided: `driver_id` → calls `get_driver_profile()`, `name` → calls `get_driver_by_name()`, `username` → calls `get_driver_by_name()`.
2. If the profile has an `"error"` key, returns a red blocking popup immediately without calling OpenAI.
3. Calls `get_route_for_driver(driver_id)` to fetch the full stop list.
4. Converts the raw dict into a `RouteSchema` object via `_build_route()`.
5. Checks `active_overrides`: if the list is empty, takes the **fast path** (no OpenAI call). If overrides are present, takes the **override path** (calls OpenAI).

---

**Step 4 — MCP tool called: `get_driver_profile`**  
Function: `get_driver_profile(driver_id)` in `mcp_server/tools/driver.py`  
Data returned:
```json
{
  "id": 1,
  "name": "Marcus Webb",
  "experience_level": "senior",
  "is_new_driver": false
}
```

---

**Step 5 — MCP tool called: `get_route_for_driver`**  
Function: `get_route_for_driver(driver_id)` in `mcp_server/tools/stops.py`  
Data returned:
```json
{
  "route_id": 1,
  "route_name": "Jaipur North Route",
  "route_status": "pending",
  "stops": [
    { "id": 16, "stop_number": 16, "sequence": 1, "name": "Shastri Nagar Daily Mart",
      "address": "Shastri Nagar, Jaipur 302016", "lat": 26.9312, "lng": 75.7824, "status": "pending" },
    { "id": 17, "stop_number": 17, "sequence": 2, "name": "Jhotwara Road Store",
      "address": "Jhotwara, Jaipur 302012", "lat": 26.9567, "lng": 75.7934, "status": "pending" }
  ]
}
```

---

**Step 6 — Fast path (no active overrides): Response built directly**  
No OpenAI call is made.  
If `profile["is_new_driver"]` is `true`, a `Spotlight` is added pointing to `"route_list"`.  
`OrchestratorResponse` is built with `deliver_button.color = "#16A34A"` (green), the `DriverInfo` object, and the `RouteSchema`.

---

**Step 6-alt — Override path (overrides present): `reason()` is called**  
Function: `reason(intent, context_data, full_prompt)` in `reasoning.py`  
Input context passed to OpenAI:
```json
{
  "intent": "driver_login",
  "context": {
    "driver_id": 1,
    "driver_profile": { "id": 1, "name": "Marcus Webb", "experience_level": "senior", "is_new_driver": false },
    "route": { "route_id": 1, "route_name": "Jaipur North Route", ... }
  }
}
```
OpenAI receives the full system prompt (`get_full_prompt()`) plus the above user message.  
OpenAI returns a JSON object matching `OrchestratorResponse` schema.

---

**Step 7 — Response is sent back to Flutter**  
Function: `websocket_endpoint()` in `main.py`  
The `OrchestratorResponse` is serialised with `model_dump(exclude_none=True)` and `"intent_type": "driver_login"` is merged in.
```json
{
  "intent_type": "driver_login",
  "deliver_button": { "color": "#16A34A" },
  "sections": [],
  "popup": { "show": false, "blocking": false, "title": "", "message": "", "buttons": [] },
  "spotlight": { "show": false, "target": "", "text": "" },
  "driver": { "id": 1, "name": "Marcus Webb", "experience_level": "senior", "is_new_driver": false },
  "route": {
    "route_id": 1,
    "route_name": "Jaipur North Route",
    "route_status": "pending",
    "stops": [ { "id": 16, "stop_number": 16, "sequence": 1, ... }, ... ]
  }
}
```

---

**Step 8 — Driver registry is updated**  
Function: `driver_registry.register(response.driver.id, ws)` in `main.py`  
Triggered only when `packet.intent_type == "driver_login"` and `response.driver is not None`.  
What it stores: `_connections[driver_id] = ws` — maps the integer driver ID to the live WebSocket object so server-push messages can reach this driver later.

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `route_map_opened`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
Endpoint: `/ws`  
Data sent:
```json
{
  "intent_type": "route_map_opened",
  "payload": {
    "driver_id": 1,
    "route_id": 1,
    "driver_lat": 26.9312,
    "driver_lng": 75.7824
  }
}
```
> Also accepted in Flutter flat format: `{"event": "route_map_opened", "driver_id": "1", "route_id": "1", "driver_lat": 26.9312, "driver_lng": 75.7824}`

---

**Step 2 — `websocket_endpoint()` receives and routes**  
Parses into `IntentPacket`. If the flat `"event"` format is detected, it is normalised: all keys except `"event"`, `"session_id"`, `"timestamp"` are moved into `"payload"`. Validates as `RouteMapPayload`. Routes to `HANDLERS["route_map_opened"]`.

---

**Step 3 — Intent handler is called**  
Function: `handle_route_map_opened(payload: RouteMapPayload)` in `intent_handler.py`  
What it does: Calls `get_route_summary(route_id, driver_id)` to fetch aggregate stats and ordered coordinates. Builds a context dict and calls `_reason("route_map_opened", context)`.

---

**Step 4 — MCP tool called: `get_route_summary`**  
Function: `get_route_summary(route_id, driver_id)` in `mcp_server/tools/stops.py`  
Data returned:
```json
{
  "route_id": 1,
  "route_name": "Jaipur North Route",
  "total_stops": 7,
  "completed_stops": 0,
  "remaining_stops": 7,
  "stops_coordinates": [
    { "sequence": 1, "stop_id": 16, "name": "Shastri Nagar Daily Mart", "lat": 26.9312, "lng": 75.7824, "status": "pending" },
    { "sequence": 2, "stop_id": 17, "name": "Jhotwara Road Store", "lat": 26.9567, "lng": 75.7934, "status": "pending" }
  ]
}
```

---

**Step 5 — `reason()` is called**  
Function: `reason(intent, context_data, full_prompt)` in `reasoning.py`  
Input context passed to OpenAI:
```json
{
  "intent": "route_map_opened",
  "context": {
    "driver_id": 1,
    "route_id": 1,
    "driver_lat": 26.9312,
    "driver_lng": 75.7824,
    "route_summary": { "route_id": 1, "total_stops": 7, "remaining_stops": 7, "stops_coordinates": [...] }
  }
}
```
OpenAI calculates total distance (Haversine between consecutive stops), estimated time (at 30 km/h), fuel estimate (at 5 km/L), and returns stat_cards plus an `ai_message`.

---

**Step 6 — Response sent to Flutter**  
```json
{
  "intent_type": "route_map_opened",
  "deliver_button": { "color": "#16A34A" },
  "popup": { "show": false, ... },
  "spotlight": { "show": false, ... },
  "map_mode": "full_route",
  "stops_coordinates": [ { "sequence": 1, "stop_id": 16, "name": "...", "lat": 26.9312, "lng": 75.7824, "status": "pending" }, ... ],
  "stat_cards": [
    { "icon": "📍", "label": "Total Distance", "value": "12.4 km", "sublabel": "" },
    { "icon": "⏱", "label": "Estimated Time", "value": "24 min", "sublabel": "at 30 km/h avg" },
    { "icon": "⛽", "label": "Fuel Estimate", "value": "1.0 L", "sublabel": "" },
    { "icon": "🏪", "label": "Stops Remaining", "value": "7", "sublabel": "" }
  ],
  "ai_message": "Your route looks clear. Start with Shastri Nagar Daily Mart and work north."
}
```

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `stop_map_opened`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
```json
{
  "intent_type": "stop_map_opened",
  "payload": {
    "driver_id": 2,
    "route_id": 2,
    "stop_id": 1,
    "driver_lat": 26.924,
    "driver_lng": 75.827
  }
}
```

---

**Step 2 — `websocket_endpoint()` receives and routes**  
Validates as `StopMapPayload`. Routes to `HANDLERS["stop_map_opened"]`.

---

**Step 3 — Intent handler is called**  
Function: `handle_stop_map_opened(payload: StopMapPayload)` in `intent_handler.py`  
What it does:
1. Calls `get_stop_details(stop_id)`.
2. Calculates `distance_km` using `_haversine(driver_lat, driver_lng, stop["lat"], stop["lng"])`.
3. Sets `start_delivery_enabled = distance_km <= 0.2` (the 200 m threshold).
4. Builds context dict and calls `_reason("stop_map_opened", context)`.

---

**Step 4 — MCP tool called: `get_stop_details`**  
Function: `get_stop_details(stop_id)` in `mcp_server/tools/stops.py`  
Data returned:
```json
{
  "id": 1,
  "name": "Pink City Kirana Store",
  "address": "Johari Bazaar, Jaipur 302003",
  "lat": 26.9239,
  "lng": 75.8267,
  "status": "pending"
}
```

---

**Step 5 — `reason()` is called**  
Context passed:
```json
{
  "intent": "stop_map_opened",
  "context": {
    "driver_id": 2,
    "route_id": 2,
    "stop_id": 1,
    "driver_lat": 26.924,
    "driver_lng": 75.827,
    "stop_details": { "id": 1, "name": "Pink City Kirana Store", ... },
    "distance_to_stop_km": 0.012,
    "start_delivery_enabled": true
  }
}
```
OpenAI receives Rule 8 from the system prompt and generates `stat_cards` (Distance to Stop, Estimated Arrival, Stop Number, optional note cards), `ai_message`, and confirms `start_delivery_enabled`.

---

**Step 6 — Response sent to Flutter**  
```json
{
  "intent_type": "stop_map_opened",
  "deliver_button": { "color": "#16A34A" },
  "map_mode": "single_stop",
  "stop": { "id": 1, "name": "Pink City Kirana Store", "address": "Johari Bazaar, Jaipur 302003", "lat": 26.9239, "lng": 75.8267, "status": "pending" },
  "next_stop": { "id": 1, "name": "Pink City Kirana Store", ... },
  "start_delivery_enabled": true,
  "distance_to_stop_km": 0.012,
  "stat_cards": [
    { "icon": "📏", "label": "Distance to Stop", "value": "12 m", "sublabel": "" },
    { "icon": "🚶", "label": "Estimated Arrival", "value": "< 1 min", "sublabel": "" },
    { "icon": "🏪", "label": "Stop Number", "value": "Stop 1 of 7", "sublabel": "" },
    { "icon": "🚬", "label": "Double Scan", "value": "Required", "sublabel": "cig_tob items" }
  ],
  "ai_message": "You're right at Pink City Kirana Store — tap Start Delivery when ready.",
  "popup": { "show": false, ... },
  "spotlight": { "show": false, ... }
}
```

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `product_screen_loaded`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
```json
{
  "intent_type": "product_screen_loaded",
  "payload": {
    "stop_id": 1,
    "driver_id": 2,
    "scanned_items": []
  }
}
```

---

**Step 2 — `websocket_endpoint()` routes**  
Validates as `ProductScreenLoadedPayload`. Routes to `HANDLERS["product_screen_loaded"]`.

---

**Step 3 — Intent handler is called**  
Function: `handle_product_screen_loaded(payload: ProductScreenLoadedPayload)` in `intent_handler.py`  
Calls `get_products(stop_id)` and `reconcile_inventory(stop_id, scanned_items)`, then calls `_reason()`.

---

**Step 4 — MCP tool called: `get_products`**  
Returns all items for the stop (see tool definition above).

---

**Step 5 — MCP tool called: `reconcile_inventory`**  
Returns classification of scanned vs expected items (all missing on first load).

---

**Step 6 — `reason()` is called**  
Context passed:
```json
{
  "intent": "product_screen_loaded",
  "context": {
    "driver_id": 2,
    "stop_id": 1,
    "products": { "stop_id": 1, "count": 8, "products": [...] },
    "reconciliation": { "stop_id": 1, "summary": { "total_expected": 8, "total_scanned": 0, ... }, "complete": [], "missing": [...], "unrecognised": [] },
    "scanned_items": []
  }
}
```
OpenAI returns populated `sections` array (one per `section_tag`), a `deliver_button` (red because items are missing), and possibly a `spotlight` for new drivers.

---

**Step 7 — Response sent to Flutter**  
```json
{
  "intent_type": "product_screen_loaded",
  "deliver_button": { "color": "#DC2626" },
  "sections": [
    {
      "title": "Overview",
      "icon": "📋",
      "items": [
        { "id": "1", "name": "Delivery Summary Sheet", "isRequired": true, "interactionType": "photo", "scanCount": 1, "photoMandatory": true }
      ]
    },
    {
      "title": "Cigarettes & Tobacco",
      "icon": "🚬",
      "items": [
        { "id": "2", "name": "Marlboro Red 20s", "isRequired": true, "interactionType": "scan", "scanCount": 1, "photoMandatory": false }
      ]
    }
  ],
  "popup": { "show": false, ... },
  "spotlight": { "show": true, "target": "first_item", "text": "Scan or photograph each item to begin your delivery checklist." }
}
```

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `item_scanned`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
```json
{
  "intent_type": "item_scanned",
  "payload": {
    "stop_id": 1,
    "item_id": 2,
    "driver_id": 2,
    "scanned_items": ["Marlboro Red 20s"]
  }
}
```

---

**Step 2 — Routes to handler**  
Validates as `ItemScannedPayload`.

---

**Step 3 — Intent handler called**  
Function: `handle_item_scanned(payload: ItemScannedPayload)` in `intent_handler.py`  
Calls `reconcile_inventory(stop_id, scanned_items)` with the updated list, then calls `_reason()`. Does **not** call `get_products` again (reconciliation is sufficient for a scan update).

---

**Step 4 — MCP tool called: `reconcile_inventory`**  
Returns updated classification showing "Marlboro Red 20s" in `complete`, remaining items in `missing`.

---

**Step 5 — `reason()` is called**  
Context passed:
```json
{
  "intent": "item_scanned",
  "context": {
    "driver_id": 2,
    "stop_id": 1,
    "item_id": 2,
    "scanned_items": ["Marlboro Red 20s"],
    "reconciliation": { "summary": { "complete_count": 1, "missing_count": 7, ... }, "complete": [...], "missing": [...], "unrecognised": [] }
  }
}
```
OpenAI updates `deliver_button` colour (amber if partially complete, red if still missing required items). No `sections` populated (this intent only returns button/popup state).

---

**Step 6 — Response sent to Flutter**  
```json
{
  "intent_type": "item_scanned",
  "deliver_button": { "color": "#F59E0B" },
  "sections": [],
  "popup": { "show": false, ... },
  "spotlight": { "show": false, ... }
}
```

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `deliver_tapped`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
```json
{
  "intent_type": "deliver_tapped",
  "payload": {
    "stop_id": 1,
    "driver_id": 2,
    "scanned_items": ["Marlboro Red 20s", "Lambert & Butler King Size", "Amber Leaf 50g Pouch"]
  }
}
```

---

**Step 2 — Routes to handler**  
Validates as `DeliverTappedPayload`.

---

**Step 3 — Intent handler called**  
Function: `handle_deliver_tapped(payload: DeliverTappedPayload)` in `intent_handler.py`  
Calls `reconcile_inventory(stop_id, scanned_items)`, builds context, calls `_reason()`.

---

**Step 4 — MCP tool called: `reconcile_inventory`**  
Returns final reconciliation. If all required items are present: `missing_count = 0`. If anything is missing, `missing` list will have items.

---

**Step 5 — `reason()` is called**  
Context:
```json
{
  "intent": "deliver_tapped",
  "context": {
    "driver_id": 2,
    "stop_id": 1,
    "scanned_items": ["Marlboro Red 20s", "Lambert & Butler King Size", "Amber Leaf 50g Pouch"],
    "reconciliation": { "summary": { "complete_count": 3, "missing_count": 5, ... }, "missing": ["Soft Drinks Tote A", "Crisps Assorted Box x12", ...] }
  }
}
```
If items are missing, OpenAI returns a **blocking popup** listing the missing items. If all items are done, returns green deliver_button. Rule 2 (cig_tob must be scanned) and Rule 3 (required items block delivery) are enforced here.

---

**Step 6 — Response sent to Flutter**  
Example when items are still missing:
```json
{
  "intent_type": "deliver_tapped",
  "deliver_button": { "color": "#DC2626" },
  "sections": [],
  "popup": {
    "show": true,
    "blocking": true,
    "title": "Missing Items",
    "message": "You must complete: Soft Drinks Tote A, Crisps Assorted Box x12, Empty Crate Return, Cash Collection, Delivery Summary Sheet.",
    "buttons": [{ "label": "Go to Checklist", "action": "open_product_screen", "visible": true }]
  },
  "spotlight": { "show": false, ... }
}
```

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `count_screen_loaded`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
```json
{
  "intent_type": "count_screen_loaded",
  "payload": {
    "stop_id": 1,
    "driver_id": 2
  }
}
```

---

**Step 2 — Routes to handler**  
Validates as `CountScreenLoadedPayload`.

---

**Step 3 — Intent handler called**  
Function: `handle_count_screen_loaded(payload: CountScreenLoadedPayload)` in `intent_handler.py`  
Calls `get_products(stop_id)`, then **filters in Python** to only items where `section_tag == "cig_tob"`. Does not make a second DB call. Builds context with `cig_tob_items` list, calls `_reason()`.

---

**Step 4 — MCP tool called: `get_products`**  
Returns all products for the stop. Handler filters to cig_tob items client-side.

---

**Step 5 — `reason()` is called**  
Context:
```json
{
  "intent": "count_screen_loaded",
  "context": {
    "driver_id": 2,
    "stop_id": 1,
    "cig_tob_items": [
      { "id": 2, "name": "Marlboro Red 20s", "section_tag": "cig_tob", "item_type": "scan", "quantity": 5 },
      { "id": 3, "name": "Lambert & Butler King Size", "section_tag": "cig_tob", "item_type": "scan", "quantity": 10 },
      { "id": 4, "name": "Amber Leaf 50g Pouch", "section_tag": "cig_tob", "item_type": "scan", "quantity": 8 }
    ]
  }
}
```
OpenAI guides the driver through the double-scan requirement (Rule 2) and returns a spotlight or popup with instructions.

---

**Step 6 — Response sent to Flutter**  
```json
{
  "intent_type": "count_screen_loaded",
  "deliver_button": { "color": "#DC2626" },
  "sections": [],
  "popup": { "show": false, ... },
  "spotlight": {
    "show": true,
    "target": "cig_tob_first_item",
    "text": "Scan each cigarette and tobacco product to confirm your delivery count."
  }
}
```

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `user_idle`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
```json
{
  "intent_type": "user_idle",
  "payload": {
    "screen": "product_screen",
    "driver_id": 2,
    "idle_seconds": 45
  }
}
```

---

**Step 2 — Routes to handler**  
Validates as `UserIdlePayload`.

---

**Step 3 — Intent handler called**  
Function: `handle_user_idle(payload: UserIdlePayload)` in `intent_handler.py`  
No MCP tool calls are made. Builds minimal context dict with `screen`, `driver_id`, `idle_seconds` and calls `_reason()`.

---

**Step 4 — `reason()` is called**  
Context:
```json
{
  "intent": "user_idle",
  "context": {
    "driver_id": 2,
    "screen": "product_screen",
    "idle_seconds": 45
  }
}
```
Rule 6 in the system prompt: if `idle_seconds > 10`, OpenAI returns a `spotlight` pointing to the most relevant UI element on that screen. No popup is shown.

---

**Step 5 — Response sent to Flutter**  
```json
{
  "intent_type": "user_idle",
  "deliver_button": { "color": "#DC2626" },
  "sections": [],
  "popup": { "show": false, ... },
  "spotlight": {
    "show": true,
    "target": "next_unscanned_item",
    "text": "Scan the next item on your checklist to keep your delivery on track."
  }
}
```

```
─────────────────────────────────────────────────────────────────
```

---

### INTENT: `stop_selected`

```
─────────────────────────────────────────────────────────────────
```

**Step 1 — Flutter sends WebSocket message**  
```json
{
  "intent_type": "stop_selected",
  "payload": {
    "stop_id": 2,
    "driver_id": 2
  }
}
```

---

**Step 2 — Routes to handler**  
Validates as `StopSelectedPayload`.

---

**Step 3 — Intent handler called**  
Function: `handle_stop_selected(payload: StopSelectedPayload)` in `intent_handler.py`  
Calls `get_stop_details(stop_id)`, builds context with `stop_details`, calls `_reason()`. No distance calculation (that happens in `stop_map_opened`).

---

**Step 4 — MCP tool called: `get_stop_details`**  
Returns stop `id`, `name`, `address`, `lat`, `lng`, `status`.

---

**Step 5 — `reason()` is called**  
Context:
```json
{
  "intent": "stop_selected",
  "context": {
    "driver_id": 2,
    "stop_id": 2,
    "stop_details": { "id": 2, "name": "Hawa Mahal Convenience", "address": "Hawa Mahal Road, Jaipur 302002", "lat": 26.9239, "lng": 75.8267, "status": "pending" }
  }
}
```

---

**Step 6 — Response sent to Flutter**  
```json
{
  "intent_type": "stop_selected",
  "deliver_button": { "color": "#16A34A" },
  "sections": [],
  "popup": { "show": false, ... },
  "spotlight": { "show": false, ... }
}
```

```
─────────────────────────────────────────────────────────────────
```

> **Intents not found in code:** `map_loaded` has a handler (`handle_map_loaded`) and is registered in `HANDLERS` but was not included in the main request list above. It is documented in Section 9 for completeness. The intents `route_map_opened`, `stop_map_opened`, `stop_selected`, `product_screen_loaded`, `item_scanned`, `deliver_tapped`, `count_screen_loaded`, `user_idle`, and `driver_login` are all confirmed present in the code.

---

## Section 6 — Server Push Flow (Dashboard → App)

---

**Step 1 — Operations manager types a command in the web dashboard**  
Endpoint: `POST /command`  
Data sent:
```json
{
  "command": "There is heavy traffic on Tonk Road, warn all drivers"
}
```
Body is validated as `DashboardCommand`. If `command` is blank, a 422 error is returned.

---

**Step 2 — `classify_and_execute()` is called**  
Function: `classify_and_execute(command: str, connected_driver_ids: list)` in `reasoning.py`  
`connected_driver_ids` is obtained from `driver_registry.online_driver_ids()` and appended to the user message as context:  
```
There is heavy traffic on Tonk Road, warn all drivers

[Context: Currently connected driver IDs: [1, 2, 3]]
```
OpenAI receives the `_CLASSIFY_SYSTEM_PROMPT` (classifies as override vs popup), reasons over the text, and returns JSON.

---

**Step 3A — If classified as `"override"`**  
OpenAI returns:
```json
{ "type": "override", "rule": "Warn drivers about heavy traffic on Tonk Road before confirming delivery on that route" }
```
Function called: `add_override(rule)` in `prompt_manager.py`  
What changes: The `rule` string is appended to the `active_overrides` list in memory. Every subsequent call to `get_full_prompt()` will append this rule under `=== LIVE DASHBOARD OVERRIDES ===` in the system prompt sent to OpenAI.

Dashboard receives:
```json
{ "type": "override", "rule": "Warn drivers about heavy traffic on Tonk Road..." }
```

---

**Step 3B — If classified as `"popup"`**  
OpenAI returns:
```json
{
  "type": "popup",
  "target": "all",
  "driver_ids": [],
  "popup": {
    "show": true,
    "blocking": false,
    "title": "Traffic Alert",
    "message": "Heavy traffic reported on Tonk Road. Plan alternative routes where possible.",
    "buttons": [{ "label": "OK", "action": "acknowledge", "visible": true }]
  }
}
```

A `ServerPushMessage` is constructed:
```python
push = ServerPushMessage(popup=popup_data)
message = push.model_dump()
```

- If `target == "all"`: `driver_registry.broadcast(message)` is called — sends to every connected driver. Returns list of `reached` driver IDs. Dead connections are cleaned up automatically.
- If `target == "specific"`: `driver_registry.send_to(int(did), message)` is called for each ID in `driver_ids`. Returns `True` if sent, `False` + cleans up if driver disconnected.

Data pushed to each Flutter client:
```json
{
  "type": "server_push",
  "popup": {
    "show": true,
    "blocking": false,
    "title": "Traffic Alert",
    "message": "Heavy traffic reported on Tonk Road. Plan alternative routes where possible.",
    "buttons": [{ "label": "OK", "action": "acknowledge", "visible": true }]
  }
}
```

---

**Step 4 — Flutter receives the server push**  
Flutter identifies this as a server-pushed notification by checking for `"type": "server_push"` in the incoming WebSocket message. When present, it displays the popup immediately regardless of which screen the driver is on.  
The `blocking` field determines whether the driver can dismiss it by tapping outside (`false`) or must tap a button (`true`).

Dashboard receives:
```json
{
  "type": "popup",
  "status": "sent",
  "target": "all",
  "reached": [1, 2, 3],
  "not_connected": []
}
```

---

## Section 7 — Prompt Manager

### Base System Prompt

The base prompt (`BASE_SYSTEM_PROMPT` in `prompt_manager.py`) is a constant string containing the following sections:

#### Response Format Rules
- Always return valid JSON, never plain text or markdown
- Exact schema: `deliver_button`, `sections`, `popup`, `spotlight`
- `deliver_button.color` must be one of three hex values: `#DC2626` (red), `#F59E0B` (amber), `#16A34A` (green)
- `sections` is only populated on `product_screen_loaded`; return `[]` for all other intents
- `popup.show` only `true` when driver must see something
- For `route_map_opened` and `stop_map_opened` additional fields required: `map_mode`, `stat_cards`, `ai_message`, and map-specific fields

#### Delivery Rules
| Rule | Condition | AI Action |
|---|---|---|
| Rule 0 — Driver Login | Active override blocks this driver | Red button + blocking popup with "OK" dismiss |
| Rule 1 — Location Threshold | Driver > 100 m from stop | Non-blocking popup with `override_location` + `cancel` buttons, button not green |
| Rule 2 — Cigarettes & Tobacco | Any `cig_tob` item missing from `scanned_items` | Red button + blocking popup listing missing items |
| Rule 3 — Required Items | Any `isRequired: true` item missing | Red button + blocking popup with action button |
| Rule 4 — Photo Items | Any `item_type: "photo"` not completed | `photoMandatory: true`, treat as missing |
| Rule 5 — New Driver | `is_new_driver: true` | Spotlight on first screen loaded |
| Rule 6 — Idle Driver | `idle_seconds > 10` | Spotlight on most relevant UI element, no popup |
| Rule 7 — Route Map | `route_map_opened` intent | 4–6 stat_cards, Haversine distance, 30 km/h ETA, 5 km/L fuel |
| Rule 8 — Stop Map | `stop_map_opened` intent | 3–5 stat_cards, set `start_delivery_enabled` from context (overrideable by dashboard rule) |

#### Deliver Button Logic
- **Green** `#16A34A`: all required items done, driver ≤ 100 m, no blockers
- **Amber** `#F59E0B`: partially complete
- **Red** `#DC2626`: missing required items, outside threshold, or any blocker

#### General Guidance
- Popup messages ≤ 2 sentences
- Spotlight text ≤ 15 words, single friendly sentence
- Never expose internal field names in user-facing text
- If context contains an `"error"` key, return red button + non-blocking popup

---

### Override Storage

```python
active_overrides: list[str] = []
```

A simple **in-memory Python list** of strings. Lives at module level in `prompt_manager.py`. Because it is in-memory, overrides are **cleared on every server restart** (acceptable for POC).

- `add_override(rule: str)` — appends `rule.strip()` to the list
- `clear_overrides()` — calls `active_overrides.clear()`

---

### How `get_full_prompt()` Assembles the Final Prompt

```python
def get_full_prompt() -> str:
    if not active_overrides:
        return BASE_SYSTEM_PROMPT

    overrides_block = "\n".join(
        f"  {i + 1}. {rule}" for i, rule in enumerate(active_overrides)
    )
    return (
        BASE_SYSTEM_PROMPT
        + "\n\n=== LIVE DASHBOARD OVERRIDES (take priority over defaults) ===\n"
        + overrides_block
    )
```

If `active_overrides` is empty, returns the base prompt unchanged.  
Otherwise, appends a numbered override section after the base prompt.

---

### Example Full Prompt with 2 Active Overrides

```
You are the AI assistant for GSC (Golden State Convenience) delivery drivers.
[...base prompt content...]

=== LIVE DASHBOARD OVERRIDES (take priority over defaults) ===
  1. Do not allow Jordan Lee to start any deliveries today — their vehicle is under inspection
  2. Warn all drivers: the Sindhi Camp area requires a police escort — contact dispatch before delivery
```

---

## Section 8 — Driver Registry

### Data Structure

```python
class DriverRegistry:
    def __init__(self) -> None:
        self._connections: dict[int, WebSocket] = {}
```

A plain Python `dict` mapping integer `driver_id` → active `WebSocket` object. Lives at module level in `main.py` as `driver_registry = DriverRegistry()`. All connected drivers are in this dict.

---

### How a Driver Gets Registered

**Trigger:** After `websocket_endpoint()` successfully processes a `driver_login` intent AND the response contains a non-`None` `response.driver` field.

```python
if packet.intent_type == "driver_login" and response.driver is not None:
    driver_registry.register(response.driver.id, ws)
```

Function: `driver_registry.register(driver_id: int, ws: WebSocket)` — sets `self._connections[driver_id] = ws`. If a driver logs in again on a new connection, their entry is overwritten with the new WebSocket.

---

### How a Driver Gets Unregistered

**Trigger:** When the WebSocket connection disconnects (the `WebSocketDisconnect` exception is caught in `websocket_endpoint()`).

```python
except WebSocketDisconnect:
    driver_registry.unregister_ws(ws)
```

Function: `driver_registry.unregister_ws(ws: WebSocket)` — iterates `_connections`, finds all entries whose WebSocket matches `ws`, and deletes them.

Also happens automatically during `broadcast()` or `send_to()` — if a send fails (any exception), that driver ID is removed from `_connections`.

---

### How `broadcast()` Works

```python
async def broadcast(self, message: dict) -> list[int]:
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
```

Iterates all entries. If any single send fails, that driver is added to a `dead` list and removed after the loop (does not interrupt delivery to other drivers). Returns a list of driver IDs that were successfully reached.

---

### How `send_to()` Works

```python
async def send_to(self, driver_id: int, message: dict) -> bool:
    ws = self._connections.get(driver_id)
    if ws is None:
        return False
    try:
        await ws.send_text(json.dumps(message, default=str))
        return True
    except Exception:
        del self._connections[driver_id]
        return False
```

If the `driver_id` is not in `_connections`, returns `False` immediately (driver is offline). If the send fails, removes the dead entry and returns `False`. The `post_command` endpoint collects all `False` results into a `not_connected` list that is returned to the dashboard.

---

## Section 9 — Function Quick Reference Table

### `mcp_server/database/connection.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `get_db()` | `connection.py` | All tool functions | `sqlite3.connect()` | Context manager yielding `sqlite3.Connection` |
| `init_db()` | `connection.py` | `server.py` lifespan | `get_db()` | `None` (drops + recreates tables, seeds data) |

---

### `mcp_server/tools/driver.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `register(mcp)` | `driver.py` | `server.py`, `intent_handler.py` (_ToolRegistry) | Attaches nested functions | `None` |
| `get_driver_profile(driver_id)` | `driver.py` | `handle_driver_login()` | `get_db()` | `dict` with `id, name, experience_level, is_new_driver` or `{"error": str}` |
| `get_driver_by_name(name)` | `driver.py` | `handle_driver_login()` | `get_db()` | Same shape as `get_driver_profile` |

---

### `mcp_server/tools/stops.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `register(mcp)` | `stops.py` | `server.py`, `intent_handler.py` | Attaches nested functions | `None` |
| `get_route_for_driver(driver_id)` | `stops.py` | `handle_driver_login()` | `get_db()` | `dict` with `route_id, route_name, route_status, stops[]` |
| `get_stop_details(stop_id)` | `stops.py` | `handle_stop_selected()`, `handle_map_loaded()`, `handle_stop_map_opened()` | `get_db()` | `dict` with `id, name, address, lat, lng, status` |
| `get_route_summary(route_id, driver_id)` | `stops.py` | `handle_route_map_opened()` | `get_db()` | `dict` with `route_id, route_name, total_stops, completed_stops, remaining_stops, stops_coordinates[]` |
| `get_next_stop(route_id)` | `stops.py` | Not called by any handler (registered but unused at runtime) | `get_db()` | `dict` with next pending stop fields or all-completed message |

---

### `mcp_server/tools/products.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `register(mcp)` | `products.py` | `server.py`, `intent_handler.py` | Attaches nested functions | `None` |
| `get_products(stop_id)` | `products.py` | `handle_product_screen_loaded()`, `handle_count_screen_loaded()` | `get_db()` | `dict` with `stop_id, count, products[]` |
| `reconcile_inventory(stop_id, scanned_items)` | `products.py` | `handle_product_screen_loaded()`, `handle_item_scanned()`, `handle_deliver_tapped()` | `get_db()` | `dict` with `stop_id, summary{}, complete[], missing[], unrecognised[]` |

---

### `orchestrator/prompt_manager.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `get_full_prompt()` | `prompt_manager.py` | `_reason()` in `intent_handler.py`, `_on_startup()` in `main.py` | None | `str` — full system prompt with optional override block |
| `add_override(rule)` | `prompt_manager.py` | `post_override()`, `post_command()` in `main.py` | None | `None` |
| `clear_overrides()` | `prompt_manager.py` | `delete_overrides()` in `main.py` | None | `None` |

---

### `orchestrator/reasoning.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `_get_client()` | `reasoning.py` | `reason()`, `classify_and_execute()` | `OpenAI()` | `OpenAI` client instance (lazy singleton) |
| `_safe_default(reason)` | `reasoning.py` | `reason()` on failure | None | `OrchestratorResponse` with red button + error popup |
| `reason(intent, context_data, full_prompt)` | `reasoning.py` | `_reason()` in `intent_handler.py` | `_get_client()`, `OpenAI.chat.completions.create()` | `OrchestratorResponse` |
| `classify_and_execute(command, connected_driver_ids)` | `reasoning.py` | `post_command()` in `main.py` | `_get_client()`, `OpenAI.chat.completions.create()` | `dict` with `type: "override"/"popup"` and associated fields |

---

### `orchestrator/intent_handler.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `_reason(intent, context)` | `intent_handler.py` | All `handle_*` functions | `reasoning.reason()`, `get_full_prompt()` | `OrchestratorResponse` |
| `_build_route(route_data)` | `intent_handler.py` | `handle_driver_login()` | None | `RouteSchema` |
| `_haversine(lat1, lon1, lat2, lon2)` | `intent_handler.py` | `handle_stop_map_opened()` | None | `float` (km) |
| `handle_driver_login(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `get_driver_profile()` or `get_driver_by_name()`, `get_route_for_driver()`, optionally `_reason()` | `OrchestratorResponse` |
| `handle_stop_selected(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `get_stop_details()`, `_reason()` | `OrchestratorResponse` |
| `handle_map_loaded(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `get_stop_details()`, `_reason()` | `OrchestratorResponse` |
| `handle_product_screen_loaded(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `get_products()`, `reconcile_inventory()`, `_reason()` | `OrchestratorResponse` |
| `handle_item_scanned(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `reconcile_inventory()`, `_reason()` | `OrchestratorResponse` |
| `handle_deliver_tapped(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `reconcile_inventory()`, `_reason()` | `OrchestratorResponse` |
| `handle_count_screen_loaded(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `get_products()`, `_reason()` | `OrchestratorResponse` |
| `handle_user_idle(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `_reason()` | `OrchestratorResponse` |
| `handle_route_map_opened(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `get_route_summary()`, `_reason()` | `OrchestratorResponse` |
| `handle_stop_map_opened(payload)` | `intent_handler.py` | `websocket_endpoint()` via `HANDLERS` | `get_stop_details()`, `_haversine()`, `_reason()` | `OrchestratorResponse` |

---

### `orchestrator/main.py`

| Function Name | File | Called By | Calls | Returns |
|---|---|---|---|---|
| `LogBroadcaster.connect(ws)` | `main.py` | `log_endpoint()` | `ws.accept()` | `None` |
| `LogBroadcaster.disconnect(ws)` | `main.py` | `log_endpoint()` on disconnect | None | `None` |
| `LogBroadcaster.broadcast(message)` | `main.py` | `websocket_endpoint()` after each intent | `ws.send_text()` for each client | `None` |
| `DriverRegistry.register(driver_id, ws)` | `main.py` | `websocket_endpoint()` on successful `driver_login` | None | `None` |
| `DriverRegistry.unregister_ws(ws)` | `main.py` | `websocket_endpoint()` on `WebSocketDisconnect` | None | `None` |
| `DriverRegistry.online_driver_ids()` | `main.py` | `get_online_drivers()`, `post_command()` | None | `list[int]` |
| `DriverRegistry.send_to(driver_id, message)` | `main.py` | `post_command()` for specific-target push | `ws.send_text()` | `bool` |
| `DriverRegistry.broadcast(message)` | `main.py` | `post_command()` for all-target push | `ws.send_text()` for each driver | `list[int]` reached |
| `websocket_endpoint(ws)` | `main.py` | FastAPI WebSocket router on `/ws` | `HANDLERS[intent_type]()`, `log_broadcaster.broadcast()`, `driver_registry.register()` | `None` (async loop) |
| `log_endpoint(ws)` | `main.py` | FastAPI WebSocket router on `/ws/log` | `log_broadcaster.connect/disconnect()` | `None` (async loop) |
| `post_override(body)` | `main.py` | `POST /override` | `add_override()` | `dict` |
| `delete_overrides()` | `main.py` | `DELETE /overrides` | `clear_overrides()` | `dict` |
| `get_overrides()` | `main.py` | `GET /overrides` | None | `dict` |
| `get_online_drivers()` | `main.py` | `GET /drivers/online` | `driver_registry.online_driver_ids()` | `dict` |
| `post_command(body)` | `main.py` | `POST /command` | `driver_registry.online_driver_ids()`, `classify_and_execute()`, `add_override()`, `driver_registry.broadcast()` or `send_to()` | `dict` |

---

## Section 10 — Data Structures Quick Reference

---

### Intent Packet — Flutter → Backend

**Direction:** Flutter → Backend (WebSocket `/ws`)  
**Standard envelope:**
```json
{
  "intent_type": "string — one of the intent types listed below",
  "payload": { }
}
```
**Alternate flat envelope** (also accepted, normalised by `websocket_endpoint()`):
```json
{
  "event": "route_map_opened",
  "driver_id": "1",
  "route_id": "1",
  "driver_lat": 26.9312,
  "driver_lng": 75.7824
}
```

#### Example per intent type:

**driver_login:**
```json
{ "intent_type": "driver_login", "payload": { "driver_id": 1 } }
```
Also accepted:
```json
{ "intent_type": "driver_login", "payload": { "name": "Marcus Webb" } }
{ "intent_type": "driver_login", "payload": { "username": "marcus_webb" } }
```

**stop_selected:**
```json
{ "intent_type": "stop_selected", "payload": { "stop_id": 1, "driver_id": 2 } }
```

**map_loaded:**
```json
{ "intent_type": "map_loaded", "payload": { "stop_id": 1, "driver_id": 2, "distance_m": 85.3, "lat": 26.9241, "lng": 75.8269 } }
```

**route_map_opened:**
```json
{ "intent_type": "route_map_opened", "payload": { "driver_id": 1, "route_id": 1, "driver_lat": 26.9312, "driver_lng": 75.7824 } }
```

**stop_map_opened:**
```json
{ "intent_type": "stop_map_opened", "payload": { "driver_id": 2, "route_id": 2, "stop_id": 1, "driver_lat": 26.924, "driver_lng": 75.827 } }
```

**product_screen_loaded:**
```json
{ "intent_type": "product_screen_loaded", "payload": { "stop_id": 1, "driver_id": 2, "scanned_items": [] } }
```

**item_scanned:**
```json
{ "intent_type": "item_scanned", "payload": { "stop_id": 1, "item_id": 2, "driver_id": 2, "scanned_items": ["Marlboro Red 20s"] } }
```

**deliver_tapped:**
```json
{ "intent_type": "deliver_tapped", "payload": { "stop_id": 1, "driver_id": 2, "scanned_items": ["Marlboro Red 20s", "Lambert & Butler King Size", "Amber Leaf 50g Pouch"] } }
```

**count_screen_loaded:**
```json
{ "intent_type": "count_screen_loaded", "payload": { "stop_id": 1, "driver_id": 2 } }
```

**user_idle:**
```json
{ "intent_type": "user_idle", "payload": { "screen": "product_screen", "driver_id": 2, "idle_seconds": 45 } }
```

---

### Login Response — Backend → Flutter

**Direction:** Backend → Flutter (WebSocket `/ws`)
```json
{
  "intent_type": "driver_login",
  "deliver_button": { "color": "#16A34A" },
  "sections": [],
  "popup": { "show": false, "blocking": false, "title": "", "message": "", "buttons": [] },
  "spotlight": { "show": true, "target": "route_list", "text": "Welcome! Tap a stop on your route to begin your first delivery." },
  "driver": {
    "id": 3,
    "name": "Jordan Lee",
    "experience_level": "junior",
    "is_new_driver": true
  },
  "route": {
    "route_id": 3,
    "route_name": "Jaipur South Route",
    "route_status": "pending",
    "stops": [
      { "id": 8, "stop_number": 8, "sequence": 1, "name": "Malviya Nagar Superstore", "address": "Malviya Nagar, Jaipur 302017", "lat": 26.8629, "lng": 75.8282, "status": "pending" },
      { "id": 9, "stop_number": 9, "sequence": 2, "name": "Jagatpura Quick Stop", "address": "Jagatpura, Jaipur 302025", "lat": 26.84, "lng": 75.856, "status": "pending" }
    ]
  }
}
```

---

### Route Map Response — Backend → Flutter

**Direction:** Backend → Flutter (WebSocket `/ws`)
```json
{
  "intent_type": "route_map_opened",
  "deliver_button": { "color": "#16A34A" },
  "sections": [],
  "popup": { "show": false, "blocking": false, "title": "", "message": "", "buttons": [] },
  "spotlight": { "show": false, "target": "", "text": "" },
  "map_mode": "full_route",
  "stops_coordinates": [
    { "sequence": 1, "stop_id": 16, "name": "Shastri Nagar Daily Mart", "lat": 26.9312, "lng": 75.7824, "status": "pending" },
    { "sequence": 2, "stop_id": 17, "name": "Jhotwara Road Store", "lat": 26.9567, "lng": 75.7934, "status": "pending" }
  ],
  "stat_cards": [
    { "icon": "📍", "label": "Total Distance", "value": "12.4 km", "sublabel": "" },
    { "icon": "⏱", "label": "Estimated Time", "value": "24 min", "sublabel": "at 30 km/h avg" },
    { "icon": "⛽", "label": "Fuel Estimate", "value": "1.0 L", "sublabel": "" },
    { "icon": "🏪", "label": "Stops Remaining", "value": "7", "sublabel": "" }
  ],
  "ai_message": "Your route looks clear. Starting from Shastri Nagar, work north through Jhotwara."
}
```

---

### Stop Map Response — Backend → Flutter

**Direction:** Backend → Flutter (WebSocket `/ws`)
```json
{
  "intent_type": "stop_map_opened",
  "deliver_button": { "color": "#16A34A" },
  "sections": [],
  "popup": { "show": false, "blocking": false, "title": "", "message": "", "buttons": [] },
  "spotlight": { "show": false, "target": "", "text": "" },
  "map_mode": "single_stop",
  "stop": { "id": 1, "name": "Pink City Kirana Store", "address": "Johari Bazaar, Jaipur 302003", "lat": 26.9239, "lng": 75.8267, "status": "pending" },
  "next_stop": { "id": 1, "name": "Pink City Kirana Store", "address": "Johari Bazaar, Jaipur 302003", "lat": 26.9239, "lng": 75.8267, "status": "pending" },
  "start_delivery_enabled": true,
  "distance_to_stop_km": 0.012,
  "stat_cards": [
    { "icon": "📏", "label": "Distance to Stop", "value": "12 m", "sublabel": "" },
    { "icon": "🚶", "label": "Estimated Arrival", "value": "< 1 min", "sublabel": "walking" },
    { "icon": "🏪", "label": "Stop Number", "value": "Stop 1 of 7", "sublabel": "" },
    { "icon": "🚬", "label": "Double Scan Required", "value": "cig_tob", "sublabel": "3 items" }
  ],
  "ai_message": "You're right at Pink City Kirana Store. Tap Start Delivery when ready."
}
```

---

### Server Push Popup — Backend → Flutter

**Direction:** Backend → Flutter (WebSocket `/ws`, unsolicited push)  
Flutter detects this by: checking for `"type": "server_push"` on every incoming WebSocket message.
```json
{
  "type": "server_push",
  "popup": {
    "show": true,
    "blocking": false,
    "title": "Traffic Alert",
    "message": "Heavy traffic reported on Tonk Road. Plan alternative routes where possible.",
    "buttons": [
      { "label": "OK", "action": "acknowledge", "visible": true }
    ]
  }
}
```
For urgent/safety messages, `blocking: true` is used — the driver cannot dismiss by tapping outside; they must press a button.

---

### Dashboard Command — Dashboard → Backend

**Direction:** Dashboard → Backend (`POST /command`)
```json
{
  "command": "There is heavy traffic on Tonk Road, warn all drivers"
}
```
- Field: `command` (string, required, must not be blank)
- A 422 error is returned if the command is empty

---

### Override Response — Backend → Dashboard

Returned by `POST /command` when AI classifies the command as an override, and also by `POST /override` directly:
```json
{
  "type": "override",
  "rule": "Warn drivers about heavy traffic on Tonk Road before confirming delivery on that route"
}
```
`POST /override` returns:
```json
{
  "status": "added",
  "rule": "Do not allow Jordan Lee to start deliveries today",
  "total_overrides": 1
}
```

---

### Popup Sent Response — Backend → Dashboard

Returned by `POST /command` when AI classifies the command as a popup push:
```json
{
  "type": "popup",
  "status": "sent",
  "target": "all",
  "reached": [1, 2, 3],
  "not_connected": []
}
```
For a specific-driver push:
```json
{
  "type": "popup",
  "status": "sent",
  "target": "specific",
  "reached": [1],
  "not_connected": [4]
}
```
Where `reached` contains IDs of drivers who received the message and `not_connected` contains IDs of drivers who were offline at the time.

---

*End of FLOW_DOCUMENTATION.md*
