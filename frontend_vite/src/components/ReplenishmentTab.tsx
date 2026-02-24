import React, { useState } from "react";
import "./ReplenishmentTab.css";

function ReplenishmentTab({
  selectedSku,
  repSettings,
  repRecommendation,
  repLoading,
  repError,
  repMessage,
  repForm,
  onRepFormChange,
  onRepSettingsSubmit,
  onRefresh,
}) {
  const [editOpen, setEditOpen] = useState(false);

  const getUrgencyClass = (urgency) => {
    if (!urgency) return "";
    const u = urgency.toLowerCase();
    if (u === "critical" || u === "high") return "urgency-high";
    if (u === "medium") return "urgency-medium";
    return "urgency-low";
  };

  const getUrgencyIcon = (urgency) => {
    if (!urgency) return "●";
    const u = urgency.toLowerCase();
    if (u === "critical" || u === "high") return "▲";
    if (u === "medium") return "◆";
    return "●";
  };

  const handleFieldChange = (field, min) => (e) => {
    onRepFormChange({
      ...repForm,
      [field]: Math.max(min, parseInt(e.target.value) || min),
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onRepSettingsSubmit(e);
  };

  return (
    <div className="rep-container">
      {/* Title bar */}
      <div className="rep-title-bar">
        <div>
          <h2 className="rep-title">Replenishment Planning</h2>
          <p className="rep-subtitle">
            Automated reorder recommendations for{" "}
            <strong>{selectedSku}</strong>
          </p>
        </div>
        <button
          className="rep-refresh-btn"
          onClick={onRefresh}
          disabled={repLoading}
        >
          {repLoading ? "Refreshing\u2026" : "Refresh"}
        </button>
      </div>

      {repLoading && !repRecommendation && (
        <p className="loading">Loading&hellip;</p>
      )}
      {repError && <div className="alert alert-error">{repError}</div>}

      {/* ── Recommendation summary cards ── */}
      {repRecommendation && (
        <div className="rep-summary-cards">
          <div
            className={`rep-summary-card ${repRecommendation.reorder_needed ? "rep-card-alert" : "rep-card-ok"
              }`}
          >
            <span className="rep-card-icon">
              {repRecommendation.reorder_needed ? "⚠" : "✓"}
            </span>
            <span className="rep-card-label">Reorder Needed</span>
            <span className="rep-card-value">
              {repRecommendation.reorder_needed ? "Yes" : "No"}
            </span>
          </div>

          <div className="rep-summary-card">
            <span className="rep-card-icon">📦</span>
            <span className="rep-card-label">Order Quantity</span>
            <span className="rep-card-value">
              {repRecommendation.order_quantity} units
            </span>
          </div>

          <div
            className={`rep-summary-card ${getUrgencyClass(
              repRecommendation.urgency
            )}`}
          >
            <span className="rep-card-icon">
              {getUrgencyIcon(repRecommendation.urgency)}
            </span>
            <span className="rep-card-label">Urgency</span>
            <span className="rep-card-value rep-urgency-value">
              {repRecommendation.urgency || "N/A"}
            </span>
          </div>

          <div className="rep-summary-card">
            <span className="rep-card-icon">📊</span>
            <span className="rep-card-label">Projected Stock</span>
            <span className="rep-card-value">
              {repRecommendation.projected_stock_at_lead_time} units
            </span>
          </div>
        </div>
      )}

      {/* ── Timeline card ── */}
      {repRecommendation && (
        <div className="rep-timeline-card">
          <h3 className="rep-section-heading">Order Timeline</h3>
          <div className="rep-timeline-row">
            <div className="rep-timeline-step">
              <div className="rep-timeline-dot dot-order" />
              <div className="rep-timeline-info">
                <span className="rep-timeline-label">Order By</span>
                <span className="rep-timeline-date">
                  {repRecommendation.suggested_order_date || "—"}
                </span>
              </div>
            </div>

            <div className="rep-timeline-connector" />

            <div className="rep-timeline-step">
              <div className="rep-timeline-dot dot-transit" />
              <div className="rep-timeline-info">
                <span className="rep-timeline-label">Lead Time Demand</span>
                <span className="rep-timeline-date">
                  {repRecommendation.demand_during_lead_time} units
                </span>
              </div>
            </div>

            <div className="rep-timeline-connector" />

            <div className="rep-timeline-step">
              <div className="rep-timeline-dot dot-arrival" />
              <div className="rep-timeline-info">
                <span className="rep-timeline-label">Expected Arrival</span>
                <span className="rep-timeline-date">
                  {repRecommendation.expected_arrival_date || "—"}
                </span>
              </div>
            </div>
          </div>

          {repRecommendation.message && (
            <div className="rep-message-banner">
              {repRecommendation.message}
            </div>
          )}
        </div>
      )}

      {/* ── Bottom two-column layout ── */}
      <div className="rep-columns">
        {/* Current Settings */}
        <div className="rep-panel">
          <div className="rep-panel-header">
            <h3 className="rep-section-heading">Current Settings</h3>
            <button
              className="rep-edit-toggle"
              type="button"
              onClick={() => setEditOpen((v) => !v)}
            >
              {editOpen ? "Cancel" : "Edit"}
            </button>
          </div>

          {repSettings ? (
            <div className="rep-settings-grid">
              {[
                { label: "Lead Time", value: `${repSettings.lead_time_days} days`, icon: "⏱" },
                { label: "Min Order Qty", value: `${repSettings.min_order_qty} units`, icon: "📋" },
                { label: "Reorder Point", value: `${repSettings.reorder_point} units`, icon: "🔻" },
                { label: "Safety Stock", value: `${repSettings.safety_stock} units`, icon: "🛡" },
                { label: "Target Stock", value: `${repSettings.target_stock_level} units`, icon: "🎯" },
              ].map((item) => (
                <div className="rep-setting-item" key={item.label}>
                  <span className="rep-setting-icon">{item.icon}</span>
                  <div className="rep-setting-text">
                    <span className="rep-setting-label">{item.label}</span>
                    <span className="rep-setting-value">{item.value}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="rep-empty">No settings available.</p>
          )}

          {/* Edit form (collapsible) */}
          {editOpen && (
            <form onSubmit={handleSubmit} className="rep-edit-form">
              <div className="rep-form-grid">
                <div className="form-group">
                  <label>Lead Time (days)</label>
                  <input
                    type="number"
                    min="1"
                    value={repForm.lead_time_days}
                    onChange={handleFieldChange("lead_time_days", 1)}
                  />
                </div>
                <div className="form-group">
                  <label>Min Order Qty</label>
                  <input
                    type="number"
                    min="1"
                    value={repForm.min_order_qty}
                    onChange={handleFieldChange("min_order_qty", 1)}
                  />
                </div>
                <div className="form-group">
                  <label>Reorder Point</label>
                  <input
                    type="number"
                    min="0"
                    value={repForm.reorder_point}
                    onChange={handleFieldChange("reorder_point", 0)}
                  />
                </div>
                <div className="form-group">
                  <label>Safety Stock</label>
                  <input
                    type="number"
                    min="0"
                    value={repForm.safety_stock}
                    onChange={handleFieldChange("safety_stock", 0)}
                  />
                </div>
                <div className="form-group">
                  <label>Target Stock Level</label>
                  <input
                    type="number"
                    min="0"
                    value={repForm.target_stock_level}
                    onChange={handleFieldChange("target_stock_level", 0)}
                  />
                </div>
              </div>

              {repMessage && (
                <div className="alert alert-success">{repMessage}</div>
              )}

              <button type="submit" className="btn-submit">
                Save Settings
              </button>
            </form>
          )}
        </div>

        {/* Stock Level Gauge */}
        {repSettings && repRecommendation && (
          <div className="rep-panel">
            <h3 className="rep-section-heading">Stock Level Overview</h3>
            <StockGauge
              projected={repRecommendation.projected_stock_at_lead_time}
              safetyStock={repSettings.safety_stock}
              reorderPoint={repSettings.reorder_point}
              target={repSettings.target_stock_level}
            />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Mini stock gauge visualisation ── */
function StockGauge({ projected, safetyStock, reorderPoint, target }) {
  const max = Math.max(target, projected, reorderPoint, safetyStock) * 1.2 || 1;
  const pct = (v) => Math.min(100, Math.max(0, (v / max) * 100));

  const projectedPct = pct(projected);
  const reorderPct = pct(reorderPoint);
  const safetyPct = pct(safetyStock);
  const targetPct = pct(target);

  const barColor =
    projected <= safetyStock
      ? "#dc2626"
      : projected <= reorderPoint
        ? "#f59e0b"
        : "#16a34a";

  return (
    <div className="stock-gauge">
      <div className="gauge-bar-bg">
        <div
          className="gauge-bar-fill"
          style={{ width: `${projectedPct}%`, background: barColor }}
        />
        {/* Markers */}
        <div
          className="gauge-marker marker-safety"
          style={{ left: `${safetyPct}%` }}
          title={`Safety Stock: ${safetyStock}`}
        >
          <span className="gauge-marker-label">Safety</span>
        </div>
        <div
          className="gauge-marker marker-reorder"
          style={{ left: `${reorderPct}%` }}
          title={`Reorder Point: ${reorderPoint}`}
        >
          <span className="gauge-marker-label">Reorder</span>
        </div>
        <div
          className="gauge-marker marker-target"
          style={{ left: `${targetPct}%` }}
          title={`Target: ${target}`}
        >
          <span className="gauge-marker-label">Target</span>
        </div>
      </div>

      <div className="gauge-legend">
        <div className="gauge-legend-item">
          <span className="gauge-dot" style={{ background: barColor }} />
          Projected: <strong>{projected}</strong>
        </div>
        <div className="gauge-legend-item">
          <span className="gauge-dot" style={{ background: "#ef4444" }} />
          Safety: <strong>{safetyStock}</strong>
        </div>
        <div className="gauge-legend-item">
          <span className="gauge-dot" style={{ background: "#f59e0b" }} />
          Reorder: <strong>{reorderPoint}</strong>
        </div>
        <div className="gauge-legend-item">
          <span className="gauge-dot" style={{ background: "#6366f1" }} />
          Target: <strong>{target}</strong>
        </div>
      </div>
    </div>
  );
}

export default ReplenishmentTab;
