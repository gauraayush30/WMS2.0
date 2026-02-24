import React from "react";

function Controls({
  skus,
  selectedSku,
  onSkuChange,
  activeTab,
  onTabChange,
  historyDays,
  forecastDays,
  onHistoryDaysChange,
  onForecastDaysChange,
  onRefresh,
  loading,
}) {
  const showDayControls =
    activeTab !== "transaction" &&
    activeTab !== "replenishment" &&
    activeTab !== "metrics" &&
    activeTab !== "alerts";

  const showSkuSelect = activeTab !== "metrics" && activeTab !== "alerts";

  return (
    <div className="controls">
      {showSkuSelect && (
        <div className="control-group">
          <label htmlFor="sku-select">SKU</label>
          <select
            id="sku-select"
            value={selectedSku}
            onChange={(e) => onSkuChange(e.target.value)}
          >
            {skus.map((s) => (
              <option key={s.sku_id} value={s.sku_id}>
                {s.sku_id} — {s.sku_name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="tab-group">
        {[
          "history",
          "forecast",
          "replenishment",
          "transaction",
          "metrics",
          "alerts",
        ].map((tab) => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? "active" : ""}`}
            onClick={() => onTabChange(tab)}
          >
            {tab === "transaction"
              ? "Transactions"
              : tab === "metrics"
                ? "Product Metrics"
                : tab === "alerts"
                  ? "🔔 Alerts"
                  : tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {showDayControls && (
        <>
          <div className="control-group">
            <label>
              {activeTab === "forecast" ? "Forecast" : "History"} Days
            </label>
            <div className="day-buttons">
              {(activeTab === "history" ? [7, 30, 90] : [7, 14, 30]).map(
                (d) => {
                  const isActive =
                    activeTab === "history"
                      ? historyDays === d
                      : forecastDays === d;
                  return (
                    <button
                      key={d}
                      className={`day-btn ${isActive ? "active" : ""}`}
                      onClick={() =>
                        activeTab === "history"
                          ? onHistoryDaysChange(d)
                          : onForecastDaysChange(d)
                      }
                    >
                      {d}d
                    </button>
                  );
                },
              )}
            </div>
          </div>

          <button
            className="refresh-btn"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? "Loading\u2026" : "Refresh"}
          </button>
        </>
      )}
    </div>
  );
}

export default Controls;
