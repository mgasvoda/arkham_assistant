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
    <div className={`card-detail class-${(card.class_name || 'neutral').toLowerCase()}`}>
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
            {card.cost === null && (
              <span className="meta-badge cost-badge">Cost: —</span>
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
          <h3>Card Information</h3>
          <dl className="detail-list">
            {card.code && (
              <>
                <dt>Card Code</dt>
                <dd>{card.code}</dd>
              </>
            )}
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
          </dl>
        </div>

        {(card.skill_willpower !== undefined || 
          card.skill_intellect !== undefined || 
          card.skill_combat !== undefined || 
          card.skill_agility !== undefined) && (
          <div className="detail-section">
            <h3>Skill Icons</h3>
            <div className="skill-icons">
              {card.skill_willpower !== undefined && card.skill_willpower > 0 && (
                <div className="skill-icon willpower">
                  <span className="icon-label">Willpower</span>
                  <span className="icon-value">×{card.skill_willpower}</span>
                </div>
              )}
              {card.skill_intellect !== undefined && card.skill_intellect > 0 && (
                <div className="skill-icon intellect">
                  <span className="icon-label">Intellect</span>
                  <span className="icon-value">×{card.skill_intellect}</span>
                </div>
              )}
              {card.skill_combat !== undefined && card.skill_combat > 0 && (
                <div className="skill-icon combat">
                  <span className="icon-label">Combat</span>
                  <span className="icon-value">×{card.skill_combat}</span>
                </div>
              )}
              {card.skill_agility !== undefined && card.skill_agility > 0 && (
                <div className="skill-icon agility">
                  <span className="icon-label">Agility</span>
                  <span className="icon-value">×{card.skill_agility}</span>
                </div>
              )}
            </div>
          </div>
        )}

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

