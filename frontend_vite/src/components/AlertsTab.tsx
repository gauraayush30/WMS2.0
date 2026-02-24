import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import "./AlertsTab.css";

const API = "http://127.0.0.1:8000";

function AlertsTab() {
  const { user, authFetch, logout } = useAuth();

  const [settings, setSettings] = useState(null);
  const [atRisk, setAtRisk] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [settingsRes, riskRes] = await Promise.all([
        authFetch(`${API}/alerts/settings`),
        authFetch(`${API}/alerts/at-risk`),
      ]);

      if (settingsRes.status === 401) { logout(); return; }
      if (!settingsRes.ok) throw new Error("Failed to load alert settings");
      if (!riskRes.ok) throw new Error("Failed to load at-risk SKUs");

      setSettings(await settingsRes.json());
      const riskData = await riskRes.json();
      setAtRisk(riskData.at_risk || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [authFetch, logout]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleToggle = async () => {
    setToggling(true);
    setError("");
    setMessage("");
    try {
      const res = await authFetch(`${API}/alerts/settings`, {
        method: "POST",
        body: JSON.stringify({ alerts_enabled: !settings.alerts_enabled }),
      });
      if (!res.ok) throw new Error("Failed to update settings");
      const updated = await res.json();
      setSettings(updated);
      setMessage(
        updated.alerts_enabled
          ? "✓ Email alerts enabled – you'll receive stock alerts every 6 hours."
          : "Alerts disabled."
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setToggling(false);
    }
  };

  const handleSendNow = async () => {
    setSending(true);
    setError("");
    setMessage("");
    try {
      const res = await authFetch(`${API}/alerts/send-now`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to trigger alert");
      setMessage("✓ Alert job triggered – check your inbox shortly.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  };

  const urgencyClass = (item) => {
    const u = (item.urgency || "").toUpperCase();
    if (u === "CRITICAL") return "risk-critical";
    if (u === "HIGH") return "risk-high";
    return "risk-medium";
  };

  const urgencyLabel = (item) => {
    const u = (item.urgency || "").toUpperCase();
    if (u === "CRITICAL") return "CRITICAL";
    if (u === "HIGH") return "HIGH";
    return "MEDIUM";
  };

  if (loading) return <p className="loading">Loading alert settings…</p>;

  return (
    <div className="alerts-container">

      {/* ── Header ── */}
      <div className="alerts-header">
        <div>
          <h2 className="alerts-title">Email Stock Alerts</h2>
          <p className="alerts-subtitle">
            Receive automated emails every 6 hours when SKUs fall below their reorder point.
          </p>
        </div>
        <button className="alerts-refresh-btn" onClick={fetchData}>
          Refresh
        </button>
      </div>

      {error && <div className="alerts-alert alerts-alert-error">{error}</div>}
      {message && <div className="alerts-alert alerts-alert-success">{message}</div>}

      {/* ── User info card ── */}
      <div className="alerts-user-card">
        <div className="alerts-user-avatar">{user?.name?.[0]?.toUpperCase() || "U"}</div>
        <div className="alerts-user-info">
          <span className="alerts-user-name">{user?.name}</span>
          <span className="alerts-user-email">{user?.email}</span>
        </div>
        <button className="alerts-logout-btn" onClick={logout}>
          Sign out
        </button>
      </div>

      {/* ── Toggle card ── */}
      {settings && (
        <div className="alerts-toggle-card">
          <div className="alerts-toggle-body">
            <div className="alerts-toggle-icon">
              {settings.alerts_enabled ? "🔔" : "🔕"}
            </div>
            <div>
              <p className="alerts-toggle-label">Stock Alert Emails</p>
              <p className="alerts-toggle-desc">
                {settings.alerts_enabled
                  ? "You will receive an email every 6 hours if any SKU needs replenishment."
                  : "Enable to receive automated stock-level alerts to your inbox."}
              </p>
              {settings.last_alert_sent && (
                <p className="alerts-last-sent">
                  Last alert sent:{" "}
                  {new Date(settings.last_alert_sent).toLocaleString()}
                </p>
              )}
            </div>
          </div>

          <div className="alerts-toggle-actions">
            {/* Toggle switch */}
            <button
              className={`toggle-switch ${settings.alerts_enabled ? "toggle-on" : "toggle-off"}`}
              onClick={handleToggle}
              disabled={toggling}
              aria-label="Toggle alerts"
            >
              <span className="toggle-thumb" />
            </button>

            {/* Manual trigger */}
            {settings.alerts_enabled && (
              <button
                className="alerts-send-btn"
                onClick={handleSendNow}
                disabled={sending}
                title="Send alert email immediately"
              >
                {sending ? "Sending…" : "Test Email Now"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── At-risk SKUs ── */}
      <div className="alerts-section">
        <div className="alerts-section-header">
          <h3 className="alerts-section-title">
            Current At-Risk SKUs
            {atRisk.length > 0 && (
              <span className="alerts-badge">{atRisk.length}</span>
            )}
          </h3>
          <p className="alerts-section-desc">
            SKUs whose projected stock during lead time falls at or below their reorder point.
          </p>
        </div>

        {atRisk.length === 0 ? (
          <div className="alerts-all-ok">
            <span className="alerts-all-ok-icon">✅</span>
            <p>All SKUs are healthy — no replenishment needed right now.</p>
          </div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="alerts-risk-cards">
              {atRisk.map((item) => (
                <div
                  key={item.sku_id}
                  className={`alerts-risk-card ${urgencyClass(item)}`}
                >
                  <div className="risk-card-top">
                    <span className="risk-sku-id">{item.sku_id}</span>
                    <span className={`risk-badge ${urgencyClass(item)}`}>
                      {urgencyLabel(item)}
                    </span>
                  </div>
                  <p className="risk-sku-name">{item.sku_name}</p>
                  <div className="risk-stats">
                    <div className="risk-stat">
                      <span className="risk-stat-label">Current Stock</span>
                      <span className="risk-stat-value">{item.current_stock} units</span>
                    </div>
                    <div className="risk-stat">
                      <span className="risk-stat-label">Projected Stock</span>
                      <span className="risk-stat-value risk-stock">{item.projected_stock} units</span>
                    </div>
                    <div className="risk-stat">
                      <span className="risk-stat-label">Forecast Demand</span>
                      <span className="risk-stat-value">{Math.round(item.demand_during_lead_time)} units</span>
                    </div>
                  </div>
                  <div className="risk-stats">
                    <div className="risk-stat">
                      <span className="risk-stat-label">Reorder at</span>
                      <span className="risk-stat-value">{item.reorder_point} units</span>
                    </div>
                    <div className="risk-stat">
                      <span className="risk-stat-label">Lead time</span>
                      <span className="risk-stat-value">{item.lead_time_days}d</span>
                    </div>
                    <div className="risk-stat">
                      <span className="risk-stat-label">Order Qty</span>
                      <span className="risk-stat-value" style={{ color: "#1976d2", fontWeight: 700 }}>{item.order_quantity} units</span>
                    </div>
                  </div>
                  {/* Stock bar — shows projected stock vs target */}
                  <div className="risk-bar-track">
                    <div
                      className={`risk-bar-fill ${urgencyClass(item)}`}
                      style={{
                        width: `${Math.min(100, Math.max(0, (Math.max(0, item.projected_stock) / item.target_stock_level) * 100))}%`,
                      }}
                    />
                  </div>
                  <div className="risk-bar-labels">
                    <span>0</span>
                    <span>Target: {item.target_stock_level}</span>
                  </div>
                  {item.message && (
                    <p className="risk-message">{item.message}</p>
                  )}
                </div>
              ))}
            </div>

            {/* Full table */}
            <div className="table-wrapper" style={{ marginTop: 20 }}>
              <table>
                <thead>
                  <tr>
                    <th>SKU ID</th>
                    <th>SKU Name</th>
                    <th>Current Stock</th>
                    <th>Projected Stock</th>
                    <th>Demand (Lead&nbsp;Time)</th>
                    <th>Reorder Point</th>
                    <th>Lead Time</th>
                    <th>Order Qty</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {atRisk.map((item, i) => (
                    <tr key={i}>
                      <td>{item.sku_id}</td>
                      <td>{item.sku_name}</td>
                      <td>{item.current_stock} units</td>
                      <td style={{ fontWeight: 700, color: "#dc2626" }}>{item.projected_stock} units</td>
                      <td>{Math.round(item.demand_during_lead_time)} units</td>
                      <td>{item.reorder_point} units</td>
                      <td>{item.lead_time_days}d</td>
                      <td style={{ fontWeight: 700, color: "#1976d2" }}>{item.order_quantity} units</td>
                      <td>
                        <span className={`risk-badge ${urgencyClass(item)}`}>
                          {urgencyLabel(item)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* ── Setup instructions ── */}
      {/* <div className="alerts-instructions">
        <h4>📬 Email Setup</h4>
        <p>
          To enable email delivery, add the following variables to your{" "}
          <code>backend_api/.env</code> file:
        </p>
        <pre>{`MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@gmail.com`}</pre>
        <p className="alerts-instructions-note">
          For Gmail, use an <strong>App Password</strong> (not your account password).
          Go to <em>Google Account → Security → 2-Step Verification → App Passwords</em>.
        </p>
      </div> */}
    </div>
  );
}

export default AlertsTab;
