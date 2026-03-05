import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import {
  ArrowLeft,
  Pencil,
  Trash2,
  Package,
  DollarSign,
  Barcode,
  Warehouse,
  Clock,
  History,
  Ruler,
  AlertTriangle,
  ArrowDownToLine,
  ShieldCheck,
  Truck,
  TrendingUp,
  MapPin,
} from "lucide-react";

interface Product {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  uom: string;
  par_level: number;
  reorder_point: number;
  safety_stock: number;
  lead_time_days: number;
  max_stock_level: number;
  location_zone: string;
  location_aisle: string;
  location_rack: string;
  location_shelf: string;
  location_level: string;
  location_bin: string;
  created_at: string;
  updated_at: string;
}

interface AuditEntry {
  id: number;
  product_id: number;
  field_name: string;
  old_value: string;
  new_value: string;
  updated_by_name: string;
  created_at: string;
}

export default function ViewProduct() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    authFetch(`${API}/products/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Product not found");
        return r.json();
      })
      .then((data) => setProduct(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [authFetch, id]);

  /* Fetch audit log */
  useEffect(() => {
    if (!id) return;
    setAuditLoading(true);
    authFetch(`${API}/products/${id}/audit-log`)
      .then((r) => {
        if (!r.ok) return { entries: [] };
        return r.json();
      })
      .then((data) => setAuditLog(data.entries || []))
      .catch(() => setAuditLog([]))
      .finally(() => setAuditLoading(false));
  }, [authFetch, id]);

  const handleDelete = async () => {
    if (
      !confirm(
        "Are you sure you want to delete this product? All related inventory transactions will also be deleted.",
      )
    )
      return;
    setDeleting(true);
    try {
      const res = await authFetch(`${API}/products/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to delete");
        setDeleting(false);
        return;
      }
      navigate("/products");
    } catch {
      alert("Error deleting product");
      setDeleting(false);
    }
  };

  if (loading) return <div className="loading">Loading...</div>;
  if (error || !product)
    return (
      <div className="page">
        <div className="alert alert-error">{error || "Product not found"}</div>
        <button
          className="btn btn-secondary btn-sm"
          style={{ marginTop: 12 }}
          onClick={() => navigate("/products")}
        >
          <ArrowLeft size={16} /> Back to Products
        </button>
      </div>
    );

  const stockClass =
    product.stock_at_warehouse === 0
      ? "stock-badge--danger"
      : product.stock_at_warehouse <= 10
        ? "stock-badge--warning"
        : "stock-badge--ok";

  return (
    <div className="page vp-page">
      {/* Header */}
      <div className="page-header">
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate("/products")}
        >
          <ArrowLeft size={16} /> Back
        </button>
        <h2 className="page-title" style={{ marginBottom: 0 }}>
          {product.name}
        </h2>
        <code className="vp-sku-badge">{product.sku_code}</code>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            className="btn btn-primary"
            onClick={() => navigate(`/products/${product.id}/edit`)}
          >
            <Pencil size={16} /> Edit
          </button>
          <button
            className="btn btn-danger"
            onClick={handleDelete}
            disabled={deleting}
          >
            <Trash2 size={16} /> {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>

      {/* Detail cards */}
      <div className="vp-grid">
        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--blue">
            <Package size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Product Name</span>
            <span className="vp-detail-value">{product.name}</span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--purple">
            <Barcode size={22} />
          </div>
          <div>
            <span className="vp-detail-label">SKU Code</span>
            <span className="vp-detail-value">
              <code>{product.sku_code}</code>
            </span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--green">
            <DollarSign size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Price</span>
            <span className="vp-detail-value">
              ₹{Number(product.price).toFixed(2)}
            </span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--yellow">
            <Warehouse size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Stock at Warehouse</span>
            <span className="vp-detail-value">
              <span className={`stock-badge ${stockClass}`}>
                {product.stock_at_warehouse}
              </span>
            </span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--purple">
            <Ruler size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Unit of Measurement</span>
            <span className="vp-detail-value">{product.uom || "pcs"}</span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--gray">
            <Clock size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Created</span>
            <span className="vp-detail-value">
              {new Date(product.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--gray">
            <Clock size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Last Updated</span>
            <span className="vp-detail-value">
              {new Date(product.updated_at).toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Inventory Management section */}
      <h3
        style={{
          marginTop: 24,
          marginBottom: 12,
          color: "var(--text-secondary)",
        }}
      >
        Inventory Management
      </h3>
      <div className="vp-grid">
        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--blue">
            <TrendingUp size={22} />
          </div>
          <div>
            <span className="vp-detail-label">PAR Level</span>
            <span className="vp-detail-value">{product.par_level ?? 0}</span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--yellow">
            <ArrowDownToLine size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Reorder Point</span>
            <span className="vp-detail-value">
              {product.reorder_point ?? 0}
            </span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--green">
            <ShieldCheck size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Safety Stock</span>
            <span className="vp-detail-value">{product.safety_stock ?? 0}</span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--purple">
            <Truck size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Lead Time</span>
            <span className="vp-detail-value">
              {product.lead_time_days ?? 0} days
            </span>
          </div>
        </div>

        <div className="vp-detail-card">
          <div className="vp-detail-icon vp-detail-icon--yellow">
            <AlertTriangle size={22} />
          </div>
          <div>
            <span className="vp-detail-label">Max Stock Level</span>
            <span className="vp-detail-value">
              {product.max_stock_level ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* Warehouse Location section */}
      <h3
        style={{
          marginTop: 24,
          marginBottom: 12,
          color: "var(--text-secondary)",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <MapPin size={18} /> Warehouse Location
        {!product.location_zone &&
          !product.location_aisle &&
          !product.location_rack &&
          !product.location_shelf &&
          !product.location_level &&
          !product.location_bin && (
            <span
              style={{
                fontSize: 12,
                background: "var(--danger, #ef4444)",
                color: "#fff",
                padding: "2px 8px",
                borderRadius: 4,
                marginLeft: 8,
              }}
            >
              Not Set
            </span>
          )}
      </h3>
      <div className="vp-grid">
        {[
          { label: "Zone", value: product.location_zone },
          { label: "Aisle", value: product.location_aisle },
          { label: "Rack", value: product.location_rack },
          { label: "Shelf", value: product.location_shelf },
          { label: "Level", value: product.location_level },
          { label: "Bin / Pallet", value: product.location_bin },
        ].map((item) => (
          <div className="vp-detail-card" key={item.label}>
            <div className="vp-detail-icon vp-detail-icon--blue">
              <MapPin size={22} />
            </div>
            <div>
              <span className="vp-detail-label">{item.label}</span>
              <span className="vp-detail-value">
                {item.value || (
                  <span style={{ color: "var(--text-muted, #999)" }}>—</span>
                )}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Edit History / Audit Log */}
      <div className="vp-audit-section">
        <h3 className="vp-audit-title">
          <History size={18} /> Edit History
        </h3>
        {auditLoading ? (
          <p className="vp-audit-empty">Loading history...</p>
        ) : auditLog.length === 0 ? (
          <p className="vp-audit-empty">
            No edits have been made to this product yet.
          </p>
        ) : (
          <div className="vp-audit-table-wrap">
            <table className="vp-audit-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Field</th>
                  <th>Old Value</th>
                  <th>New Value</th>
                  <th>Updated By</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.created_at).toLocaleString()}</td>
                    <td>
                      <span className="vp-audit-field">{entry.field_name}</span>
                    </td>
                    <td>
                      <span className="vp-audit-old">{entry.old_value}</span>
                    </td>
                    <td>
                      <span className="vp-audit-new">{entry.new_value}</span>
                    </td>
                    <td>{entry.updated_by_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
