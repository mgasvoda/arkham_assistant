import { useState, useRef, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import { useDeck } from '../context/DeckContext';
import Button from './common/Button';
import DeckProposal from './DeckProposal';
import './ChatWindow.css';

// Common Arkham Horror scenarios for autocomplete
const COMMON_SCENARIOS = [
  'The Gathering',
  'The Midnight Masks',
  'The Devourer Below',
  'Extracurricular Activity',
  'The House Always Wins',
  'The Miskatonic Museum',
  'The Essex County Express',
  'Blood on the Altar',
  'Undimensioned and Unseen',
  'Where Doom Awaits',
  'Lost in Time and Space',
  'Curtain Call',
  'The Last King',
  'Echoes of the Past',
  'The Unspeakable Oath',
  'A Phantom of Truth',
  'The Pallid Mask',
  'Black Stars Rise',
  'Dim Carcosa',
  'The Untamed Wilds',
  'The Doom of Eztli',
  'Threads of Fate',
  'The Boundary Beyond',
  'Heart of the Elders',
  'The City of Archives',
  'The Depths of Yoth',
  'Shattered Aeons',
  'Disappearance at the Twilight Estate',
  'The Witching Hour',
  'At Death\'s Doorstep',
  'The Secret Name',
  'The Wages of Sin',
  'For the Greater Good',
  'Union and Disillusion',
  'In the Clutches of Chaos',
  'Before the Black Throne',
];

export default function ChatWindow({ onOpenSimulation }) {
  const [input, setInput] = useState('');
  const [upgradeXp, setUpgradeXp] = useState('');
  const [scenarioName, setScenarioName] = useState('');
  const [showScenarioSuggestions, setShowScenarioSuggestions] = useState(false);
  const [dismissedProposals, setDismissedProposals] = useState(new Set());
  const messagesEndRef = useRef(null);
  const scenarioInputRef = useRef(null);
  const { messages, loading, sendMessage, analyzeDeck, suggestSwaps, runSimulation } = useChat();
  const { activeDeck, selectedInvestigator, setActiveDeck, setSelectedInvestigator } = useDeck();

  // Filter scenarios based on input
  const filteredScenarios = scenarioName
    ? COMMON_SCENARIOS.filter(s =>
        s.toLowerCase().includes(scenarioName.toLowerCase())
      ).slice(0, 5)
    : [];

  // Build context options for API requests
  const buildContextOptions = () => {
    // Extract card IDs from active deck if available
    let deckCards = null;
    if (activeDeck?.cards && Array.isArray(activeDeck.cards)) {
      // Convert cards array to dict format: { card_id: count }
      deckCards = {};
      activeDeck.cards.forEach(card => {
        const cardId = card.card_id || card.id || card.code;
        const count = card.count || card.quantity || 1;
        if (cardId) {
          deckCards[cardId] = (deckCards[cardId] || 0) + count;
        }
      });
    }

    return {
      deckId: activeDeck?.id,
      deckCards,
      investigatorId: selectedInvestigator?.id || activeDeck?.investigator_id,
      investigatorName: selectedInvestigator?.name || activeDeck?.investigator_name,
      upgradeXp: upgradeXp ? parseInt(upgradeXp, 10) : null,
      scenarioName: scenarioName || null,
    };
  };

  // Handle scenario selection from suggestions
  const handleSelectScenario = (scenario) => {
    setScenarioName(scenario);
    setShowScenarioSuggestions(false);
  };

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (scenarioInputRef.current && !scenarioInputRef.current.contains(e.target)) {
        setShowScenarioSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Helper to detect if structuredData contains a NewDeckResponse
  const isNewDeckResponse = (structuredData) => {
    return structuredData &&
      Array.isArray(structuredData.cards) &&
      structuredData.cards.length > 0 &&
      structuredData.cards[0]?.card_id;
  };

  // Handle accepting a proposed deck
  const handleAcceptDeck = (deckData) => {
    // Create a new active deck from the proposal
    setActiveDeck({
      id: `ai-${Date.now()}`,
      name: deckData.name,
      investigator_id: deckData.investigator_id,
      investigator_name: deckData.investigator_name,
      cards: deckData.cards,
    });
  };

  // Handle dismissing a proposal
  const handleDismissProposal = (messageId) => {
    setDismissedProposals(prev => new Set([...prev, messageId]));
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const message = input.trim();
    setInput('');

    try {
      await sendMessage(message, buildContextOptions());
    } catch (err) {
      // Error is handled in context
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickAction = async (action) => {
    if (!activeDeck) {
      alert('Please create or load a deck first');
      return;
    }

    const options = buildContextOptions();

    try {
      switch (action) {
        case 'analyze':
          await analyzeDeck(options);
          break;
        case 'swaps':
          await suggestSwaps(options);
          break;
        case 'simulate':
          await runSimulation(options);
          break;
      }
    } catch (err) {
      // Error is handled in context
    }
  };

  return (
    <div className="chat-window">
      <div className="chat-header">
        <h2>AI Assistant</h2>
      </div>

      <div className="quick-actions">
        <Button
          size="small"
          variant="ghost"
          onClick={() => handleQuickAction('analyze')}
          disabled={!activeDeck || loading}
        >
          Analyze Deck
        </Button>
        <Button
          size="small"
          variant="ghost"
          onClick={() => handleQuickAction('swaps')}
          disabled={!activeDeck || loading}
        >
          Suggest Swaps
        </Button>
        <Button
          size="small"
          variant="ghost"
          onClick={() => handleQuickAction('simulate')}
          disabled={!activeDeck || loading}
        >
          Run Simulation
        </Button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-chat">
            <p>👋 Hi! I'm your Arkham Horror deck building assistant.</p>
            <p>Ask me anything about your deck, card interactions, or get recommendations!</p>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`message message-${message.role}`}>
            <div className="message-content">
              {message.content}
            </div>

            {/* Show DeckProposal for NewDeckResponse structured data */}
            {message.structuredData &&
              isNewDeckResponse(message.structuredData) &&
              !dismissedProposals.has(message.id) && (
              <DeckProposal
                proposal={message.structuredData}
                onAccept={handleAcceptDeck}
                onClose={() => handleDismissProposal(message.id)}
              />
            )}

            {message.recommendations && message.recommendations.length > 0 && (
              <div className="recommendations">
                <h4>Recommendations:</h4>
                {message.recommendations.map((rec, idx) => (
                  <div key={idx} className="recommendation-card">
                    <div className="rec-text">
                      <strong>Remove:</strong> {rec.remove}<br />
                      <strong>Add:</strong> {rec.add}<br />
                      <span className="rec-reason">{rec.reason}</span>
                    </div>
                    <div className="rec-actions">
                      <Button size="small" variant="success">Apply</Button>
                      <Button size="small" variant="ghost">Ignore</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {message.simulation && onOpenSimulation && (
              <div className="simulation-link">
                <Button
                  size="small"
                  variant="primary"
                  onClick={() => onOpenSimulation(message.simulation)}
                >
                  View Simulation Report
                </Button>
              </div>
            )}

            {/* Show recommendation from structured data if present */}
            {message.structuredData?.recommendation && (
              <div className="structured-recommendation">
                <span className="rec-label">Recommendation:</span>
                {message.structuredData.recommendation}
              </div>
            )}

            {/* Show confidence indicator if present */}
            {message.structuredData?.confidence !== undefined && (
              <div className="confidence-indicator">
                <span className="confidence-label">Confidence:</span>
                <div className="confidence-bar">
                  <div
                    className="confidence-fill"
                    style={{ width: `${message.structuredData.confidence * 100}%` }}
                  />
                </div>
                <span className="confidence-value">
                  {Math.round(message.structuredData.confidence * 100)}%
                </span>
              </div>
            )}

            {/* Show agents consulted */}
            {message.agentsConsulted && message.agentsConsulted.length > 0 && (
              <div className="agents-consulted">
                <span className="agents-label">Consulted:</span>
                {message.agentsConsulted.map(agent => (
                  <span key={agent} className={`agent-badge agent-${agent.toLowerCase().replace('agent', '')}`}>
                    {agent.replace('Agent', '')}
                  </span>
                ))}
              </div>
            )}

            <div className="message-time">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message message-assistant">
            <div className="message-content loading">
              <span className="loading-dots">Thinking</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        {activeDeck && (
          <div className="context-inputs">
            <div className="context-row">
              <label className="context-label">
                Available XP:
                <input
                  type="number"
                  className="xp-input"
                  min="0"
                  max="50"
                  value={upgradeXp}
                  onChange={(e) => setUpgradeXp(e.target.value)}
                  placeholder="0"
                  disabled={loading}
                />
              </label>
              <div className="scenario-input-wrapper" ref={scenarioInputRef}>
                <label className="context-label">
                  Scenario:
                  <input
                    type="text"
                    className="scenario-input"
                    value={scenarioName}
                    onChange={(e) => {
                      setScenarioName(e.target.value);
                      setShowScenarioSuggestions(true);
                    }}
                    onFocus={() => setShowScenarioSuggestions(true)}
                    placeholder="e.g., The Gathering"
                    disabled={loading}
                  />
                </label>
                {showScenarioSuggestions && filteredScenarios.length > 0 && (
                  <ul className="scenario-suggestions">
                    {filteredScenarios.map(scenario => (
                      <li
                        key={scenario}
                        onClick={() => handleSelectScenario(scenario)}
                      >
                        {scenario}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <span className="context-hint">Set context for scenario-specific advice</span>
          </div>
        )}
        <div className="input-row">
          <textarea
            className="chat-input"
            placeholder="Ask about your deck or request analysis..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={loading}
            rows={2}
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            variant="primary"
          >
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}

