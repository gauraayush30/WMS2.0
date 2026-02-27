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
} from "lucide-react";

interface Product {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  created_at: string;
  updated_at: string;
}

export default function ViewProduct() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

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
    </div>
  );
}
