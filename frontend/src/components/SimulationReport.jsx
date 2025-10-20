import Modal from './common/Modal';
import './SimulationReport.css';

export default function SimulationReport({ isOpen, onClose, simulation }) {
  if (!simulation) return null;

  // Extract simulation data
  const {
    iterations = 0,
    avg_turns_to_setup = 0,
    success_rate = 0,
    key_card_reliability = {},
    draw_curves = {},
    metrics = {},
  } = simulation;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Simulation Report" size="large">
      <div className="simulation-report">
        <div className="sim-summary">
          <div className="sim-stat">
            <span className="stat-label">Iterations</span>
            <span className="stat-value">{iterations}</span>
          </div>
          <div className="sim-stat">
            <span className="stat-label">Success Rate</span>
            <span className="stat-value">{(success_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="sim-stat">
            <span className="stat-label">Avg Setup Time</span>
            <span className="stat-value">{avg_turns_to_setup.toFixed(1)} turns</span>
          </div>
        </div>

        {Object.keys(key_card_reliability).length > 0 && (
          <div className="sim-section">
            <h3>Key Card Reliability</h3>
            <div className="reliability-chart">
              {Object.entries(key_card_reliability).map(([card, reliability]) => (
                <div key={card} className="reliability-bar">
                  <span className="card-name">{card}</span>
                  <div className="bar-container">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${reliability * 100}%`,
                        background: getReliabilityColor(reliability),
                      }}
                    />
                  </div>
                  <span className="reliability-value">{(reliability * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {Object.keys(draw_curves).length > 0 && (
          <div className="sim-section">
            <h3>Draw Curves</h3>
            <p className="section-description">Turns until key cards are drawn</p>
            <div className="draw-curves">
              {Object.entries(draw_curves).map(([card, turns]) => (
                <div key={card} className="draw-curve-item">
                  <span className="card-name">{card}</span>
                  <span className="turns-value">Turn {turns.toFixed(1)}</span>
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

        {Object.keys(key_card_reliability).length === 0 &&
          Object.keys(draw_curves).length === 0 &&
          Object.keys(metrics).length === 0 && (
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

