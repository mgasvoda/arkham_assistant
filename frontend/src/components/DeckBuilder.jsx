import { useState, useMemo } from 'react';
import { useDeck } from '../context/DeckContext';
import { api } from '../api/client';
import Button from './common/Button';
import InvestigatorPicker from './InvestigatorPicker';
import DeckListModal from './DeckListModal';
import './DeckBuilder.css';

export default function DeckBuilder({ onCardClick }) {
  const {
    activeDeck,
    setActiveDeck,
    selectedInvestigator,
    setSelectedInvestigator,
    addCard,
    removeCard,
    clearDeck,
  } = useDeck();
  const [groupBy, setGroupBy] = useState('cost');
  const [showInvestigatorPicker, setShowInvestigatorPicker] = useState(false);
  const [showDeckList, setShowDeckList] = useState(false);
  const [saving, setSaving] = useState(false);

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

  // Deck management functions
  const handleNewDeck = () => {
    const name = prompt('Enter deck name:', 'New Deck');
    if (name) {
      setActiveDeck({
        id: null, // null ID means it's a new deck
        name,
        investigator_id: selectedInvestigator?.id || null,
        investigator_name: selectedInvestigator?.name || null,
        investigator_faction: selectedInvestigator?.faction || null,
        cards: [],
        archetype: 'balanced',
        notes: '',
      });
    }
  };

  const handleSaveDeck = async () => {
    if (!activeDeck) return;

    // Prompt for name if untitled
    let deckName = activeDeck.name;
    if (!deckName || deckName === 'Untitled Deck') {
      deckName = prompt('Enter deck name:', 'My Deck');
      if (!deckName) return;
    }

    setSaving(true);
    try {
      const deckData = {
        name: deckName,
        investigator_code: activeDeck.investigator_id || selectedInvestigator?.id,
        investigator_name: activeDeck.investigator_name || selectedInvestigator?.name,
        cards: activeDeck.cards.map(c => ({
          code: c.code,
          name: c.name || c.real_name,
          quantity: c.quantity,
          cost: c.cost,
          type_name: c.type_name,
          class_name: c.class_name,
        })),
        archetype: activeDeck.archetype || 'balanced',
        notes: activeDeck.notes || '',
      };

      let savedDeck;
      // Try to update if deck has an ID that looks like it's from the database
      // Skip update for mock IDs (deck_*) and AI-generated IDs (ai-*)
      const isExistingDeck = activeDeck.id &&
        !activeDeck.id.startsWith('ai-') &&
        !activeDeck.id.startsWith('deck_');

      if (isExistingDeck) {
        try {
          // Try to update existing deck
          savedDeck = await api.decks.update(activeDeck.id, deckData);
        } catch (updateErr) {
          // If update fails (deck doesn't exist), create new instead
          console.log('Update failed, creating new deck instead');
          savedDeck = await api.decks.create(deckData);
        }
      } else {
        // Create new deck
        savedDeck = await api.decks.create(deckData);
      }

      setActiveDeck({
        ...activeDeck,
        id: savedDeck.id,
        name: deckName,
      });
      alert('Deck saved successfully!');
    } catch (err) {
      console.error('Failed to save deck:', err);
      alert('Failed to save deck. Make sure the backend is running.');
    } finally {
      setSaving(false);
    }
  };

  const handleLoadDeck = (deck) => {
    // Convert backend deck format to frontend format
    setActiveDeck({
      id: deck.id,
      name: deck.name,
      investigator_id: deck.investigator_code,
      investigator_name: deck.investigator_name,
      investigator_faction: deck.investigator_faction,
      cards: deck.cards || [],
      archetype: deck.archetype,
      notes: deck.notes,
    });
    // Update investigator if deck has one
    if (deck.investigator_name) {
      setSelectedInvestigator({
        id: deck.investigator_code,
        name: deck.investigator_name,
        faction: deck.investigator_faction,
      });
    }
  };

  // Display name - prefer selected investigator, fall back to deck investigator
  const displayInvestigator = selectedInvestigator || (activeDeck?.investigator_name ? {
    name: activeDeck.investigator_name,
    faction: activeDeck.investigator_faction,
  } : null);

  if (!activeDeck) {
    return (
      <div
        className="deck-builder"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <div className="deck-toolbar">
          <Button variant="primary" onClick={handleNewDeck}>
            New Deck
          </Button>
          <Button variant="ghost" onClick={() => setShowDeckList(true)}>
            Load Deck
          </Button>
        </div>
        <div className="empty-state">
          <h3>No Active Deck</h3>
          <p>Create a new deck or load an existing one to get started.</p>
          <div className="investigator-selection">
            {displayInvestigator ? (
              <div className="selected-investigator">
                <span className={`investigator-badge faction-${(displayInvestigator.faction || 'neutral').toLowerCase()}`}>
                  {displayInvestigator.name}
                </span>
                <Button
                  size="small"
                  variant="ghost"
                  onClick={() => setShowInvestigatorPicker(true)}
                >
                  Change
                </Button>
              </div>
            ) : (
              <Button
                variant="secondary"
                onClick={() => setShowInvestigatorPicker(true)}
              >
                Select Investigator
              </Button>
            )}
          </div>
        </div>
        <InvestigatorPicker
          isOpen={showInvestigatorPicker}
          onClose={() => setShowInvestigatorPicker(false)}
        />
        <DeckListModal
          isOpen={showDeckList}
          onClose={() => setShowDeckList(false)}
          onSelect={handleLoadDeck}
        />
      </div>
    );
  }

  return (
    <div
      className="deck-builder"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
      <div className="deck-toolbar">
        <Button variant="ghost" onClick={handleNewDeck}>
          New
        </Button>
        <Button variant="ghost" onClick={() => setShowDeckList(true)}>
          Load
        </Button>
        <Button
          variant="primary"
          onClick={handleSaveDeck}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </div>
      <div className="deck-header">
        <div>
          <h2>{activeDeck.name || 'Untitled Deck'}</h2>
          <div className="investigator-row">
            {displayInvestigator ? (
              <>
                <span className={`investigator-badge faction-${(displayInvestigator.faction || 'neutral').toLowerCase()}`}>
                  {displayInvestigator.name}
                </span>
                <Button
                  size="small"
                  variant="ghost"
                  onClick={() => setShowInvestigatorPicker(true)}
                >
                  Change
                </Button>
              </>
            ) : (
              <Button
                size="small"
                variant="primary"
                onClick={() => setShowInvestigatorPicker(true)}
              >
                Select Investigator
              </Button>
            )}
          </div>
        </div>
        <div className="deck-stats-summary">
          <span className="stat-badge">{stats.totalCards} cards</span>
        </div>
      </div>
      <InvestigatorPicker
        isOpen={showInvestigatorPicker}
        onClose={() => setShowInvestigatorPicker(false)}
      />
      <DeckListModal
        isOpen={showDeckList}
        onClose={() => setShowDeckList(false)}
        onSelect={handleLoadDeck}
      />

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
                      className={`deck-card-tile faction-${(card.class_name || 'neutral').toLowerCase()}`}
                      onClick={() => onCardClick && onCardClick(card)}
                    >
                      <div className="card-tile-image">
                        <img
                          src={`https://arkhamdb.com/bundles/cards/${card.code}.png`}
                          alt={card.name || card.real_name}
                          loading="lazy"
                          onError={(e) => {
                            e.target.style.display = 'none';
                            e.target.nextSibling.style.display = 'flex';
                          }}
                        />
                        <div className="card-tile-placeholder" style={{ display: 'none' }}>
                          <span className="placeholder-icon">🎴</span>
                        </div>
                        <div className="card-tile-quantity">×{card.quantity}</div>
                        {card.cost !== undefined && card.cost !== null && (
                          <div className="card-tile-cost">{card.cost}</div>
                        )}
                      </div>
                      <div className="card-tile-content">
                        <h4 className="card-tile-name">{card.name || card.real_name}</h4>
                        <div className="card-tile-meta">
                          <span className={`card-tile-class faction-${(card.class_name || 'neutral').toLowerCase()}`}>
                            {card.class_name || 'Neutral'}
                          </span>
                          {card.type_name && (
                            <span className="card-tile-type">{card.type_name}</span>
                          )}
                        </div>
                        {card.traits && (
                          <p className="card-tile-traits">{card.traits}</p>
                        )}
                        {card.text && (
                          <p className="card-tile-text" dangerouslySetInnerHTML={{ __html: card.text }} />
                        )}
                      </div>
                      <div className="card-tile-actions">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            removeCard(card.code, 1);
                          }}
                          className="tile-action-btn remove"
                          title="Remove one copy"
                        >
                          −
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            addCard(card, 1);
                          }}
                          className="tile-action-btn add"
                          title="Add one copy"
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

