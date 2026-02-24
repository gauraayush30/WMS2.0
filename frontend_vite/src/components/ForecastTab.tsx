import React from "react";
import { Line } from "react-chartjs-2";

function ForecastTab({ data, meta, loading }) {
  if (loading) return <p className="loading">Loading data&hellip;</p>;
  if (data.length === 0) return <p className="no-data">No data available.</p>;

  const chartData = {
    labels: data.map((d) => d.date),
    datasets: [
      {
        label: "Predicted Sales",
        data: data.map((d) => d.predicted_sales),
        borderColor: "#1976d2",
        backgroundColor: "rgba(25,118,210,0.12)",
        tension: 0.35,
        fill: true,
        pointRadius: 4,
      },
    ],
  };

  const chartOpts = {
    responsive: true,
    plugins: { legend: { position: "top" }, title: { display: true, text: "Forecasted Sales" } },
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
      {meta && (
        <div className="status-cards">
          <div className="card">
            <span className="card-label">Current Stock</span>
            <span className="card-value">{meta.current_stock}</span>
          </div>
          <div className="card">
            <span className="card-label">Forecast Demand</span>
            <span className="card-value">{meta.total_forecast_demand}</span>
          </div>
          <div
            className={`card status-${(meta.stock_status || "")
              .replace(/\s+/g, "-")
              .toLowerCase()}`}
          >
            <span className="card-label">Status</span>
            <span className="card-value">{meta.stock_status}</span>
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
              <th>Predicted Sales</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item, i) => (
              <tr key={i}>
                <td>{item.date}</td>
                <td>{item.predicted_sales} units </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default ForecastTab;
