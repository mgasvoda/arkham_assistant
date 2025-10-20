import './Card.css';

export default function Card({ card, onSelect, onAdd, showAddButton = false }) {
  const handleClick = () => {
    if (onSelect) {
      onSelect(card);
    }
  };

  const handleAddClick = (e) => {
    e.stopPropagation();
    if (onAdd) {
      onAdd(card);
    }
  };

  return (
    <div className="card-item" onClick={handleClick}>
      <div className="card-header">
        <div className="card-title">
          <span className="card-name">{card.name || card.real_name}</span>
          {card.cost !== undefined && card.cost !== null && (
            <span className="card-cost">{card.cost}</span>
          )}
        </div>
        {card.class_name && (
          <span className={`card-class ${card.class_name.toLowerCase()}`}>
            {card.class_name}
          </span>
        )}
      </div>

      <div className="card-info">
        {card.type_name && (
          <span className="card-type">{card.type_name}</span>
        )}
        {card.traits && (
          <span className="card-traits">{card.traits}</span>
        )}
      </div>

      {card.text && (
        <div className="card-text">{card.text}</div>
      )}

      <div className="card-footer">
        {card.pack_name && (
          <span className="card-pack">{card.pack_name}</span>
        )}
        {showAddButton && (
          <button
            className="card-add-btn"
            onClick={handleAddClick}
            title="Add to deck"
          >
            +
          </button>
        )}
      </div>
    </div>
  );
}

