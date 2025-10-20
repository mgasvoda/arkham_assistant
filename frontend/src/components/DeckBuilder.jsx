import { useState, useMemo } from 'react';
import { useDeck } from '../context/DeckContext';
import Button from './common/Button';
import './DeckBuilder.css';

export default function DeckBuilder() {
  const { activeDeck, addCard, removeCard } = useDeck();
  const [sortBy, setSortBy] = useState('cost');

  // Calculate deck statistics
  const stats = useMemo(() => {
    if (!activeDeck?.cards) {
      return {
        totalCards: 0,
        costCurve: {},
        typeDistribution: {},
        classDistribution: {},
      };
    }

    const totalCards = activeDeck.cards.reduce((sum, c) => sum + c.quantity, 0);
    const costCurve = {};
    const typeDistribution = {};
    const classDistribution = {};

    activeDeck.cards.forEach((card) => {
      const cost = card.cost !== undefined ? card.cost : 'X';
      costCurve[cost] = (costCurve[cost] || 0) + card.quantity;

      const type = card.type_name || 'Unknown';
      typeDistribution[type] = (typeDistribution[type] || 0) + card.quantity;

      const className = card.class_name || 'Neutral';
      classDistribution[className] = (classDistribution[className] || 0) + card.quantity;
    });

    return { totalCards, costCurve, typeDistribution, classDistribution };
  }, [activeDeck]);

  // Sort cards
  const sortedCards = useMemo(() => {
    if (!activeDeck?.cards) return [];

    const cards = [...activeDeck.cards];
    switch (sortBy) {
      case 'cost':
        return cards.sort((a, b) => {
          const costA = a.cost !== undefined ? a.cost : 999;
          const costB = b.cost !== undefined ? b.cost : 999;
          return costA - costB;
        });
      case 'type':
        return cards.sort((a, b) => 
          (a.type_name || '').localeCompare(b.type_name || '')
        );
      case 'class':
        return cards.sort((a, b) => 
          (a.class_name || '').localeCompare(b.class_name || '')
        );
      case 'name':
        return cards.sort((a, b) => 
          (a.name || a.real_name || '').localeCompare(b.name || b.real_name || '')
        );
      default:
        return cards;
    }
  }, [activeDeck, sortBy]);

  if (!activeDeck) {
    return (
      <div className="deck-builder">
        <div className="empty-state">
          <h3>No Active Deck</h3>
          <p>Create a new deck or load an existing one to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="deck-builder">
      <div className="deck-header">
        <div>
          <h2>{activeDeck.name || 'Untitled Deck'}</h2>
          {activeDeck.investigator_name && (
            <p className="investigator">{activeDeck.investigator_name}</p>
          )}
        </div>
        <div className="deck-stats-summary">
          <span className="stat-badge">{stats.totalCards} cards</span>
        </div>
      </div>

      <div className="deck-controls">
        <label>
          Sort by:
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="cost">Cost</option>
            <option value="type">Type</option>
            <option value="class">Class</option>
            <option value="name">Name</option>
          </select>
        </label>
      </div>

      <div className="deck-content">
        <div className="deck-list">
          {sortedCards.length === 0 ? (
            <div className="empty-deck">
              <p>No cards in deck. Start searching to add cards!</p>
            </div>
          ) : (
            sortedCards.map((card) => (
              <div key={card.code} className="deck-card">
                <div className="deck-card-info">
                  <span className="deck-card-quantity">×{card.quantity}</span>
                  <span className="deck-card-name">{card.name || card.real_name}</span>
                  {card.cost !== undefined && card.cost !== null && (
                    <span className="deck-card-cost">{card.cost}</span>
                  )}
                </div>
                <div className="deck-card-meta">
                  {card.type_name && (
                    <span className="deck-card-type">{card.type_name}</span>
                  )}
                  {card.class_name && (
                    <span className={`deck-card-class ${card.class_name.toLowerCase()}`}>
                      {card.class_name}
                    </span>
                  )}
                </div>
                <div className="deck-card-actions">
                  <button
                    onClick={() => removeCard(card.code, 1)}
                    className="quantity-btn"
                    title="Remove one"
                  >
                    −
                  </button>
                  <button
                    onClick={() => addCard(card, 1)}
                    className="quantity-btn"
                    title="Add one"
                  >
                    +
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="deck-stats">
          <div className="stat-section">
            <h3>Cost Curve</h3>
            <div className="cost-curve">
              {Object.entries(stats.costCurve).map(([cost, count]) => (
                <div key={cost} className="cost-bar">
                  <span className="cost-label">{cost}</span>
                  <div className="bar-container">
                    <div
                      className="bar-fill"
                      style={{ width: `${(count / stats.totalCards) * 100}%` }}
                    />
                  </div>
                  <span className="cost-count">{count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="stat-section">
            <h3>Type Distribution</h3>
            <div className="distribution">
              {Object.entries(stats.typeDistribution).map(([type, count]) => (
                <div key={type} className="dist-item">
                  <span>{type}</span>
                  <span className="dist-count">{count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="stat-section">
            <h3>Class Distribution</h3>
            <div className="distribution">
              {Object.entries(stats.classDistribution).map(([className, count]) => (
                <div key={className} className="dist-item">
                  <span className={`class-label ${className.toLowerCase()}`}>
                    {className}
                  </span>
                  <span className="dist-count">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

