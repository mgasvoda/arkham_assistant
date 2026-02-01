import Modal from './common/Modal';
import './SimulationReport.css';

export default function SimulationReport({ isOpen, onClose, simulation }) {
  if (!simulation) return null;

  // Extract simulation data with backend field names
  // Backend returns: n_trials, metrics, key_card_reliability (dict of KeyCardStats), warnings
  const {
    n_trials = 0,
    key_card_reliability = {},
    metrics = {},
    warnings = [],
  } = simulation;

  // Transform key_card_reliability from backend structure
  // Backend: { card_id: { card_id, card_name, probability_in_opening, probability_by_turn_3, avg_turn_drawn } }
  const cardStats = Object.values(key_card_reliability);

  // Build draw curves from avg_turn_drawn values
  const drawCurves = cardStats
    .filter(stats => stats.avg_turn_drawn != null)
    .map(stats => ({
      cardName: stats.card_name,
      avgTurn: stats.avg_turn_drawn,
    }));

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Simulation Report" size="large">
      <div className="simulation-report">
        <div className="sim-summary">
          <div className="sim-stat">
            <span className="stat-label">Trials</span>
            <span className="stat-value">{n_trials.toLocaleString()}</span>
          </div>
          {metrics.avg_resources_turn_1 !== undefined && (
            <div className="sim-stat">
              <span className="stat-label">Avg Resources T1</span>
              <span className="stat-value">{metrics.avg_resources_turn_1.toFixed(1)}</span>
            </div>
          )}
          {metrics.avg_cards_drawn_turn_1 !== undefined && (
            <div className="sim-stat">
              <span className="stat-label">Avg Cards T1</span>
              <span className="stat-value">{metrics.avg_cards_drawn_turn_1.toFixed(1)}</span>
            </div>
          )}
        </div>

        {warnings.length > 0 && (
          <div className="sim-warnings">
            <h3>Warnings</h3>
            <ul>
              {warnings.map((warning, idx) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          </div>
        )}

        {cardStats.length > 0 && (
          <div className="sim-section">
            <h3>Key Card Reliability</h3>
            <p className="section-description">Probability of seeing key cards in opening hand</p>
            <div className="reliability-chart">
              {cardStats.map(stats => (
                <div key={stats.card_id} className="reliability-bar">
                  <span className="card-name">{stats.card_name}</span>
                  <div className="bar-container">
                    <div
                      className="bar-fill opening"
                      style={{
                        width: `${stats.probability_in_opening * 100}%`,
                        background: getReliabilityColor(stats.probability_in_opening),
                      }}
                      title="Opening hand"
                    />
                  </div>
                  <span className="reliability-value">
                    {(stats.probability_in_opening * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {cardStats.length > 0 && (
          <div className="sim-section">
            <h3>By Turn 3</h3>
            <p className="section-description">Probability of drawing key cards by turn 3</p>
            <div className="reliability-chart">
              {cardStats.map(stats => (
                <div key={stats.card_id} className="reliability-bar">
                  <span className="card-name">{stats.card_name}</span>
                  <div className="bar-container">
                    <div
                      className="bar-fill turn3"
                      style={{
                        width: `${stats.probability_by_turn_3 * 100}%`,
                        background: getReliabilityColor(stats.probability_by_turn_3),
                      }}
                      title="By turn 3"
                    />
                  </div>
                  <span className="reliability-value">
                    {(stats.probability_by_turn_3 * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {drawCurves.length > 0 && (
          <div className="sim-section">
            <h3>Average Draw Turn</h3>
            <p className="section-description">Average turn when each key card is first drawn</p>
            <div className="draw-curves">
              {drawCurves.map(({ cardName, avgTurn }) => (
                <div key={cardName} className="draw-curve-item">
                  <span className="card-name">{cardName}</span>
                  <span className="turns-value">Turn {avgTurn.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {Object.keys(metrics).length > 0 && (
          <div className="sim-section">
            <h3>Additional Metrics</h3>
            <div className="metrics-grid">
              {Object.entries(metrics).map(([key, value]) => (
                <div key={key} className="metric-item">
                  <span className="metric-label">{formatMetricLabel(key)}</span>
                  <span className="metric-value">{formatMetricValue(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {cardStats.length === 0 && Object.keys(metrics).length === 0 && (
          <div className="empty-simulation">
            <p>No detailed simulation data available.</p>
            <p>Run a simulation from the chat to see detailed results.</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

function getReliabilityColor(reliability) {
  if (reliability >= 0.8) return '#10b981'; // Green
  if (reliability >= 0.6) return '#f59e0b'; // Orange
  return '#ef4444'; // Red
}

function formatMetricLabel(key) {
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatMetricValue(value) {
  if (typeof value === 'number') {
    return value % 1 === 0 ? value : value.toFixed(2);
  }
  return String(value);
}

