# Arkham Assistant — System Design Document

### Version

v0.1 – Initial Design

---

## 🎯 Purpose

**Arkham Assistant** is a local hobby project to assist with *Arkham Horror: The Card Game* deckbuilding, testing, and tuning.
It combines:

* a **ChromaDB** store for card and deck data
* a **Python backend** for simulation, analysis, and AI-assisted recommendations
* a **React frontend** for chat-based interaction and deck management

The project is optimized for local, single-user use with no cloud dependencies.

---

## 🗂️ Data Model (ChromaDB)

Three primary collections (tables):

### 1. `characters`

| Field               | Type          | Notes                                       |
| ------------------- | ------------- | ------------------------------------------- |
| `CharacterID`       | String        | Unique ID                                   |
| `Name`              | String        | Investigator name                           |
| `Class`             | String        | Primary class (e.g. Seeker, Rogue)          |
| `DeckbuildingRules` | JSON          | Class / card restrictions                   |
| `Archetypes`        | Array<String> | Labeled archetypes (manual or AI-generated) |
| `LockedCards`       | Array<CardID> | Signature cards or forced includes          |
| `DeckID`            | FK<Decks>     | Reference to default or active deck         |

---

### 2. `cards`

| Field           | Type              | Notes                                      |
| --------------- | ----------------- | ------------------------------------------ |
| `CardID`        | String            | Primary key                                |
| `Class`         | String            | Used for filtering and ratios              |
| `Cost`          | Int               | Resource cost                              |
| `Type`          | String            | e.g. Asset, Event, Skill                   |
| `Text`          | String            | Card rules text                            |
| `Attributes`    | JSON              | Traits, keywords                           |
| `Icons`         | JSON              | Skill icons                                |
| `Archetypes`    | Array<String>     | Optional generated tags                    |
| `Set`           | String            | Pack or expansion name                     |
| `Function`      | String            | Role in deck (damage, clue, defense, etc.) |
| `Upgrades`      | Array<CardID>     | Upgrade relationships                      |
| `TextEmbedding` | Vector (optional) | Generated for similarity search            |

---

### 3. `decks`

| Field               | Type           | Notes                            |
| ------------------- | -------------- | -------------------------------- |
| `DeckID`            | String         | Primary key                      |
| `CharacterID`       | FK<characters> | Investigator                     |
| `CardList`          | Array<CardID>  | Full deck contents               |
| `Archetype`         | String         | Deck focus (clue, fight, hybrid) |
| `SimulationReports` | Array<JSON>    | Cached sim summaries             |
| `Notes`             | Text           | Freeform notes                   |

---

### Data Flow for Updates

* Manual sync script fetches data from **ArkhamDB API**:

  ```
  GET Packs → GET Cards (by Pack ID)
  ```
* Script writes card and pack data into ChromaDB via backend’s Data Fetching Service.
* No AI-driven web pulls — refresh only when adding a new expansion.

---

## ⚙️ Backend (Python)

### Components

| Module                    | Responsibilities                                                |
| ------------------------- | --------------------------------------------------------------- |
| **Data Fetching Service** | Fetch card data from ArkhamDB once; handle Chroma insert/update |
| **Simulator**             | Run randomized draw simulations, compile per-deck metrics       |
| **AI Agent**              | Orchestrate recommendations, summarize decks, tag archetypes    |
| **CRUD API**              | Expose REST endpoints for deck/card operations                  |

---

### Endpoints (Initial)

| Method          | Route                                                                 | Purpose |
| --------------- | --------------------------------------------------------------------- | ------- |
| `GET /cards`    | Search/filter cards                                                   |         |
| `GET /deck/:id` | Retrieve deck and metadata                                            |         |
| `POST /deck`    | Create or update deck                                                 |         |
| `POST /run_sim` | Run simulation for a given deck                                       |         |
| `POST /chat`    | Send a chat message to the AI agent (deck analysis / recommendations) |         |

---

### Simulation Engine

* **Input:** Deck ID or card list
* **Process:** Simulates random draws / mulligans, tracks success and tempo metrics
* **Output:** JSON report

  ```json
  {
    "avg_draws_per_turn": 3.1,
    "setup_time": 2.8,
    "success_rate": 0.74,
    "key_card_reliability": 0.85
  }
  ```

---

### AI Agent Tools

The backend agent runs locally and uses callable Python functions as tools:

| Tool                                | Function                                             |
| ----------------------------------- | ---------------------------------------------------- |
| `get_card_details(card_ids)`        | Query Chroma for cards                               |
| `get_deck(deck_id)`                 | Retrieve deck definition                             |
| `run_simulation(deck_id, n_trials)` | Call simulator and return report                     |
| `get_static_info(topic)`            | Read static markdown files from `/static` directory  |
| `recommend_cards(deck_id)`          | Use LLM to analyze deck balance and propose changes  |
| `summarize_deck(deck_id)`           | Generate archetype summary (curve, ratio, class mix) |

> Note: No direct `fetch_arkhamdb` tool — manual data updates only.

---

### Static Info

Static markdown files under `/static` provide context to the agent:

```
/static/
├── rules_overview.md
├── meta_trends.md
├── owned_sets.md
└── archetype_guides/
    ├── seeker_clue.md
    ├── rogue_money.md
    └── mystic_spell.md
```

---

## 💬 Frontend (React)

### Components

| Component                   | Functionality                                             |
| --------------------------- | --------------------------------------------------------- |
| **Deck Builder View**       | Add/remove cards, sort by cost/type/function              |
| **Deck Search View**        | Browse/search card database                               |
| **Card Detail Pane**        | Show full text, stats, and ownership info                 |
| **Chat Window**             | Conversational interface with AI agent                    |
| **Simulation Report Modal** | Visualize simulation results (draw curves, success rates) |

### Interaction Pattern

1. User edits a deck in **Deck Builder View**.
2. Clicks “Analyze Deck” → triggers `POST /chat`.
3. Backend AI agent:

   * Retrieves deck
   * Runs simulation
   * Summarizes archetype & metrics
   * Returns structured recommendations:

     ```json
     {
       "summary": "Resource curve is slightly top-heavy.",
       "recommendations": [
         {"remove": "Hot Streak", "add": "Lone Wolf"},
         {"remove": "Flashlight", "add": "Sixth Sense"}
       ]
     }
     ```
4. Frontend displays recommended swaps inline, with “Apply” or “Ignore” buttons.

---

## 🧠 Example Flow: Deck Review

```
Frontend → /chat
  ↳ Backend Agent → get_deck()
  ↳ summarize_deck()
  ↳ run_simulation()
  ↳ recommend_cards()
  ↳ Return structured response
```

Deck summary and sim results are cached in Chroma under `SimulationReports` for later viewing.

---

## 🧩 Implementation Plan

### Phase 1 – Core Data + Backend

* [ ] Define Chroma schema (`cards`, `characters`, `decks`)
* [ ] Implement Data Fetching CLI for ArkhamDB pulls
* [ ] Implement CRUD API routes
* [ ] Build basic deck simulation logic
* [ ] Add local `.md` static files

### Phase 2 – AI Agent + Simulation Integration

* [ ] Define agent tools and schemas
* [ ] Implement `recommend_cards` and `summarize_deck`
* [ ] Integrate simulation outputs as context for recommendations

### Phase 3 – Frontend

* [ ] React components for deck builder, search, and chat
* [ ] Local state management + deck storage
* [ ] Visualization of sim results
* [ ] Optional offline cache using `localStorage`

---

## 🧰 Tech Stack Summary

| Layer           | Technology                  | Notes                      |
| --------------- | --------------------------- | -------------------------- |
| **Frontend**    | React + Vite                | Chat + deck builder UI     |
| **Backend**     | FastAPI (Python)            | Serves REST API + AI tools |
| **DB**          | ChromaDB                    | Vector + metadata store    |
| **LLM**         | OpenAI GPT-5 or local model | Used for recommendations   |
| **Data Source** | ArkhamDB API                | Manual import only         |
| **Storage**     | Local (JSON + ChromaDB)     | No remote persistence      |

---

## 📦 Repo Structure (proposed)

```
arkham-assistant/
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── cards.py
│   │   ├── decks.py
│   │   ├── sim.py
│   │   └── chat.py
│   ├── services/
│   │   ├── chroma_client.py
│   │   ├── simulator.py
│   │   ├── arkham_import.py
│   │   └── agent_tools.py
│   └── static/
│       └── *.md
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   └── api/
│   └── public/
├── scripts/
│   └── fetch_arkhamdb.py
├── docs/
│   └── architecture_overview.md
└── README.md
```
