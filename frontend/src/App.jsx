import { useState } from 'react';
import { DeckProvider } from './context/DeckContext';
import { ChatProvider } from './context/ChatContext';
import DeckBuilder from './components/DeckBuilder';
import DeckSearch from './components/DeckSearch';
import CardDetail from './components/CardDetail';
import ChatWindow from './components/ChatWindow';
import SimulationReport from './components/SimulationReport';
import Button from './components/common/Button';
import './App.css';

function App() {
  const [selectedCard, setSelectedCard] = useState(null);
  const [showSimulation, setShowSimulation] = useState(false);
  const [simulationData, setSimulationData] = useState(null);
  const [activeView, setActiveView] = useState('builder'); // 'builder' or 'search'

  const handleOpenSimulation = (data) => {
    setSimulationData(data);
    setShowSimulation(true);
  };

  const handleCloseSimulation = () => {
    setShowSimulation(false);
  };

  return (
    <DeckProvider>
      <ChatProvider>
        <div className="App" data-testid="app">
          <header className="app-header">
            <div className="header-content">
              <h1>🃏 Arkham Assistant</h1>
              <p>AI-powered deckbuilding for Arkham Horror LCG</p>
            </div>
            <div className="header-actions">
              <Button
                variant={activeView === 'builder' ? 'primary' : 'ghost'}
                size="small"
                onClick={() => setActiveView('builder')}
              >
                Deck Builder
              </Button>
              <Button
                variant={activeView === 'search' ? 'primary' : 'ghost'}
                size="small"
                onClick={() => setActiveView('search')}
              >
                Card Search
              </Button>
            </div>
          </header>

          <main className="app-main">
            <div className="main-content">
              {activeView === 'builder' ? (
                <div className="pane deck-pane">
                  <DeckBuilder />
                </div>
              ) : (
                <div className="pane search-pane">
                  <DeckSearch onCardSelect={setSelectedCard} />
                </div>
              )}

              {selectedCard && activeView === 'search' && (
                <div className="pane detail-pane">
                  <CardDetail card={selectedCard} onClose={() => setSelectedCard(null)} />
                </div>
              )}
            </div>

            <div className="sidebar">
              <div className="pane chat-pane">
                <ChatWindow onOpenSimulation={handleOpenSimulation} />
              </div>
            </div>
          </main>

          <SimulationReport
            isOpen={showSimulation}
            onClose={handleCloseSimulation}
            simulation={simulationData}
          />
        </div>
      </ChatProvider>
    </DeckProvider>
  );
}

export default App;
