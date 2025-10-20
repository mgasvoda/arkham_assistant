import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api/client';
import { mockDeck } from '../mockData';

const DeckContext = createContext();

export function DeckProvider({ children }) {
  const [activeDeck, setActiveDeck] = useState(null);
  const [selectedInvestigator, setSelectedInvestigator] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load mock deck on mount for testing (when API is not available)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!activeDeck) {
        console.log('Loading mock deck for demo purposes');
        setActiveDeck(mockDeck);
      }
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  // Load deck from API
  const loadDeck = async (deckId) => {
    setLoading(true);
    setError(null);
    try {
      const deck = await api.decks.get(deckId);
      setActiveDeck(deck);
    } catch (err) {
      setError(err.message);
      console.error('Failed to load deck:', err);
    } finally {
      setLoading(false);
    }
  };

  // Create new deck
  const createDeck = async (deckData) => {
    setLoading(true);
    setError(null);
    try {
      const newDeck = await api.decks.create(deckData);
      setActiveDeck(newDeck);
      return newDeck;
    } catch (err) {
      setError(err.message);
      console.error('Failed to create deck:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Update existing deck
  const updateDeck = async (deckId, updates) => {
    setLoading(true);
    setError(null);
    try {
      const updatedDeck = await api.decks.update(deckId, updates);
      setActiveDeck(updatedDeck);
      return updatedDeck;
    } catch (err) {
      setError(err.message);
      console.error('Failed to update deck:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Add card to deck
  const addCard = (card, quantity = 1) => {
    if (!activeDeck) return;
    
    const existingCard = activeDeck.cards.find(c => c.code === card.code);
    let newCards;
    
    if (existingCard) {
      newCards = activeDeck.cards.map(c =>
        c.code === card.code
          ? { ...c, quantity: c.quantity + quantity }
          : c
      );
    } else {
      newCards = [...activeDeck.cards, { ...card, quantity }];
    }
    
    setActiveDeck({ ...activeDeck, cards: newCards });
  };

  // Remove card from deck
  const removeCard = (cardCode, quantity = 1) => {
    if (!activeDeck) return;
    
    const newCards = activeDeck.cards
      .map(c =>
        c.code === cardCode
          ? { ...c, quantity: c.quantity - quantity }
          : c
      )
      .filter(c => c.quantity > 0);
    
    setActiveDeck({ ...activeDeck, cards: newCards });
  };

  // Clear active deck
  const clearDeck = () => {
    setActiveDeck(null);
    setSelectedInvestigator(null);
  };

  const value = {
    activeDeck,
    selectedInvestigator,
    loading,
    error,
    loadDeck,
    createDeck,
    updateDeck,
    addCard,
    removeCard,
    clearDeck,
    setSelectedInvestigator,
  };

  return <DeckContext.Provider value={value}>{children}</DeckContext.Provider>;
}

export function useDeck() {
  const context = useContext(DeckContext);
  if (!context) {
    throw new Error('useDeck must be used within a DeckProvider');
  }
  return context;
}

