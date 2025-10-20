# Arkham Assistant Frontend

React + Vite frontend for the Arkham Horror LCG deck building assistant.

## Development

### Installation

```bash
npm install
```

### Running the Development Server

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Building for Production

```bash
npm run build
```

### Testing

Run unit tests:
```bash
npm test
```

Run E2E tests:
```bash
npm run test:e2e
```

Run all tests:
```bash
npm run test:all
```

## Features

### Current Components

- **Deck Builder**: View and edit your deck with statistics and cost curves
- **Card Search**: Search and filter cards from the database
- **Card Detail**: View detailed information about individual cards
- **Chat Window**: Interact with the AI assistant for deck analysis
- **Simulation Report**: View detailed simulation results

### Mock Data

The frontend includes mock data for development purposes. When the backend API is not available, the app will automatically load a sample deck to demonstrate the UI.

## Architecture

- **React 18** with Hooks for component state
- **Context API** for global state management (Deck, Chat)
- **Vite** for fast development and building
- **Native Fetch API** for backend communication
- **CSS Modules** for component styling

## API Integration

The frontend expects the backend API at `http://localhost:8000`. Set the `VITE_API_BASE` environment variable to override this:

```bash
VITE_API_BASE=http://your-api-url npm run dev
```

## File Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── common/          # Reusable components
│   │   ├── DeckBuilder.jsx
│   │   ├── DeckSearch.jsx
│   │   ├── CardDetail.jsx
│   │   ├── ChatWindow.jsx
│   │   └── SimulationReport.jsx
│   ├── context/             # React context providers
│   │   ├── DeckContext.jsx
│   │   └── ChatContext.jsx
│   ├── api/                 # API client
│   │   └── client.js
│   ├── mockData.js          # Mock data for testing
│   ├── App.jsx              # Main app component
│   └── main.jsx             # Entry point
└── tests/                   # Test files
```

