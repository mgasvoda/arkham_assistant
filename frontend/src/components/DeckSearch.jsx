import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useDeck } from '../context/DeckContext';
import Card from './common/Card';
import Button from './common/Button';
import './DeckSearch.css';

export default function DeckSearch({ onCardSelect }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    class: '',
    type: '',
    owned: false,
  });
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
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
          <div className="card-grid">
            {cards.map((card) => (
              <Card
                key={card.code}
                card={card}
                onSelect={onCardSelect}
                onAdd={handleAddCard}
                showAddButton={true}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

