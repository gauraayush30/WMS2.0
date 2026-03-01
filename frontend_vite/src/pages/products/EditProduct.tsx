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
