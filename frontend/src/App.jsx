import { useState } from 'react';
import { DeckProvider } from './context/DeckContext';
import { ChatProvider } from './context/ChatContext';
import DeckBuilder from './components/DeckBuilder';
import DeckSearch from './components/DeckSearch';
import ChatWindow from './components/ChatWindow';
import SimulationReport from './components/SimulationReport';
import CardDetail from './components/CardDetail';
import Modal from './components/common/Modal';
import './App.css';

function App() {
  const [showSimulation, setShowSimulation] = useState(false);
  const [simulationData, setSimulationData] = useState(null);
  const [searchPaneCollapsed, setSearchPaneCollapsed] = useState(false);
  const [selectedCard, setSelectedCard] = useState(null);

  const handleOpenSimulation = (data) => {
    setSimulationData(data);
    setShowSimulation(true);
  };

  const handleCloseSimulation = () => {
    setShowSimulation(false);
  };

  const handleCardClick = (card) => {
    setSelectedCard(card);
  };

  const handleCloseCardDetail = () => {
    setSelectedCard(null);
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
          </header>

          <main className="app-main">
            <div className="main-content">
              <div className={`pane search-pane ${searchPaneCollapsed ? 'collapsed' : ''}`}>
                <button 
                  className="collapse-toggle"
                  onClick={() => setSearchPaneCollapsed(!searchPaneCollapsed)}
                  aria-label={searchPaneCollapsed ? "Expand search" : "Collapse search"}
                >
                  {searchPaneCollapsed ? '›' : '‹'}
                </button>
                <DeckSearch collapsed={searchPaneCollapsed} onCardClick={handleCardClick} />
              </div>

              <div className="pane deck-pane">
                <DeckBuilder onCardClick={handleCardClick} />
              </div>
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

          <Modal
            isOpen={!!selectedCard}
            onClose={handleCloseCardDetail}
            title={selectedCard?.name || selectedCard?.real_name || 'Card Details'}
            size="large"
          >
            {selectedCard && <CardDetail card={selectedCard} />}
          </Modal>
        </div>
      </ChatProvider>
    </DeckProvider>
  );
}

export default App;
