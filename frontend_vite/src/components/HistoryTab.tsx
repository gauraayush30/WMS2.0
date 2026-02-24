import React from "react";
import { Line } from "react-chartjs-2";

function HistoryTab({ data, meta, skuInfo, loading }) {
  if (loading) return <p className="loading">Loading data&hellip;</p>;
  if (data.length === 0) return <p className="no-data">No data available.</p>;

  const chartData = {
    labels: data.map((d) => d.date),
    datasets: [
      {
        label: "Sales Qty",
        data: data.map((d) => d.sales_qty),
        borderColor: "#2e7d32",
        backgroundColor: "rgba(46,125,50,0.12)",
        tension: 0.35,
        fill: true,
        pointRadius: 3,
      },
      {
        label: "Stock Level",
        data: data.map((d) => d.stock_level),
        borderColor: "#f57c00",
        backgroundColor: "rgba(245,124,0,0.08)",
        tension: 0.35,
        fill: false,
        pointRadius: 3,
        borderDash: [6, 3],
      },
    ],
  };

  const chartOpts = {
    responsive: true,
    plugins: { legend: { position: "top" }, title: { display: true, text: "Sales and Stock History" } },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Timestamps', // X-axis label
        },
        // ... other x-axis configurations like ticks, etc.
      },
      y: {
        title: {
          display: true,
          text: 'Quantity', // Y-axis label
        },
        beginAtZero: true, // Common option to start the y-axis at zero
        // ... other y-axis configurations
      },
    },
  };

  return (
    <>
      {skuInfo && meta && (
        <div className="status-cards">
          <div className="card">
            <span className="card-label">SKU</span>
            <span className="card-value">{skuInfo.sku_name}</span>
          </div>
          <div className="card">
            <span className="card-label">Records</span>
            <span className="card-value">{skuInfo.total_records}</span>
          </div>
          <div className="card">
            <span className="card-label">Current Stock</span>
            <span className="card-value">{meta.current_stock}</span>
          </div>
        </div>
      )}

      <div className="chart-box">
        <Line data={chartData} options={chartOpts} />
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Sales Qty</th>
              <th>Purchase Qty</th>
              <th>Stock Level</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, i) => (
              <tr key={i}>
                <td>{item.date}</td>
                <td>{item.sales_qty} units</td>
                <td>{item.purchase_qty} units</td>
                <td>{item.stock_level} units</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default HistoryTab;
