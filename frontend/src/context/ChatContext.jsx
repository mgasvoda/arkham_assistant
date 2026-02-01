import { createContext, useContext, useState } from 'react';
import { api } from '../api/client';

const ChatContext = createContext();

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Send message to AI agent
  const sendMessage = async (message, deckId = null) => {
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
      const response = await api.chat.send({
        message,
        deck_id: deckId,
      });

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

  // Quick actions
  const analyzeDeck = (deckId) => {
    return sendMessage('Analyze this deck and provide recommendations', deckId);
  };

  const suggestSwaps = (deckId) => {
    return sendMessage('Suggest card swaps to improve this deck', deckId);
  };

  const runSimulation = (deckId) => {
    return sendMessage('Run a simulation on this deck', deckId);
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

