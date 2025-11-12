import { useState, useMemo } from 'react';
import { useDeck } from '../context/DeckContext';
import Button from './common/Button';
import './DeckBuilder.css';

export default function DeckBuilder({ onCardClick }) {
  const { activeDeck, addCard, removeCard } = useDeck();
  const [groupBy, setGroupBy] = useState('cost');

  // Helper function to determine slot/function category
  const determineSlot = (card) => {
    const traits = (card.traits || '').toLowerCase();
    const text = (card.text || '').toLowerCase();
    const type = (card.type_name || '').toLowerCase();

    if (type === 'event') return 'Events';
    if (type === 'skill') return 'Skills';
    
    // Assets by slot
    if (traits.includes('weapon') || text.includes('hand slot')) return 'Weapons';
    if (traits.includes('ally') || text.includes('ally slot')) return 'Allies';
    if (traits.includes('tool') || traits.includes('item')) return 'Tools/Items';
    if (traits.includes('talent') || text.includes('talent')) return 'Talents';
    if (traits.includes('spell')) return 'Spells';
    if (text.includes('body slot')) return 'Body';
    if (text.includes('accessory slot')) return 'Accessories';
    
    return 'Other Assets';
  };

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

  // Group cards dynamically based on selected grouping
  const groupedCards = useMemo(() => {
    if (!activeDeck?.cards) return {};

    const cards = [...activeDeck.cards];
    const groups = {};

    cards.forEach((card) => {
      let key;
      switch (groupBy) {
        case 'cost':
          key = card.cost !== undefined && card.cost !== null ? `Cost ${card.cost}` : 'Cost X';
          break;
        case 'type':
          key = card.type_name || 'Unknown Type';
          break;
        case 'class':
          key = card.class_name || 'Neutral';
          break;
        case 'slot':
          // Determine slot from traits or card text
          key = determineSlot(card);
          break;
        default:
          key = 'All Cards';
      }

      if (!groups[key]) {
        groups[key] = [];
      }
      groups[key].push(card);
    });

    // Sort groups and cards within groups
    const sortedGroups = {};
    Object.keys(groups).sort((a, b) => {
      if (groupBy === 'cost') {
        const costA = a === 'Cost X' ? 999 : parseInt(a.replace('Cost ', ''));
        const costB = b === 'Cost X' ? 999 : parseInt(b.replace('Cost ', ''));
        return costA - costB;
      }
      return a.localeCompare(b);
    }).forEach(key => {
      sortedGroups[key] = groups[key].sort((a, b) => 
        (a.name || a.real_name || '').localeCompare(b.name || b.real_name || '')
      );
    });

    return sortedGroups;
  }, [activeDeck, groupBy]);

  const handleDrop = (e) => {
    e.preventDefault();
    try {
      const cardData = e.dataTransfer.getData('application/json');
      if (cardData) {
        const card = JSON.parse(cardData);
        addCard(card, 1);
      }
    } catch (error) {
      console.error('Failed to add card from drag:', error);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  if (!activeDeck) {
    return (
      <div 
        className="deck-builder"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <div className="empty-state">
          <h3>No Active Deck</h3>
          <p>Create a new deck or load an existing one to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="deck-builder"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
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
          Group by:
          <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="cost">Cost</option>
            <option value="type">Type</option>
            <option value="class">Class</option>
            <option value="slot">Slot/Function</option>
          </select>
        </label>
      </div>

      <div className="deck-content">
        <div className="deck-grid">
          {Object.keys(groupedCards).length === 0 ? (
            <div className="empty-deck">
              <p>No cards in deck. Drag cards from the search pane to add them!</p>
            </div>
          ) : (
            Object.entries(groupedCards).map(([groupName, cards]) => (
              <div key={groupName} className="card-group">
                <div className="group-header">
                  <h3>{groupName}</h3>
                  <span className="group-count">
                    {cards.reduce((sum, c) => sum + c.quantity, 0)} cards
                  </span>
                </div>
                <div className="group-cards">
                  {cards.map((card) => (
                    <div 
                      key={card.code} 
                      className={`deck-card-item class-${(card.class_name || 'neutral').toLowerCase()}`}
                    >
                      <div 
                        className="card-visual"
                        onClick={() => onCardClick && onCardClick(card)}
                        style={{ cursor: onCardClick ? 'pointer' : 'default' }}
                      >
                        <div className="card-visual-header">
                          <span className="card-visual-name">{card.name || card.real_name}</span>
                          {card.cost !== undefined && card.cost !== null && (
                            <span className="card-visual-cost">{card.cost}</span>
                          )}
                        </div>
                        {card.class_name && (
                          <span className={`card-visual-class ${card.class_name.toLowerCase()}`}>
                            {card.class_name}
                          </span>
                        )}
                        <div className="card-visual-quantity">×{card.quantity}</div>
                      </div>
                      <div className="card-actions">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            removeCard(card.code, 1);
                          }}
                          className="action-btn remove"
                          title="Remove one"
                        >
                          −
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            addCard(card, 1);
                          }}
                          className="action-btn add"
                          title="Add one"
                        >
                          +
                        </button>
                      </div>
                    </div>
                  ))}
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

