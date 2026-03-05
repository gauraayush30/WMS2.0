import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../context/AuthContext";
import {
  Package,
  MapPin,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Pencil,
} from "lucide-react";

interface DashboardStats {
  total_products: number;
  products_without_location: number;
  low_stock_products: number;
  out_of_stock_products: number;
}

interface UnlocatedProduct {
  id: number;
  name: string;
  sku_code: string;
  stock_at_warehouse: number;
}

export default function DashboardPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [unlocated, setUnlocated] = useState<UnlocatedProduct[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(() => {
    setLoading(true);
    Promise.all([
      authFetch(`${API}/dashboard/stats`).then((r) => r.json()),
      authFetch(`${API}/dashboard/products-without-location`).then((r) =>
        r.json(),
      ),
    ])
      .then(([statsData, unlocatedData]) => {
        setStats(statsData);
        setUnlocated(unlocatedData.products || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [authFetch]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading)
    return (
      <div className="page">
        <div className="loading">Loading dashboard...</div>
      </div>
    );

  return (
    <div className="page dashboard-page">
      <div className="page-header">
        <h2 className="page-title">Dashboard</h2>
        <button
          className="btn btn-secondary btn-sm"
          onClick={fetchDashboard}
          title="Refresh"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* ── Stat Cards ──────────────────────────────── */}
      <div className="dash-stats-grid">
        <div className="dash-stat-card">
          <div className="dash-stat-icon dash-stat-icon--blue">
            <Package size={24} />
          </div>
          <div className="dash-stat-info">
            <span className="dash-stat-value">
              {stats?.total_products ?? 0}
            </span>
            <span className="dash-stat-label">Total Products</span>
          </div>
        </div>

        <div
          className={`dash-stat-card ${(stats?.products_without_location ?? 0) > 0 ? "dash-stat-card--warn" : ""}`}
        >
          <div className="dash-stat-icon dash-stat-icon--orange">
            <MapPin size={24} />
          </div>
          <div className="dash-stat-info">
            <span className="dash-stat-value">
              {stats?.products_without_location ?? 0}
            </span>
            <span className="dash-stat-label">Without Location</span>
          </div>
        </div>

        <div
          className={`dash-stat-card ${(stats?.low_stock_products ?? 0) > 0 ? "dash-stat-card--warn" : ""}`}
        >
          <div className="dash-stat-icon dash-stat-icon--yellow">
            <AlertTriangle size={24} />
          </div>
          <div className="dash-stat-info">
            <span className="dash-stat-value">
              {stats?.low_stock_products ?? 0}
            </span>
            <span className="dash-stat-label">Low Stock</span>
          </div>
        </div>

        <div
          className={`dash-stat-card ${(stats?.out_of_stock_products ?? 0) > 0 ? "dash-stat-card--danger" : ""}`}
        >
          <div className="dash-stat-icon dash-stat-icon--red">
            <XCircle size={24} />
          </div>
          <div className="dash-stat-info">
            <span className="dash-stat-value">
              {stats?.out_of_stock_products ?? 0}
            </span>
            <span className="dash-stat-label">Out of Stock</span>
          </div>
        </div>
      </div>

      {/* ── Notifications / Alerts ──────────────────── */}
      {(stats?.products_without_location ?? 0) > 0 && (
        <div className="dash-alert dash-alert--warning">
          <MapPin size={18} />
          <div>
            <strong>
              {stats!.products_without_location} product
              {stats!.products_without_location > 1 ? "s" : ""} without
              warehouse location
            </strong>
            <p style={{ margin: "4px 0 0", fontSize: 13, opacity: 0.85 }}>
              Assign warehouse locations to enable pick-list generation.
            </p>
          </div>
        </div>
      )}

      {(stats?.low_stock_products ?? 0) > 0 && (
        <div className="dash-alert dash-alert--info">
          <AlertTriangle size={18} />
          <span>
            <strong>{stats!.low_stock_products}</strong> product
            {stats!.low_stock_products > 1 ? "s are" : " is"} below reorder
            point.
          </span>
        </div>
      )}

      {(stats?.out_of_stock_products ?? 0) > 0 && (
        <div className="dash-alert dash-alert--danger">
          <XCircle size={18} />
          <span>
            <strong>{stats!.out_of_stock_products}</strong> product
            {stats!.out_of_stock_products > 1 ? "s are" : " is"} out of stock.
          </span>
        </div>
      )}

      {/* ── Products Without Location Table ─────────── */}
      {unlocated.length > 0 && (
        <div className="dash-section">
          <h3 className="dash-section-title">
            <MapPin size={18} /> Products Without Warehouse Location
          </h3>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>SKU Code</th>
                  <th>Stock</th>
                  <th style={{ width: 120 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {unlocated.map((p) => (
                  <tr key={p.id}>
                    <td className="td-bold">{p.name}</td>
                    <td>
                      <code>{p.sku_code}</code>
                    </td>
                    <td>{p.stock_at_warehouse}</td>
                    <td>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => navigate(`/products/${p.id}/edit`)}
                      >
                        <Pencil size={14} /> Set Location
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
