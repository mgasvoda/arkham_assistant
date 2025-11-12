import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useDeck } from '../context/DeckContext';
import Card from './common/Card';
import Button from './common/Button';
import './DeckSearch.css';

export default function DeckSearch({ collapsed, onCardClick }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    class: '',
    type: '',
    owned: false,
  });
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filtersExpanded, setFiltersExpanded] = useState(true);
  
  const { addCard } = useDeck();

  // Search cards
  const searchCards = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = {
        search: searchTerm || undefined,
        class: filters.class || undefined,
        type: filters.type || undefined,
        owned: filters.owned || undefined,
      };
      
      const results = await api.cards.search(params);
      setCards(results || []);
    } catch (err) {
      setError(err.message);
      console.error('Failed to search cards:', err);
      // Show placeholder data when API isn't available
      setCards([]);
    } finally {
      setLoading(false);
    }
  };

  // Search on filter change
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchTerm || filters.class || filters.type || filters.owned) {
        searchCards();
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchTerm, filters]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleAddCard = (card) => {
    addCard(card, 1);
  };

  const handleDragStart = (e, card) => {
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('application/json', JSON.stringify(card));
  };

  if (collapsed) {
    return (
      <div className="deck-search collapsed">
        <div className="search-collapsed-label">
          <span>Card Search</span>
        </div>
      </div>
    );
  }

  return (
    <div className="deck-search">
      <div className="search-header">
        <h2>Card Search</h2>
      </div>

      <div className="search-controls">
        <input
          type="text"
          className="search-input"
          placeholder="Search by name, traits, or text..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <div className="filters-section">
          <button 
            className="filters-toggle"
            onClick={() => setFiltersExpanded(!filtersExpanded)}
          >
            {filtersExpanded ? '▼' : '▶'} Filters
          </button>
          
          {filtersExpanded && (
            <div className="filters">
              <select
                value={filters.class}
                onChange={(e) => handleFilterChange('class', e.target.value)}
                className="filter-select"
              >
                <option value="">All Classes</option>
                <option value="Guardian">Guardian</option>
                <option value="Seeker">Seeker</option>
                <option value="Rogue">Rogue</option>
                <option value="Mystic">Mystic</option>
                <option value="Survivor">Survivor</option>
                <option value="Neutral">Neutral</option>
              </select>

              <select
                value={filters.type}
                onChange={(e) => handleFilterChange('type', e.target.value)}
                className="filter-select"
              >
                <option value="">All Types</option>
                <option value="Asset">Asset</option>
                <option value="Event">Event</option>
                <option value="Skill">Skill</option>
                <option value="Treachery">Treachery</option>
                <option value="Enemy">Enemy</option>
              </select>

              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={filters.owned}
                  onChange={(e) => handleFilterChange('owned', e.target.checked)}
                />
                Owned Sets Only
              </label>

              <Button
                variant="secondary"
                size="small"
                onClick={() => {
                  setSearchTerm('');
                  setFilters({ class: '', type: '', owned: false });
                  setCards([]);
                }}
              >
                Clear
              </Button>
            </div>
          )}
        </div>
      </div>

      <div className="search-results">
        {loading && (
          <div className="loading-state">
            <p>Searching cards...</p>
          </div>
        )}

        {error && !loading && (
          <div className="error-state">
            <p>API not available yet. Search functionality coming soon!</p>
            <p className="error-detail">{error}</p>
          </div>
        )}

        {!loading && !error && cards.length === 0 && (searchTerm || filters.class || filters.type) && (
          <div className="empty-state">
            <p>No cards found. Try different search criteria.</p>
          </div>
        )}

        {!loading && !error && cards.length === 0 && !searchTerm && !filters.class && !filters.type && (
          <div className="empty-state">
            <p>Enter search criteria to find cards</p>
          </div>
        )}

        {!loading && !error && cards.length > 0 && (
          <div className="card-list">
            {cards.map((card) => (
              <div
                key={card.code}
                className={`search-result-item class-${(card.class_name || 'neutral').toLowerCase()}`}
                draggable
                onDragStart={(e) => handleDragStart(e, card)}
              >
                <div 
                  className="result-info"
                  onClick={() => onCardClick && onCardClick(card)}
                  style={{ cursor: onCardClick ? 'pointer' : 'default' }}
                >
                  <div className="result-header">
                    <span className="result-name">{card.name || card.real_name}</span>
                    {card.cost !== undefined && card.cost !== null && (
                      <span className="result-cost">{card.cost}</span>
                    )}
                  </div>
                  <div className="result-meta">
                    {card.type_name && (
                      <span className="result-type">{card.type_name}</span>
                    )}
                    {card.class_name && (
                      <span className={`result-class ${card.class_name.toLowerCase()}`}>
                        {card.class_name}
                      </span>
                    )}
                  </div>
                  {card.traits && (
                    <div className="result-traits">{card.traits}</div>
                  )}
                </div>
                <button
                  className="result-add-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAddCard(card);
                  }}
                  title="Add to deck"
                >
                  +
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

