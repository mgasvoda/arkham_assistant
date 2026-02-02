import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api/client';
import { mockDeck } from '../mockData';

const DeckContext = createContext();

/**
 * Enrich a card with full data from the cards API.
 * Maps backend field names to frontend expected names.
 */
async function enrichCard(card) {
  try {
    const fullCard = await api.cards.get(card.code);
    if (!fullCard) {
      return card;
    }

    // Parse traits from JSON string to dot-separated string
    let traits = '';
    if (fullCard.traits) {
      try {
        const traitsArray = JSON.parse(fullCard.traits);
        if (Array.isArray(traitsArray)) {
          traits = traitsArray.join('. ') + '.';
        } else {
          traits = fullCard.traits;
        }
      } catch {
        traits = fullCard.traits;
      }
    }

    return {
      code: card.code,
      name: fullCard.name || card.name,
      real_name: fullCard.name || card.name,
      quantity: card.quantity || 1,
      cost: fullCard.cost,
      type_name: fullCard.type || '',
      class_name: fullCard.class || 'Neutral',
      traits,
      text: fullCard.text || '',
    };
  } catch (err) {
    console.warn(`Failed to enrich card ${card.code}:`, err);
    return card;
  }
}

/**
 * Enrich all cards in a deck with full data.
 */
export async function enrichDeckCards(cards) {
  if (!cards || !Array.isArray(cards)) {
    return [];
  }
  return Promise.all(cards.map(enrichCard));
}

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
      // Enrich cards with full data from cards API
      if (deck.cards && Array.isArray(deck.cards)) {
        deck.cards = await enrichDeckCards(deck.cards);
      }
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
    setActiveDeck,
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

