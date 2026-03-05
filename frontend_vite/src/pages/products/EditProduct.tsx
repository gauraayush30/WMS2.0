import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import { ArrowLeft } from "lucide-react";

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
}

export default function EditProduct() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    name: "",
    sku_code: "",
    price: "0",
    uom: "pcs",
    par_level: "0",
    reorder_point: "0",
    safety_stock: "0",
    lead_time_days: "0",
    max_stock_level: "0",
    location_zone: "",
    location_aisle: "",
    location_rack: "",
    location_shelf: "",
    location_level: "",
    location_bin: "",
  });
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    authFetch(`${API}/products/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Product not found");
        return r.json();
      })
      .then((p: Product) => {
        setForm({
          name: p.name,
          sku_code: p.sku_code,
          price: String(p.price),
          uom: p.uom || "pcs",
          par_level: String(p.par_level ?? 0),
          reorder_point: String(p.reorder_point ?? 0),
          safety_stock: String(p.safety_stock ?? 0),
          lead_time_days: String(p.lead_time_days ?? 0),
          max_stock_level: String(p.max_stock_level ?? 0),
          location_zone: p.location_zone ?? "",
          location_aisle: p.location_aisle ?? "",
          location_rack: p.location_rack ?? "",
          location_shelf: p.location_shelf ?? "",
          location_level: p.location_level ?? "",
          location_bin: p.location_bin ?? "",
        });
      })
      .catch((e) => setFormError(e.message))
      .finally(() => setLoading(false));
  }, [authFetch, id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setFormSuccess("");
    if (!form.name.trim() || !form.sku_code.trim()) {
      setFormError("Name and SKU Code are required");
      return;
    }
    setSaving(true);
    try {
      const res = await authFetch(`${API}/products/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: form.name.trim(),
          sku_code: form.sku_code.trim(),
          price: parseFloat(form.price) || 0,
          uom: form.uom.trim() || "pcs",
          par_level: parseInt(form.par_level) || 0,
          reorder_point: parseInt(form.reorder_point) || 0,
          safety_stock: parseInt(form.safety_stock) || 0,
          lead_time_days: parseInt(form.lead_time_days) || 0,
          max_stock_level: parseInt(form.max_stock_level) || 0,
          location_zone: form.location_zone.trim(),
          location_aisle: form.location_aisle.trim(),
          location_rack: form.location_rack.trim(),
          location_shelf: form.location_shelf.trim(),
          location_level: form.location_level.trim(),
          location_bin: form.location_bin.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update product");
      }
      setFormSuccess("Product updated successfully!");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <div className="page edit-product-page">
      {/* Header */}
      <div className="page-header">
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate(`/products/${id}`)}
        >
          <ArrowLeft size={16} /> Back to Product
        </button>
        <h2 className="page-title" style={{ marginBottom: 0 }}>
          Edit Product
        </h2>
      </div>

      <div className="card ep-card">
        {formError && <div className="alert alert-error">{formError}</div>}
        {formSuccess && (
          <div className="alert alert-success">{formSuccess}</div>
        )}
        <form onSubmit={handleSubmit} className="form-vertical">
          <div className="form-row">
            <div className="form-group">
              <label>Product Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>SKU Code *</label>
              <input
                type="text"
                value={form.sku_code}
                onChange={(e) => setForm({ ...form, sku_code: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Price</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Unit of Measurement</label>
              <input
                type="text"
                placeholder="e.g. pcs, kg, litre"
                value={form.uom}
                onChange={(e) => setForm({ ...form, uom: e.target.value })}
              />
            </div>
          </div>

          {/* ── Inventory Management Fields ──────────────── */}
          <h4
            style={{
              marginTop: 16,
              marginBottom: 8,
              color: "var(--text-secondary)",
            }}
          >
            Inventory Management
          </h4>
          <div className="form-row">
            <div className="form-group">
              <label>PAR Level</label>
              <input
                type="number"
                min="0"
                value={form.par_level}
                onChange={(e) =>
                  setForm({ ...form, par_level: e.target.value })
                }
                title="Periodic Automatic Replenishment level"
              />
            </div>
            <div className="form-group">
              <label>Reorder Point</label>
              <input
                type="number"
                min="0"
                value={form.reorder_point}
                onChange={(e) =>
                  setForm({ ...form, reorder_point: e.target.value })
                }
                title="Stock level at which a new order should be placed"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Safety Stock</label>
              <input
                type="number"
                min="0"
                value={form.safety_stock}
                onChange={(e) =>
                  setForm({ ...form, safety_stock: e.target.value })
                }
                title="Extra buffer stock to prevent stock-outs"
              />
            </div>
            <div className="form-group">
              <label>Lead Time (days)</label>
              <input
                type="number"
                min="0"
                value={form.lead_time_days}
                onChange={(e) =>
                  setForm({ ...form, lead_time_days: e.target.value })
                }
                title="Days to receive new stock after ordering"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Max Stock Level</label>
              <input
                type="number"
                min="0"
                value={form.max_stock_level}
                onChange={(e) =>
                  setForm({ ...form, max_stock_level: e.target.value })
                }
                title="Maximum stock capacity"
              />
            </div>
          </div>

          {/* ── Warehouse Location Fields ─────────────── */}
          <h4
            style={{
              marginTop: 16,
              marginBottom: 8,
              color: "var(--text-secondary)",
            }}
          >
            Warehouse Location
          </h4>
          <div className="form-row">
            <div className="form-group">
              <label>Zone</label>
              <input
                type="text"
                placeholder="e.g. A, B, Cold"
                value={form.location_zone}
                onChange={(e) =>
                  setForm({ ...form, location_zone: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label>Aisle</label>
              <input
                type="text"
                placeholder="e.g. 1, 2, 3"
                value={form.location_aisle}
                onChange={(e) =>
                  setForm({ ...form, location_aisle: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label>Rack</label>
              <input
                type="text"
                placeholder="e.g. R1, R2"
                value={form.location_rack}
                onChange={(e) =>
                  setForm({ ...form, location_rack: e.target.value })
                }
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Shelf</label>
              <input
                type="text"
                placeholder="e.g. S1, S2"
                value={form.location_shelf}
                onChange={(e) =>
                  setForm({ ...form, location_shelf: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label>Level</label>
              <input
                type="text"
                placeholder="e.g. 1, 2, 3, 4"
                value={form.location_level}
                onChange={(e) =>
                  setForm({ ...form, location_level: e.target.value })
                }
              />
            </div>
            <div className="form-group">
              <label>Bin / Pallet</label>
              <input
                type="text"
                placeholder="e.g. P01, BIN-05"
                value={form.location_bin}
                onChange={(e) =>
                  setForm({ ...form, location_bin: e.target.value })
                }
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: 12 }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Update Product"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(`/products/${id}`)}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
