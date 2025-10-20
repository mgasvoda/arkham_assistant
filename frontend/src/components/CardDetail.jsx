import { useDeck } from '../context/DeckContext';
import Button from './common/Button';
import './CardDetail.css';

export default function CardDetail({ card, onClose }) {
  const { addCard } = useDeck();

  if (!card) {
    return (
      <div className="card-detail">
        <div className="no-selection">
          <p>Select a card to view details</p>
        </div>
      </div>
    );
  }

  const handleAddCard = () => {
    addCard(card, 1);
  };

  return (
    <div className="card-detail">
      <div className="detail-header">
        <h2>{card.name || card.real_name}</h2>
        {onClose && (
          <button className="close-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        )}
      </div>

      <div className="detail-content">
        <div className="detail-section">
          <div className="detail-meta">
            {card.class_name && (
              <span className={`meta-badge class-badge ${card.class_name.toLowerCase()}`}>
                {card.class_name}
              </span>
            )}
            {card.type_name && (
              <span className="meta-badge type-badge">{card.type_name}</span>
            )}
            {card.cost !== undefined && card.cost !== null && (
              <span className="meta-badge cost-badge">Cost: {card.cost}</span>
            )}
          </div>
        </div>

        {card.traits && (
          <div className="detail-section">
            <h3>Traits</h3>
            <p className="traits">{card.traits}</p>
          </div>
        )}

        {card.text && (
          <div className="detail-section">
            <h3>Card Text</h3>
            <div className="card-text" dangerouslySetInnerHTML={{ __html: card.text }} />
          </div>
        )}

        {card.flavor && (
          <div className="detail-section">
            <div className="flavor-text">{card.flavor}</div>
          </div>
        )}

        <div className="detail-section">
          <h3>Card Details</h3>
          <dl className="detail-list">
            {card.pack_name && (
              <>
                <dt>Pack/Expansion</dt>
                <dd>{card.pack_name}</dd>
              </>
            )}
            {card.position !== undefined && (
              <>
                <dt>Card Number</dt>
                <dd>{card.position}</dd>
              </>
            )}
            {card.quantity !== undefined && (
              <>
                <dt>Deck Limit</dt>
                <dd>{card.quantity}</dd>
              </>
            )}
            {card.skill_willpower !== undefined && (
              <>
                <dt>Willpower</dt>
                <dd>{card.skill_willpower || '-'}</dd>
              </>
            )}
            {card.skill_intellect !== undefined && (
              <>
                <dt>Intellect</dt>
                <dd>{card.skill_intellect || '-'}</dd>
              </>
            )}
            {card.skill_combat !== undefined && (
              <>
                <dt>Combat</dt>
                <dd>{card.skill_combat || '-'}</dd>
              </>
            )}
            {card.skill_agility !== undefined && (
              <>
                <dt>Agility</dt>
                <dd>{card.skill_agility || '-'}</dd>
              </>
            )}
          </dl>
        </div>

        {card.restrictions && (
          <div className="detail-section">
            <h3>Restrictions</h3>
            <p className="restrictions">{card.restrictions}</p>
          </div>
        )}

        <div className="detail-actions">
          <Button onClick={handleAddCard} variant="primary">
            Add to Deck
          </Button>
        </div>
      </div>
    </div>
  );
}

