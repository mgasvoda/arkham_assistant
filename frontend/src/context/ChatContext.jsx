import { createContext, useContext, useState } from 'react';
import { api } from '../api/client';

const ChatContext = createContext();

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Send message to AI agent
  // Options: { deckId, investigatorId, investigatorName, scenarioName, upgradeXp }
  const sendMessage = async (message, options = {}) => {
    // Support legacy signature: sendMessage(message, deckId)
    const opts = typeof options === 'string' ? { deckId: options } : options;

    // Add user message to chat
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    setLoading(true);
    setError(null);

    try {
      // Build request payload
      const payload = {
        message,
        deck_id: opts.deckId || null,
        investigator_id: opts.investigatorId || null,
        investigator_name: opts.investigatorName || null,
        scenario_name: opts.scenarioName || null,
        upgrade_xp: opts.upgradeXp ?? null,
      };

      const response = await api.chat.send(payload);

      // Add AI response to chat
      // Backend returns: reply, structured_data, agents_consulted
      const aiMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.reply || 'No response',
        structuredData: response.structured_data || null,
        agentsConsulted: response.agents_consulted || [],
        timestamp: new Date().toISOString(),
      };
      
      setMessages(prev => [...prev, aiMessage]);
      return aiMessage;
    } catch (err) {
      setError(err.message);
      console.error('Failed to send message:', err);
      
      // Add error message to chat
      const errorMessage = {
        id: Date.now() + 1,
        role: 'error',
        content: `Error: ${err.message}. The API may not be available yet.`,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Clear chat history
  const clearMessages = () => {
    setMessages([]);
    setError(null);
  };

  // Quick actions - accept options object for context
  const analyzeDeck = (options = {}) => {
    return sendMessage('Analyze this deck and provide recommendations', options);
  };

  const suggestSwaps = (options = {}) => {
    return sendMessage('Suggest card swaps to improve this deck', options);
  };

  const runSimulation = (options = {}) => {
    return sendMessage('Run a simulation on this deck', options);
  };

  const value = {
    messages,
    loading,
    error,
    sendMessage,
    clearMessages,
    analyzeDeck,
    suggestSwaps,
    runSimulation,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}

