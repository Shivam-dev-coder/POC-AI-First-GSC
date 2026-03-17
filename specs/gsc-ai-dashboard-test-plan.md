# GSC AI Dashboard Test Plan

## Application Overview

The GSC AI Dashboard is a React (Vite) single-page application running at http://localhost:5173 that communicates with a FastAPI orchestrator at http://localhost:8000. It is a Delivery Logic Control Panel for managing AI behavior for delivery drivers of GSC (Golden State Convenience). The dashboard has five main sections: Overview (stat cards), Command Centre (rule/popup commands), Active Overrides (list of AI rules), Live Log (real-time WebSocket feed), and System Prompt (read-only base prompt viewer). Key flows include applying plain-English rule overrides via AI classification, sending popup messages to drivers, clearing all override rules, and monitoring real-time driver activity via WebSocket.

## Test Scenarios

### 1. Sidebar and Page Load

**Seed:** `gsc-ai-backend/seed.spec.ts`

#### 1.1. Page loads with correct heading

**File:** `specs/dashboard/sidebar.spec.ts`

**Steps:**
  1. Navigate to http://localhost:5173
    - expect: Page renders without error
    - expect: h1 displays '🚚 GSC AI Dashboard'
    - expect: Browser tab title reads 'GSC AI Dashboard'

#### 1.2. Sidebar renders all five navigation links

**File:** `specs/dashboard/sidebar.spec.ts`

**Steps:**
  1. Navigate to the dashboard and inspect the left sidebar nav element
    - expect: Sidebar is fixed on the left with dark background
    - expect: Five links are present: Overview, Command Centre, Active Overrides, Live Log, System Prompt
    - expect: Each link is prefixed with its emoji icon

#### 1.3. Sidebar shows subtitle Delivery Logic Control Panel

**File:** `specs/dashboard/sidebar.spec.ts`

**Steps:**
  1. Navigate to the dashboard
    - expect: Text 'Delivery Logic Control Panel' is visible beneath the logo heading in grey

#### 1.4. Sidebar footer shows orchestrator address

**File:** `specs/dashboard/sidebar.spec.ts`

**Steps:**
  1. Navigate to the dashboard and scroll to the bottom of the sidebar
    - expect: Text 'Orchestrator · localhost:8000' is visible at the bottom of the sidebar

#### 1.5. Navigation links scroll to correct page sections

**File:** `specs/dashboard/sidebar.spec.ts`

**Steps:**
  1. Click each sidebar link one by one: Overview, Command Centre, Active Overrides, Live Log, System Prompt
    - expect: Each click scrolls main content so the corresponding h2 heading is in the viewport
    - expect: URL fragment updates (e.g. #command-centre)

#### 1.6. Sidebar link hover state is visible

**File:** `specs/dashboard/sidebar.spec.ts`

**Steps:**
  1. Hover over each sidebar link
    - expect: Background changes to darker grey
    - expect: Text changes to white on hover for each link

### 2. Overview Section

**Seed:** `gsc-ai-backend/seed.spec.ts`

#### 2.1. Three stat cards render on load

**File:** `specs/dashboard/overview.spec.ts`

**Steps:**
  1. Navigate to the dashboard and observe the Overview section
    - expect: Stat card labeled 'Active Overrides' is visible
    - expect: Stat card labeled 'Orchestrator' is visible
    - expect: Stat card labeled 'Current Time' is visible
    - expect: Each card has an icon, grey uppercase label, and bold value

#### 2.2. Active Overrides count is zero with no overrides

**File:** `specs/dashboard/overview.spec.ts`

**Steps:**
  1. Call DELETE http://localhost:8000/overrides to clear all state, then navigate to the dashboard
    - expect: 'Active Overrides' stat card shows value 0

#### 2.3. Active Overrides count reflects current API state

**File:** `specs/dashboard/overview.spec.ts`

**Steps:**
  1. POST two rules to http://localhost:8000/override, then navigate to the dashboard
    - expect: 'Active Overrides' stat card shows value 2

#### 2.4. Orchestrator stat shows Online when backend is running

**File:** `specs/dashboard/overview.spec.ts`

**Steps:**
  1. Ensure orchestrator is running, navigate to the dashboard, wait up to 6 seconds
    - expect: 'Orchestrator' card shows 'Online' in green text
    - expect: Icon is 🟢

#### 2.5. Orchestrator stat shows Offline when backend is down

**File:** `specs/dashboard/overview.spec.ts`

**Steps:**
  1. Stop the orchestrator server, navigate to the dashboard, wait for the initial fetch to complete
    - expect: 'Orchestrator' card shows 'Offline' in red text
    - expect: Icon is 🔴

#### 2.6. Current Time stat auto-updates every second

**File:** `specs/dashboard/overview.spec.ts`

**Steps:**
  1. Navigate to the dashboard and read the Current Time card value
    - expect: A time string is displayed in format HH:MM:SS AM/PM
  2. Wait 1.1 seconds and read the Current Time card value again
    - expect: The two time values are different, confirming the clock increments live

### 3. Command Centre

**Seed:** `gsc-ai-backend/seed.spec.ts`

#### 3.1. Quick Commands section shows 8 buttons

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Navigate to the dashboard and scroll to the Command Centre section
    - expect: Label 'QUICK COMMANDS' is visible in small uppercase grey text
    - expect: Exactly 8 quick-command buttons are displayed in a responsive grid

#### 3.2. All eight quick-command button labels are correct

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Navigate to the dashboard and read each quick-command button text
    - expect: Button text 1: "Don't show location override popup on map screen"
    - expect: Button text 2: "Hard block Stop 4 — no override allowed"
    - expect: Button text 3: "Cigarettes must be scanned twice and manually counted"
    - expect: Button text 4: "All damaged items require a photo before delivery"
    - expect: Button text 5: "Driver ID 1 is new — enable spotlight guidance on all screens"
    - expect: Button text 6: "Clear all location restrictions"
    - expect: Button text 7: "Send a popup to all drivers: please check your next stop details"
    - expect: Button text 8: "Send urgent popup to all drivers: route has changed, check the app"

#### 3.3. Clicking a quick-command button populates the textarea

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Click the quick-command button "Hard block Stop 4 — no override allowed"
    - expect: Textarea value is set to "Hard block Stop 4 — no override allowed"
    - expect: No form submission occurs automatically

#### 3.4. Textarea shows correct placeholder text

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Navigate to the dashboard and ensure the textarea is empty
    - expect: Textarea displays placeholder text mentioning 'Hard block Stop 4' and 'Send a popup to all drivers'

#### 3.5. Apply button is disabled when textarea is empty

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Navigate to the dashboard and ensure the textarea is empty
    - expect: Apply button has disabled attribute
    - expect: Button shows reduced opacity and cursor-not-allowed style
    - expect: Clicking the button has no effect

#### 3.6. Apply button is disabled for whitespace-only input

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Type only spaces into the textarea
    - expect: Apply button remains disabled (whitespace-only input is treated as empty)

#### 3.7. Apply button becomes enabled after typing text

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Type 'Test command' into the textarea
    - expect: Apply button is enabled and clickable

#### 3.8. Applying a rule override shows green success toast

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Type 'Warn drivers about wet floor at Stop 3' into textarea and click Apply
    - expect: Loading spinner ⏳ appears on the Apply button during the API call
    - expect: Apply button is disabled during loading to prevent double-submission
  2. Wait up to 20 seconds for the AI response
    - expect: Green toast notification appears at bottom-right: '✅ Rule applied — AI updated'
    - expect: Textarea is cleared after successful submission
    - expect: Toast auto-dismisses after approximately 4 seconds

#### 3.9. Applying a popup command shows blue info toast

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Type 'Send a popup to all drivers: road closed ahead' into textarea and click Apply, wait up to 20 seconds
    - expect: Blue toast notification appears: '📣 Popup sent to X driver(s)'
    - expect: If drivers not connected, text includes '(N not connected)'
    - expect: Toast auto-dismisses after approximately 4 seconds

#### 3.10. Applying a rule updates Active Overrides count without page reload

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Clear all overrides, navigate to dashboard, confirm 'Active Overrides' shows 0
    - expect: Overview stat card shows 0
  2. Apply rule 'Block fragile item stops during rain' and wait for success toast
    - expect: 'Active Overrides' stat card increments to 1 without page refresh

#### 3.11. API error shows red error toast

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Stop the orchestrator server, type a command, and click Apply
    - expect: Red toast notification appears with message starting 'Failed:' followed by error detail
    - expect: Toast auto-dismisses after approximately 4 seconds

#### 3.12. Clear All Rules button shows confirmation dialog

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. With at least one override present, click '🗑️ Clear All Rules'
    - expect: Browser confirm() dialog appears with message: 'Remove all active override rules? The AI will revert to the base system prompt.'
  2. Click Cancel on the dialog
    - expect: No overrides are cleared
    - expect: No toast appears
    - expect: Active Overrides section is unchanged

#### 3.13. Confirming Clear All shows red toast and clears all overrides

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. With at least one override present, click 'Clear All Rules' and accept the confirmation dialog
    - expect: Red toast appears: '🗑️ All rules cleared'
    - expect: Active Overrides section shows empty state
    - expect: 'Active Overrides' stat card shows 0
    - expect: Toast auto-dismisses after approximately 4 seconds

#### 3.14. Second toast replaces first if applied within 4 seconds

**File:** `specs/dashboard/command-centre.spec.ts`

**Steps:**
  1. Apply a first rule and observe the toast, then within 4 seconds apply a second rule
    - expect: Only one toast is visible at any time
    - expect: The second toast replaces the first toast

### 4. Active Overrides

**Seed:** `gsc-ai-backend/seed.spec.ts`

#### 4.1. Empty state shown when no overrides are active

**File:** `specs/dashboard/active-overrides.spec.ts`

**Steps:**
  1. Call DELETE /overrides to clear all, then navigate to the dashboard and scroll to Active Overrides
    - expect: Dashed-border empty state panel is visible
    - expect: 🤖 emoji icon is shown
    - expect: Text 'No active overrides.' is visible
    - expect: Sub-text 'AI is running on the base system prompt.' is visible

#### 4.2. Override card displays rule text and AI Active badge

**File:** `specs/dashboard/active-overrides.spec.ts`

**Steps:**
  1. POST rule 'Require photo for all fragile items' to /override, then navigate to the dashboard
    - expect: Card is visible with rule text 'Require photo for all fragile items'
    - expect: '⚙️ AI Active' purple pill badge is shown on the card

#### 4.3. Override card shows numbered badge starting from 1

**File:** `specs/dashboard/active-overrides.spec.ts`

**Steps:**
  1. Add one override via the API, then navigate to the dashboard
    - expect: Purple circle badge on the card shows '1'

#### 4.4. Multiple overrides get numbered cards in order

**File:** `specs/dashboard/active-overrides.spec.ts`

**Steps:**
  1. Clear overrides, then POST Rule A, Rule B, and Rule C in order, then navigate to the dashboard
    - expect: Three distinct cards appear in correct order
    - expect: Badges show 1, 2, 3 respectively
    - expect: Each card shows the correct rule text

#### 4.5. Override card displays added-at timestamp

**File:** `specs/dashboard/active-overrides.spec.ts`

**Steps:**
  1. Note the current time, apply a rule via the Command Centre UI, then observe the resulting override card
    - expect: Card shows a time string in the bottom-right corner in locale time format
    - expect: Timestamp approximately reflects when the rule was applied

### 5. Live Log

**Seed:** `gsc-ai-backend/seed.spec.ts`

#### 5.1. Live Log section heading is visible

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Navigate to the dashboard and scroll to the Live Log section
    - expect: h2 heading 'Live Log' is visible

#### 5.2. Connection status badge is visible on page load

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Navigate to the dashboard and immediately observe the Live Log status badge
    - expect: A status badge appears showing one of: '🟡 Reconnecting…', '🟢 Connected', '⚪ Disconnected', or '🔴 Error'

#### 5.3. Status badge shows Connected within 8 seconds when orchestrator is running

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Ensure orchestrator is running, navigate to the dashboard, wait up to 8 seconds
    - expect: Status badge shows '🟢 Connected'

#### 5.4. Status badge shows Disconnected when WebSocket is unavailable

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Stop the orchestrator server, navigate to the dashboard, wait at least 4 seconds
    - expect: Status badge shows '⚪ Disconnected' or '🔴 Error'
    - expect: Badge does NOT show '🟢 Connected'

#### 5.5. Entry count label is visible

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Navigate to the dashboard and scroll to the Live Log section
    - expect: A label showing 'X entries' is visible (X may be 0 or more)

#### 5.6. Clear Log button resets the entry count to 0

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Navigate to the dashboard, allow log entries to accumulate, then click the 'Clear Log' button
    - expect: Entry count resets to '0 entries'
    - expect: Log feed area shows no entries

#### 5.7. Log entries show correct labels for each direction

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Wait for at least one inbound and one outbound log entry to appear
    - expect: Inbound entries show blue label 'Flutter → AI' with blue left border
    - expect: Outbound entries show purple label 'AI → Flutter' with purple left border
    - expect: Error entries show red label 'Error' with red left border

#### 5.8. Log entry shows event name and timestamp

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Wait for at least one log entry to appear and inspect its content
    - expect: Each entry row displays the intent/event name (e.g. 'driver_login')
    - expect: Each entry row displays a time string on the right side in locale format

#### 5.9. Clicking json button on a log entry expands the JSON payload

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Wait for at least one log entry, then click the '▼ json' button on any entry
    - expect: A dark code block expands below the entry header
    - expect: Formatted JSON payload is displayed in green monospace text
    - expect: Button text changes to '▲ hide'
  2. Click the '▲ hide' button
    - expect: JSON payload collapses and code block is hidden
    - expect: Button text returns to '▼ json'

#### 5.10. Log is capped at 100 entries maximum

**File:** `specs/dashboard/live-log.spec.ts`

**Steps:**
  1. Simulate 105 sequential intents from a driver WebSocket client
    - expect: Entry count shown is 100
    - expect: Oldest entries are dropped
    - expect: Only the newest 100 entries are kept

### 6. System Prompt

**Seed:** `gsc-ai-backend/seed.spec.ts`

#### 6.1. System Prompt section heading is visible

**File:** `specs/dashboard/system-prompt.spec.ts`

**Steps:**
  1. Navigate to the dashboard and scroll to the System Prompt section
    - expect: h2 heading 'System Prompt' is visible

#### 6.2. Code window header bar shows file name annotation

**File:** `specs/dashboard/system-prompt.spec.ts`

**Steps:**
  1. Navigate to the dashboard and observe the dark header bar above the System Prompt code block
    - expect: Header bar displays text: 'orchestrator/prompt_manager.py — BASE_SYSTEM_PROMPT'

#### 6.3. Traffic-light window controls are displayed in header bar

**File:** `specs/dashboard/system-prompt.spec.ts`

**Steps:**
  1. Navigate to the dashboard and observe the System Prompt header bar dots
    - expect: Three colored circle dots appear left-to-right: red, yellow, green

#### 6.4. Code block contains GSC identity text

**File:** `specs/dashboard/system-prompt.spec.ts`

**Steps:**
  1. Navigate to the dashboard and read the System Prompt pre block content
    - expect: Block contains 'You are the AI assistant for GSC (Golden State Convenience) delivery drivers'

#### 6.5. All six delivery rules are present in the code block

**File:** `specs/dashboard/system-prompt.spec.ts`

**Steps:**
  1. Navigate to the dashboard and read the System Prompt code block
    - expect: RULE 1 — LOCATION THRESHOLD is present
    - expect: RULE 2 — CIGARETTES AND TOBACCO is present
    - expect: RULE 3 — REQUIRED ITEMS BLOCK DELIVERY is present
    - expect: RULE 4 — PHOTO ITEMS is present
    - expect: RULE 5 — NEW DRIVER GUIDANCE is present
    - expect: RULE 6 — IDLE DRIVER is present

#### 6.6. Code block is scrollable and does not overflow the page

**File:** `specs/dashboard/system-prompt.spec.ts`

**Steps:**
  1. Navigate to the dashboard and attempt to scroll within the System Prompt code block
    - expect: Code block has an internal scrollbar
    - expect: Max height is capped (approximately 32rem)
    - expect: Block does not push other sections off the page

#### 6.7. System Prompt section is read-only

**File:** `specs/dashboard/system-prompt.spec.ts`

**Steps:**
  1. Navigate to the dashboard and attempt to click or interact with the System Prompt code block content
    - expect: Content is inside a pre element and cannot be edited
    - expect: No edit controls, pencil icons, or form inputs are present in this section
