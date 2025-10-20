import { useState, useRef, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import { useDeck } from '../context/DeckContext';
import Button from './common/Button';
import './ChatWindow.css';

export default function ChatWindow({ onOpenSimulation }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const { messages, loading, sendMessage, analyzeDeck, suggestSwaps, runSimulation } = useChat();
  const { activeDeck } = useDeck();

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
      await sendMessage(message, activeDeck?.id);
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

    try {
      switch (action) {
        case 'analyze':
          await analyzeDeck(activeDeck.id);
          break;
        case 'swaps':
          await suggestSwaps(activeDeck.id);
          break;
        case 'simulate':
          await runSimulation(activeDeck.id);
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
  );
}

