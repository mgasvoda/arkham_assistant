import { useState } from 'react';
import { useDeck } from '../context/DeckContext';
import Button from './common/Button';
import './DeckProposal.css';

/**
 * DeckProposal displays an AI-generated deck from a NewDeckResponse.
 * Shows card selections with reasoning, warnings, and accept/modify actions.
 */
export default function DeckProposal({ proposal, onAccept, onClose }) {
  const { setSelectedInvestigator } = useDeck();
  const [expandedCards, setExpandedCards] = useState(new Set());

  if (!proposal) return null;

  const {
    deck_name,
    investigator_id,
    investigator_name,
    cards = [],
    total_cards,
    reasoning,
    archetype,
    warnings = [],
    confidence,
  } = proposal;

  // Group cards by category
  const cardsByCategory = cards.reduce((acc, card) => {
    const category = card.category || 'Other';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(card);
    return acc;
  }, {});

  const toggleCardExpanded = (cardId) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(cardId)) {
        next.delete(cardId);
      } else {
        next.add(cardId);
      }
      return next;
    });
  };

  const handleAccept = () => {
    // Set the investigator from the proposal
    if (investigator_id && investigator_name) {
      setSelectedInvestigator({
        id: investigator_id,
        name: investigator_name,
      });
    }

    // Transform cards to deck format and call onAccept
    const deckCards = cards.map(card => ({
      code: card.card_id,
      name: card.name,
      quantity: card.quantity,
      // Include any other needed fields
    }));

    onAccept({
      name: deck_name,
      investigator_id,
      investigator_name,
      cards: deckCards,
    });
  };

  const getConfidenceColor = (conf) => {
    if (conf >= 0.8) return 'high';
    if (conf >= 0.5) return 'medium';
    return 'low';
  };

  return (
    <div className="deck-proposal">
      <div className="proposal-header">
        <div className="proposal-title">
          <h3>{deck_name || 'AI Generated Deck'}</h3>
          {archetype && <span className="archetype-badge">{archetype}</span>}
        </div>
        <div className="proposal-meta">
          <span className="investigator-name">{investigator_name}</span>
          <span className="card-count">{total_cards} cards</span>
          {confidence !== undefined && (
            <span className={`confidence-badge ${getConfidenceColor(confidence)}`}>
              {Math.round(confidence * 100)}% confidence
            </span>
          )}
        </div>
      </div>

      {warnings.length > 0 && (
        <div className="proposal-warnings">
          <h4>Warnings</h4>
          <ul>
            {warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {reasoning && (
        <div className="proposal-reasoning">
          <h4>Build Strategy</h4>
          <p>{reasoning}</p>
        </div>
      )}

      <div className="proposal-cards">
        <h4>Card Selections</h4>
        {Object.entries(cardsByCategory).map(([category, categoryCards]) => (
          <div key={category} className="card-category">
            <div className="category-header">
              <span className="category-name">{category}</span>
              <span className="category-count">
                {categoryCards.reduce((sum, c) => sum + c.quantity, 0)} cards
              </span>
            </div>
            <div className="category-cards">
              {categoryCards.map(card => (
                <div
                  key={card.card_id}
                  className={`proposal-card ${expandedCards.has(card.card_id) ? 'expanded' : ''}`}
                  onClick={() => toggleCardExpanded(card.card_id)}
                >
                  <div className="card-row">
                    <span className="card-quantity">{card.quantity}x</span>
                    <span className="card-name">{card.name}</span>
                    <span className="expand-icon">
                      {expandedCards.has(card.card_id) ? '-' : '+'}
                    </span>
                  </div>
                  {expandedCards.has(card.card_id) && card.reason && (
                    <div className="card-reason">
                      <em>{card.reason}</em>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="proposal-actions">
        <Button variant="primary" onClick={handleAccept}>
          Accept Deck
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}
