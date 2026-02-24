import React, { useState } from "react";
import { Bar } from "react-chartjs-2";
import "./ProductMetricsTab.css";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const API = "http://127.0.0.1:8000";

interface ReportRow {
  transaction_date: string;
  sku_id: string;
  sku_name: string;
  stock_adjustment_qty: number;
}

function downloadCsv(rows: ReportRow[], filename: string) {
  if (rows.length === 0) return;
  const header = "Transaction Date,SKU ID,SKU Name,Stock Adjustment Qty";
  const csv = [
    header,
    ...rows.map(
      (r) =>
        `${r.transaction_date},${r.sku_id},"${r.sku_name}",${r.stock_adjustment_qty}`,
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function ProductMetricsTab() {
  const today = new Date().toISOString().split("T")[0];
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split("T")[0];

  const [startDate, setStartDate] = useState(thirtyDaysAgo);
  const [endDate, setEndDate] = useState(today);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fetched, setFetched] = useState(false);
  const [reportLoading, setReportLoading] = useState<string | null>(null);
  const [reportError, setReportError] = useState("");

  // Forecast accuracy state
  interface AccuracyRow {
    sku_id: string;
    sku_name: string;
    total_actual_sales: number;
    total_predicted_sales: number;
    mae: number;
    mape: number;
    accuracy_pct: number;
  }
  const [accuracy, setAccuracy] = useState<AccuracyRow[]>([]);
  const [accuracyLoading, setAccuracyLoading] = useState(false);
  const [accuracyError, setAccuracyError] = useState("");
  const [accuracyFetched, setAccuracyFetched] = useState(false);

  const fetchMetrics = async () => {
    if (!startDate || !endDate) {
      setError("Please select both start and end dates.");
      return;
    }
    if (startDate > endDate) {
      setError("Start date cannot be after end date.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await fetch(
        `${API}/product-metrics?start_date=${startDate}&end_date=${endDate}`,
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to fetch metrics");
      }
      const data = await res.json();
      setMetrics(data.metrics || []);
      setFetched(true);

      // Also fetch forecast accuracy for the same period
      setAccuracyLoading(true);
      setAccuracyError("");
      try {
        const accRes = await fetch(
          `${API}/forecast-accuracy?start_date=${startDate}&end_date=${endDate}`,
        );
        if (!accRes.ok) {
          const accErr = await accRes.json().catch(() => ({}));
          throw new Error(accErr.detail || "Failed to fetch accuracy data");
        }
        const accData = await accRes.json();
        setAccuracy(accData.comparison || []);
        setAccuracyFetched(true);
      } catch (ae: unknown) {
        setAccuracyError(
          ae instanceof Error ? ae.message : "Error fetching accuracy data",
        );
      } finally {
        setAccuracyLoading(false);
      }
    } catch (e) {
      setError(e.message || "Error fetching metrics");
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async (type: "purchases" | "sales") => {
    if (!startDate || !endDate) {
      setReportError("Please select both start and end dates.");
      return;
    }
    if (startDate > endDate) {
      setReportError("Start date cannot be after end date.");
      return;
    }
    setReportLoading(type);
    setReportError("");
    try {
      const res = await fetch(
        `${API}/reports/${type}?start_date=${startDate}&end_date=${endDate}`,
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to fetch ${type} report`);
      }
      const data = await res.json();
      const rows: ReportRow[] = data.report || [];
      if (rows.length === 0) {
        setReportError(
          `No ${type} transactions found for the selected period.`,
        );
        return;
      }
      downloadCsv(rows, `${type}_report_${startDate}_to_${endDate}.csv`);
    } catch (e: unknown) {
      setReportError(
        e instanceof Error ? e.message : `Error downloading ${type} report`,
      );
    } finally {
      setReportLoading(null);
    }
  };

  // Compute highlights
  const mostSold =
    metrics.length > 0
      ? metrics.reduce((a, b) => (b.total_sales > a.total_sales ? b : a))
      : null;

  const leastSold =
    metrics.length > 0
      ? metrics.reduce((a, b) => (b.total_sales < a.total_sales ? b : a))
      : null;

  const totalSalesAll = metrics.reduce(
    (sum, m) => sum + (m.total_sales || 0),
    0,
  );
  const totalPurchasesAll = metrics.reduce(
    (sum, m) => sum + (m.total_purchases || 0),
    0,
  );

  const chartData = {
    labels: metrics.map((m) => m.sku_id),
    datasets: [
      {
        label: "Total Sales",
        data: metrics.map((m) => m.total_sales),
        backgroundColor: "rgba(25, 118, 210, 0.75)",
        borderColor: "#1976d2",
        borderWidth: 1,
        borderRadius: 6,
      },
      {
        label: "Total Purchases",
        data: metrics.map((m) => m.total_purchases),
        backgroundColor: "rgba(46, 125, 50, 0.7)",
        borderColor: "#2e7d32",
        borderWidth: 1,
        borderRadius: 6,
      },
    ],
  };

  const chartOpts = {
    responsive: true,
    plugins: {
      legend: { position: "top" },
      tooltip: {
        callbacks: {
          title: (items) => {
            const idx = items[0].dataIndex;
            return `${metrics[idx].sku_id} — ${metrics[idx].sku_name}`;
          },
        },
      },
      title: {
        display: true,
        text: "Product Metrics",
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: { stepSize: 1 },
        title: {
          display: true,
          text: "Quantity",
        },
      },
      x: {
        title: {
          display: true,
          text: "SKUs",
        },
      },
    },
  };

  return (
    <div className="metrics-container">
      {/* Title bar */}
      <div className="metrics-title-bar">
        <div>
          <h2 className="metrics-title">Product Metrics</h2>
          <p className="metrics-subtitle">
            Analyse total sales &amp; purchases across all SKUs for a date range
          </p>
        </div>
      </div>

      {/* Date picker + Generate */}
      <div className="metrics-controls">
        <div className="metrics-controls-left">
          <div className="control-group">
            <label htmlFor="metrics-start">Start Date</label>
            <input
              id="metrics-start"
              type="date"
              className="metrics-date-input"
              value={startDate}
              max={endDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>

          <div className="control-group">
            <label htmlFor="metrics-end">End Date</label>
            <input
              id="metrics-end"
              type="date"
              className="metrics-date-input"
              value={endDate}
              min={startDate}
              max={today}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
        </div>

        <button
          className="metrics-primary-btn"
          onClick={fetchMetrics}
          disabled={loading}
        >
          {loading ? "Loading\u2026" : "Generate Report"}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Download reports section */}
      <div className="metrics-download-section">
        <div className="metrics-download-info">
          <span className="metrics-download-title">Download Reports</span>
          <span className="metrics-download-desc">
            Export transaction-level data for the selected date range as CSV
          </span>
        </div>
        <div className="metrics-download-actions">
          <button
            className="metrics-download-btn metrics-download-purchase"
            onClick={() => downloadReport("purchases")}
            disabled={reportLoading !== null}
            title="Download purchase transactions as CSV"
          >
            <span className="metrics-download-icon">&#x1F4E5;</span>
            {reportLoading === "purchases"
              ? "Downloading\u2026"
              : "Purchase Report"}
          </button>

          <button
            className="metrics-download-btn metrics-download-sales"
            onClick={() => downloadReport("sales")}
            disabled={reportLoading !== null}
            title="Download sales transactions as CSV"
          >
            <span className="metrics-download-icon">&#x1F4E4;</span>
            {reportLoading === "sales" ? "Downloading\u2026" : "Sales Report"}
          </button>
        </div>
      </div>

      {reportError && <div className="alert alert-error">{reportError}</div>}

      {loading && <p className="loading">Fetching metrics&hellip;</p>}

      {!loading && fetched && metrics.length === 0 && (
        <p className="no-data">
          No transactions found for the selected period.
        </p>
      )}

      {!loading && metrics.length > 0 && (
        <>
          {/* Summary cards */}
          <div className="status-cards">
            <div className="card">
              <span className="card-label">Period</span>
              <span className="card-value" style={{ fontSize: "1rem" }}>
                {startDate} &rarr; {endDate}
              </span>
            </div>
            <div className="card">
              <span className="card-label">Total Sales (all SKUs)</span>
              <span className="card-value">{totalSalesAll} units</span>
            </div>
            <div className="card">
              <span className="card-label">Total Purchases (all SKUs)</span>
              <span className="card-value">{totalPurchasesAll} units</span>
            </div>
          </div>

          {/* Most / Least sold highlight cards */}
          <div className="metrics-highlight-row">
            {mostSold && (
              <div className="metrics-highlight-card metrics-highlight-top">
                <div className="metrics-highlight-icon">🏆</div>
                <div className="metrics-highlight-body">
                  <span className="metrics-highlight-label">Most Sold</span>
                  <span className="metrics-highlight-sku">
                    {mostSold.sku_id} — {mostSold.sku_name}
                  </span>
                  <span className="metrics-highlight-qty">
                    {mostSold.total_sales} units sold
                  </span>
                </div>
              </div>
            )}

            {leastSold && metrics.length > 1 && (
              <div className="metrics-highlight-card metrics-highlight-bottom">
                <div className="metrics-highlight-icon">📉</div>
                <div className="metrics-highlight-body">
                  <span className="metrics-highlight-label">Least Sold</span>
                  <span className="metrics-highlight-sku">
                    {leastSold.sku_id} — {leastSold.sku_name}
                  </span>
                  <span className="metrics-highlight-qty">
                    {leastSold.total_sales} units sold
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Bar chart */}
          <div className="chart-box">
            <Bar data={chartData} options={chartOpts} />
          </div>

          {/* Data table */}
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>SKU ID</th>
                  <th>SKU Name</th>
                  <th>Total Sales</th>
                  <th>Total Purchases</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((m, i) => (
                  <tr
                    key={i}
                    className={
                      mostSold && m.sku_id === mostSold.sku_id
                        ? "metrics-row-top"
                        : leastSold &&
                            m.sku_id === leastSold.sku_id &&
                            metrics.length > 1
                          ? "metrics-row-bottom"
                          : ""
                    }
                  >
                    <td>{m.sku_id}</td>
                    <td>{m.sku_name}</td>
                    <td>{m.total_sales} units</td>
                    <td>{m.total_purchases} units</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Forecast accuracy comparison */}
      {!loading && accuracyFetched && (
        <div className="accuracy-section">
          <div className="accuracy-header">
            <h3 className="accuracy-title">Forecast Accuracy Comparison</h3>
            <p className="accuracy-desc">
              Actual vs predicted sales per SKU for {startDate} &rarr; {endDate}
            </p>
          </div>

          {accuracyLoading && (
            <p className="loading">Loading accuracy data&hellip;</p>
          )}
          {accuracyError && (
            <div className="alert alert-error">{accuracyError}</div>
          )}

          {!accuracyLoading && accuracy.length === 0 && (
            <p className="no-data">No accuracy data available.</p>
          )}

          {!accuracyLoading && accuracy.length > 0 && (
            <>
              {/* Summary cards */}
              <div className="accuracy-cards">
                <div className="accuracy-card accuracy-card-good">
                  <span className="accuracy-card-value">
                    {Math.round(
                      accuracy.reduce((s, a) => s + a.accuracy_pct, 0) /
                        accuracy.length,
                    )}
                    %
                  </span>
                  <span className="accuracy-card-label">Avg Accuracy</span>
                </div>
                <div className="accuracy-card">
                  <span className="accuracy-card-value">
                    {Math.round(
                      (accuracy.reduce((s, a) => s + a.mae, 0) /
                        accuracy.length) *
                        100,
                    ) / 100}
                  </span>
                  <span className="accuracy-card-label">Avg MAE</span>
                </div>
                <div className="accuracy-card">
                  <span className="accuracy-card-value">
                    {
                      accuracy.reduce(
                        (best, a) =>
                          a.accuracy_pct > best.accuracy_pct ? a : best,
                        accuracy[0],
                      ).sku_id
                    }
                  </span>
                  <span className="accuracy-card-label">
                    Best Predicted SKU
                  </span>
                </div>
              </div>

              {/* Accuracy bar chart */}
              <div className="chart-box">
                <Bar
                  data={{
                    labels: accuracy.map((a) => a.sku_id),
                    datasets: [
                      {
                        label: "Actual Sales",
                        data: accuracy.map((a) => a.total_actual_sales),
                        backgroundColor: "rgba(25, 118, 210, 0.75)",
                        borderColor: "#1976d2",
                        borderWidth: 1,
                        borderRadius: 6,
                      },
                      {
                        label: "Predicted Sales",
                        data: accuracy.map((a) => a.total_predicted_sales),
                        backgroundColor: "rgba(255, 152, 0, 0.7)",
                        borderColor: "#f57c00",
                        borderWidth: 1,
                        borderRadius: 6,
                      },
                    ],
                  }}
                  options={{
                    responsive: true,
                    plugins: {
                      legend: { position: "top" as const },
                      tooltip: {
                        callbacks: {
                          title: (items) => {
                            const idx = items[0].dataIndex;
                            return `${accuracy[idx].sku_id} \u2014 ${accuracy[idx].sku_name}`;
                          },
                          afterBody: (items) => {
                            const idx = items[0].dataIndex;
                            const a = accuracy[idx];
                            return [
                              `Accuracy: ${a.accuracy_pct}%`,
                              `MAE: ${a.mae}`,
                              `WMAPE: ${a.mape}%`,
                            ];
                          },
                        },
                      },
                        title: {
                          display: true,
                          text: "Actual vs Predicted Sales",
                        },
                    },
                    scales: {
                      y: { beginAtZero: true, ticks: { stepSize: 1 }, title: { display: true, text: "Quantity" } },
                      x: { title: { display: true, text: "SKUs" } },
                    },
                  }}
                />
              </div>

              {/* Accuracy table */}
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>SKU ID</th>
                      <th>SKU Name</th>
                      <th>Actual Sales</th>
                      <th>Predicted Sales</th>
                      <th>MAE</th>
                      <th>WMAPE</th>
                      <th>Accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accuracy.map((a) => (
                      <tr key={a.sku_id}>
                        <td>{a.sku_id}</td>
                        <td>{a.sku_name}</td>
                        <td>{a.total_actual_sales} units</td>
                        <td>{a.total_predicted_sales} units</td>
                        <td>{a.mae}</td>
                        <td>{a.mape}%</td>
                        <td>
                          <span
                            className={
                              a.accuracy_pct >= 80
                                ? "accuracy-badge accuracy-good"
                                : a.accuracy_pct >= 50
                                  ? "accuracy-badge accuracy-mid"
                                  : "accuracy-badge accuracy-low"
                            }
                          >
                            {a.accuracy_pct}%
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
      )}

      {!fetched && !loading && (
        <div className="metrics-empty-state">
          <div className="metrics-empty-icon">📊</div>
          <p>
            Select a date range and click <strong>Generate Report</strong> to
            view metrics.
          </p>
        </div>
      )}
    </div>
  );
}

export default ProductMetricsTab;
