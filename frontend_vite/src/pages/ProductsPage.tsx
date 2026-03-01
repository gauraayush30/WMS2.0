import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../context/AuthContext";
import { Plus, Search, MoreVertical, Eye, Pencil, Trash2 } from "lucide-react";

interface Product {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  uom: string;
  created_at: string;
  updated_at: string;
}

export default function ProductsPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const [products, setProducts] = useState<Product[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  /* Three-dot menu state */
  const [menuOpenId, setMenuOpenId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

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

  /* Close menu on outside click */
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleDelete = async (id: number) => {
    setMenuOpenId(null);
    if (
      !confirm(
        "Are you sure you want to delete this product? All related inventory transactions will also be deleted.",
      )
    )
      return;
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
        <button
          className="btn btn-primary"
          onClick={() => navigate("/products/create")}
        >
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
                  <th>UOM</th>
                  <th>Stock</th>
                  <th>Updated</th>
                  <th style={{ width: 60 }}></th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr
                    key={p.id}
                    className="tr-clickable"
                    onClick={() => navigate(`/products/${p.id}`)}
                  >
                    <td className="td-bold">{p.name}</td>
                    <td>
                      <code>{p.sku_code}</code>
                    </td>
                    <td>₹{Number(p.price).toFixed(2)}</td>
                    <td>{p.uom || "pcs"}</td>
                    <td>
                      <span
                        className={`stock-badge ${
                          p.stock_at_warehouse === 0
                            ? "stock-badge--danger"
                            : p.stock_at_warehouse <= 10
                              ? "stock-badge--warning"
                              : "stock-badge--ok"
                        }`}
                      >
                        {p.stock_at_warehouse}
                      </span>
                    </td>
                    <td>{new Date(p.updated_at).toLocaleDateString()}</td>
                    <td>
                      <div
                        className="dot-menu-wrapper"
                        ref={menuOpenId === p.id ? menuRef : null}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          className="btn-icon"
                          title="Actions"
                          onClick={() =>
                            setMenuOpenId(menuOpenId === p.id ? null : p.id)
                          }
                        >
                          <MoreVertical size={16} />
                        </button>
                        {menuOpenId === p.id && (
                          <div className="dot-menu">
                            <button
                              className="dot-menu-item"
                              onClick={() => {
                                setMenuOpenId(null);
                                navigate(`/products/${p.id}`);
                              }}
                            >
                              <Eye size={14} /> View
                            </button>
                            <button
                              className="dot-menu-item"
                              onClick={() => {
                                setMenuOpenId(null);
                                navigate(`/products/${p.id}/edit`);
                              }}
                            >
                              <Pencil size={14} /> Edit
                            </button>
                            <button
                              className="dot-menu-item dot-menu-item--danger"
                              onClick={() => handleDelete(p.id)}
                            >
                              <Trash2 size={14} /> Delete
                            </button>
                          </div>
                        )}
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
    </div>
  );
}
