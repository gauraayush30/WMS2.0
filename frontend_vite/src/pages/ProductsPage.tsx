import { useEffect, useState, useCallback } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Plus, Pencil, Trash2, X, Search } from "lucide-react";

interface Product {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  created_at: string;
  updated_at: string;
}

export default function ProductsPage() {
  const { authFetch } = useAuth();
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editProduct, setEditProduct] = useState<Product | null>(null);
  const [form, setForm] = useState({
    name: "",
    sku_code: "",
    price: "0",
    stock_at_warehouse: "0",
  });
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const fetchProducts = useCallback(() => {
    setLoading(true);
    authFetch(
      `${API}/products?page=${page}&per_page=15&search=${encodeURIComponent(search)}`,
    )
      .then((r) => r.json())
      .then((data) => {
        setProducts(data.products || []);
        setTotalPages(data.total_pages || 0);
        setTotal(data.total || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [authFetch, page, search]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const openCreate = () => {
    setEditProduct(null);
    setForm({ name: "", sku_code: "", price: "0", stock_at_warehouse: "0" });
    setFormError("");
    setShowModal(true);
  };

  const openEdit = (p: Product) => {
    setEditProduct(p);
    setForm({
      name: p.name,
      sku_code: p.sku_code,
      price: String(p.price),
      stock_at_warehouse: String(p.stock_at_warehouse),
    });
    setFormError("");
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (!form.name.trim() || !form.sku_code.trim()) {
      setFormError("Name and SKU Code are required");
      return;
    }
    setSaving(true);
    try {
      const url = editProduct
        ? `${API}/products/${editProduct.id}`
        : `${API}/products`;
      const method = editProduct ? "PUT" : "POST";
      const body: Record<string, unknown> = {
        name: form.name.trim(),
        sku_code: form.sku_code.trim(),
        price: parseFloat(form.price) || 0,
      };
      if (!editProduct) {
        body.stock_at_warehouse = parseInt(form.stock_at_warehouse) || 0;
      }
      const res = await authFetch(url, {
        method,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save product");
      }
      setShowModal(false);
      fetchProducts();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this product?")) return;
    try {
      const res = await authFetch(`${API}/products/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to delete");
        return;
      }
      fetchProducts();
    } catch {
      alert("Error deleting product");
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">Products</h2>
        <span className="page-count">{total} total</span>
        <button className="btn btn-primary" onClick={openCreate}>
          <Plus size={16} /> Add Product
        </button>
      </div>

      <div className="toolbar">
        <div className="search-box">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by name or SKU..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : products.length === 0 ? (
        <div className="empty-state">
          <p>No products found.</p>
        </div>
      ) : (
        <>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>SKU Code</th>
                  <th>Price</th>
                  <th>Stock</th>
                  <th>Updated</th>
                  <th style={{ width: 100 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id}>
                    <td className="td-bold">{p.name}</td>
                    <td>
                      <code>{p.sku_code}</code>
                    </td>
                    <td>${Number(p.price).toFixed(2)}</td>
                    <td>
                      <span
                        className={`stock-badge ${p.stock_at_warehouse === 0 ? "stock-badge--danger" : p.stock_at_warehouse <= 10 ? "stock-badge--warning" : "stock-badge--ok"}`}
                      >
                        {p.stock_at_warehouse}
                      </span>
                    </td>
                    <td>{new Date(p.updated_at).toLocaleDateString()}</td>
                    <td>
                      <div className="action-btns">
                        <button
                          className="btn-icon"
                          onClick={() => openEdit(p)}
                          title="Edit"
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          className="btn-icon btn-icon--danger"
                          onClick={() => handleDelete(p.id)}
                          title="Delete"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Create / Edit Modal */}
      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editProduct ? "Edit Product" : "Add Product"}</h3>
              <button className="btn-icon" onClick={() => setShowModal(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="modal-body">
              {formError && (
                <div className="alert alert-error">{formError}</div>
              )}
              <div className="form-group">
                <label>Product Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>SKU Code</label>
                <input
                  type="text"
                  value={form.sku_code}
                  onChange={(e) =>
                    setForm({ ...form, sku_code: e.target.value })
                  }
                  required
                />
              </div>
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
              {!editProduct && (
                <div className="form-group">
                  <label>Initial Stock</label>
                  <input
                    type="number"
                    min="0"
                    value={form.stock_at_warehouse}
                    onChange={(e) =>
                      setForm({ ...form, stock_at_warehouse: e.target.value })
                    }
                  />
                </div>
              )}
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving}
                >
                  {saving ? "Saving..." : editProduct ? "Update" : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
