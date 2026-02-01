import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useDeck } from '../context/DeckContext';
import Modal from './common/Modal';
import Button from './common/Button';
import './InvestigatorPicker.css';

export default function InvestigatorPicker({ isOpen, onClose }) {
  const [investigators, setInvestigators] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedClass, setSelectedClass] = useState('all');
  const { selectedInvestigator, setSelectedInvestigator } = useDeck();

  // Fetch investigators on mount
  useEffect(() => {
    if (isOpen && investigators.length === 0) {
      fetchInvestigators();
    }
  }, [isOpen]);

  const fetchInvestigators = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.characters.list();
      setInvestigators(data.investigators || data || []);
    } catch (err) {
      setError(err.message);
      console.error('Failed to fetch investigators:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (investigator) => {
    setSelectedInvestigator({
      id: investigator.code || investigator.id,
      name: investigator.name || investigator.real_name,
      faction: investigator.faction_name || investigator.faction,
      health: investigator.health,
      sanity: investigator.sanity,
    });
    onClose();
  };

  // Get unique factions for filter
  const factions = [...new Set(investigators.map(inv => inv.faction_name || inv.faction))].filter(Boolean);

  // Filter investigators
  const filteredInvestigators = investigators.filter(inv => {
    const name = (inv.name || inv.real_name || '').toLowerCase();
    const matchesSearch = name.includes(searchTerm.toLowerCase());
    const matchesClass = selectedClass === 'all' ||
      (inv.faction_name || inv.faction) === selectedClass;
    return matchesSearch && matchesClass;
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Select Investigator" size="large">
      <div className="investigator-picker">
        <div className="picker-controls">
          <input
            type="text"
            className="search-input"
            placeholder="Search investigators..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <select
            className="faction-filter"
            value={selectedClass}
            onChange={(e) => setSelectedClass(e.target.value)}
          >
            <option value="all">All Factions</option>
            {factions.map(faction => (
              <option key={faction} value={faction}>{faction}</option>
            ))}
          </select>
        </div>

        {loading && (
          <div className="picker-loading">Loading investigators...</div>
        )}

        {error && (
          <div className="picker-error">
            <p>Failed to load investigators: {error}</p>
            <Button onClick={fetchInvestigators} variant="primary" size="small">
              Retry
            </Button>
          </div>
        )}

        {!loading && !error && (
          <div className="investigators-grid">
            {filteredInvestigators.length === 0 ? (
              <div className="no-results">No investigators found</div>
            ) : (
              filteredInvestigators.map(investigator => (
                <div
                  key={investigator.code || investigator.id}
                  className={`investigator-card ${
                    selectedInvestigator?.id === (investigator.code || investigator.id)
                      ? 'selected'
                      : ''
                  } faction-${(investigator.faction_name || investigator.faction || 'neutral').toLowerCase()}`}
                  onClick={() => handleSelect(investigator)}
                >
                  <div className="investigator-name">
                    {investigator.name || investigator.real_name}
                  </div>
                  <div className="investigator-faction">
                    {investigator.faction_name || investigator.faction}
                  </div>
                  <div className="investigator-stats">
                    <span className="stat health">Health: {investigator.health}</span>
                    <span className="stat sanity">Sanity: {investigator.sanity}</span>
                  </div>
                  {investigator.deck_requirements && (
                    <div className="investigator-decksize">
                      Deck Size: {investigator.deck_requirements.size || 30}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
