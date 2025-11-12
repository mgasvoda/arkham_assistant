# Frontend Design — Arkham Assistant

## Overview

React + Vite frontend providing a chat-based interface for deck building, analysis, and card search.

**Target:** Single-user, local desktop browser.

---

## Core Components

### 1. Deck Builder View
- **Purpose:** Add/remove cards, visualize deck composition
- **Layout:** Central pane with table-like grouped card view
- **Features:**
  - **Grouped Card Display:** Cards organized by cost, type, class, or slot/function
  - **Dynamic Grouping:** Categories automatically determined from deck data
  - **Card Grid Layout:** Visual "card-like" items in a responsive grid within each group
  - **Drag-and-Drop Support:** Accept cards dragged from search pane
  - **Quantity Controls:** Add/remove buttons on each card
  - **Group Statistics:** Card count per group displayed in headers
  - **Visual Curves:** Resource cost distribution, class/archetype ratios in sidebar
  - **Responsive:** Grid adapts to screen size (mobile-friendly)

### 2. Deck Search View
- **Purpose:** Browse and filter card database
- **Layout:** Collapsible left-hand pane (350px wide, collapses to 48px)
- **Features:**
  - **Collapsible Pane:** Expand/collapse toggle button for space management
  - **Text Search:** Name, traits, card text search with debouncing
  - **Collapsible Filters:** Expandable filter section below search bar
  - **Filters:** Class, type, owned sets toggle
  - **Drag-to-Add:** Drag search results to deck builder pane
  - **Quick-Add Button:** Plus button on each result for instant add
  - **Compact List View:** Optimized for narrow pane width
  - **Result Details:** Name, cost, type, class, and traits shown inline

### 3. Card Detail Pane
- **Purpose:** Display full card information
- **Data shown:**
  - Name, class, cost, type
  - Full rules text
  - Traits, icons, attributes
  - Set/expansion info
  - Ownership status
  - Related upgrades (if applicable)

### 4. Chat Window
- **Purpose:** Conversational AI interface for deck analysis
- **Features:**
  - Free-form text input
  - Structured recommendation cards (inline "Apply" buttons)
  - Simulation report summaries
  - Conversation history (session-based)
  - Quick actions: "Analyze Deck", "Suggest Swaps", "Run Simulation"

### 5. Simulation Report Modal
- **Purpose:** Visualize simulation results
- **Data displayed:**
  - Draw curves (turns to key cards)
  - Setup time distribution
  - Success rate metrics
  - Key card reliability scores
- **Visual:** Simple charts (bar/line graphs via Recharts or similar)

---

## Interaction Flow: Deck Building

### Card Addition Flow
```
User searches for cards in left pane
  ↓
Results displayed in compact list format
  ↓
User either:
  1. Drags card to deck builder pane → addCard(card)
  2. Clicks + button on result → addCard(card)
  ↓
Card added to active deck
  ↓
Deck builder updates, card appears in appropriate group
```

### Deck Organization Flow
```
User selects grouping: Cost | Type | Class | Slot/Function
  ↓
Frontend analyzes deck cards
  ↓
Groups dynamically created based on card data
  ↓
Cards rendered in grid layout within each group
  ↓
User can add/remove quantities per card
```

### Interaction Flow: Deck Analysis

```
User clicks "Analyze Deck"
  ↓
POST /chat → { deck_id, message: "analyze" }
  ↓
Backend returns structured response:
{
  "summary": "...",
  "recommendations": [
    { "remove": "CardName", "add": "CardName", "reason": "..." }
  ],
  "simulation": { ... }
}
  ↓
Frontend renders:
  - Summary text in chat
  - Recommendation cards with Apply/Ignore buttons
  - Link to open full sim report modal
```

---

## State Management

**Simple approach (no Redux needed):**
- `useState` for local component state
- `useContext` for:
  - Active deck
  - Selected investigator
  - Chat history
- `localStorage` for:
  - Recent decks
  - Chat session cache (optional)

---

## API Integration

**Base URL:** `http://localhost:8000`

| Endpoint         | Method | Purpose                  |
| ---------------- | ------ | ------------------------ |
| `/cards`         | GET    | Search/filter cards      |
| `/deck/:id`      | GET    | Load deck                |
| `/deck`          | POST   | Save deck (create/update)|
| `/run_sim`       | POST   | Run simulation           |
| `/chat`          | POST   | AI agent interaction     |

**Request/Response Examples:**

```javascript
// Search cards
const cards = await fetch('/cards?class=Seeker&type=Asset&owned=true');

// Load deck
const deck = await fetch('/deck/deck_001');

// Chat with AI
const response = await fetch('/chat', {
  method: 'POST',
  body: JSON.stringify({ deck_id: 'deck_001', message: 'analyze this deck' })
});
```

---

## UI/UX Principles

- **Speed:** Local-first, instant updates, async API calls
- **Clarity:** Clear visual hierarchy, no clutter
- **Space Efficiency:** Collapsible search pane maximizes deck view area
- **Visual Organization:** Grouped card view for quick deck cross-section analysis
- **Drag-and-Drop:** Intuitive card addition via drag from search results
- **Feedback:** Loading states, success/error toasts, hover effects
- **Accessibility:** Semantic HTML, keyboard navigation, ARIA labels

---

## Tech Stack

- **Framework:** React 18
- **Build Tool:** Vite
- **Styling:** TailwindCSS (or CSS modules)
- **Charts:** Recharts
- **HTTP:** Native `fetch` or Axios
- **Icons:** Lucide React or Heroicons

---

## File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── DeckBuilder.jsx
│   │   ├── DeckSearch.jsx
│   │   ├── CardDetail.jsx
│   │   ├── ChatWindow.jsx
│   │   ├── SimulationReport.jsx
│   │   └── common/
│   │       ├── Card.jsx
│   │       ├── Button.jsx
│   │       └── Modal.jsx
│   ├── views/
│   │   ├── MainView.jsx
│   │   └── DeckEditorView.jsx
│   ├── context/
│   │   ├── DeckContext.jsx
│   │   └── ChatContext.jsx
│   ├── api/
│   │   └── client.js
│   ├── App.jsx
│   └── main.jsx
└── public/
```

---

## Implementation Notes

- Keep components small and focused
- Use TypeScript for props if desired (optional)
- Mock API during initial development
- Test with sample deck data from architecture doc

---

## Implementation Status

**Completed Components (v0.2.0):**

- ✅ **DeckBuilder**: Enhanced with grouped card layout and drag-and-drop support
  - Dynamic grouping by cost, type, class, or slot/function
  - Card-based visual display with quantity overlays
  - Responsive grid layout adapting to screen size
  - Drop zone for dragged cards from search pane
- ✅ **DeckSearch**: Collapsible left-hand pane with enhanced UX
  - Collapsible pane (350px ↔ 48px) for space efficiency
  - Collapsible filter section within search controls
  - Compact list view optimized for narrow width
  - Drag-and-drop enabled search results
  - Quick-add button per result
- ✅ **ChatWindow**: AI assistant interface with quick actions
- ✅ **SimulationReport**: Modal displaying simulation results and metrics
- ✅ **Common Components**: Button, Modal, Card (reusable UI components)
- ✅ **Context Providers**: DeckContext and ChatContext for state management
- ✅ **API Client**: Full REST API integration layer
- ✅ **Mock Data**: Sample data for development without backend

**UI Features:**

- **New in v0.2.0:**
  - Drag-and-drop card addition from search to deck
  - Collapsible search pane with toggle button
  - Grouped card view with dynamic categorization
  - Card-based visual layout for deck view
  - Slot/function-based grouping algorithm
- Responsive design (desktop, tablet, mobile)
- Dark mode support via CSS prefers-color-scheme
- Loading states and error handling
- Keyboard navigation and accessibility
- Smooth animations and transitions

**Development Server:**

Run `npm run dev` in the frontend directory to start the development server at `http://localhost:5173`.

The frontend will automatically load mock data when the backend API is unavailable, allowing full UI testing.

