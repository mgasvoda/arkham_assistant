import { useState, useEffect } from 'react';
import { api } from '../api/client';
import Button from './common/Button';
import './DeckListModal.css';

export default function DeckListModal({ isOpen, onClose, onSelect }) {
  const [decks, setDecks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      loadDecks();
    }
  }, [isOpen]);

  const loadDecks = async () => {
    setLoading(true);
    setError(null);
    try {
      const deckList = await api.decks.list();
      setDecks(deckList || []);
    } catch (err) {
      setError('Failed to load decks. Make sure the backend is running.');
      console.error('Failed to load decks:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (deck) => {
    onSelect(deck);
    onClose();
  };

  const handleDelete = async (e, deckId) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this deck?')) {
      return;
    }
    try {
      await api.decks.delete(deckId);
      setDecks(decks.filter(d => d.id !== deckId));
    } catch (err) {
      console.error('Failed to delete deck:', err);
      alert('Failed to delete deck');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content deck-list-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Load Deck</h2>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          {loading && <div className="loading">Loading decks...</div>}

          {error && <div className="error-message">{error}</div>}

          {!loading && !error && decks.length === 0 && (
            <div className="empty-state">
              <p>No saved decks found.</p>
              <p>Create a new deck and save it to see it here.</p>
            </div>
          )}

          {!loading && decks.length > 0 && (
            <div className="deck-list">
              {decks.map(deck => (
                <div
                  key={deck.id}
                  className="deck-list-item"
                  onClick={() => handleSelect(deck)}
                >
                  <div className="deck-info">
                    <div className="deck-name">{deck.name || 'Untitled Deck'}</div>
                    <div className="deck-meta">
                      {deck.investigator_name && (
                        <span className="investigator">{deck.investigator_name}</span>
                      )}
                      {deck.cards && (
                        <span className="card-count">
                          {Array.isArray(deck.cards) ? deck.cards.length : 0} cards
                        </span>
                      )}
                      {deck.archetype && (
                        <span className="archetype">{deck.archetype}</span>
                      )}
                    </div>
                  </div>
                  <div className="deck-actions">
                    <Button
                      size="small"
                      variant="danger"
                      onClick={(e) => handleDelete(e, deck.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </div>
  );
}
