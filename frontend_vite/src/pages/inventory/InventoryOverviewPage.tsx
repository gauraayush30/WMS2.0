import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import { ArrowLeft, Package } from "lucide-react";

interface ProductStock {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  uom: string;
  updated_at: string;
}

export default function InventoryOverviewPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();

  const [products, setProducts] = useState<ProductStock[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await authFetch(
          `${API}/inventory/overview?page=${page}&per_page=18&search=${encodeURIComponent(search)}`,
        );
        const data = await r.json();
        if (!cancelled) {
          setProducts(data.products || []);
          setTotalPages(data.total_pages || 0);
        }
      } catch (err) {
        console.error(err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    setLoading(true);
    load();
    return () => {
      cancelled = true;
    };
  }, [authFetch, page, search]);

  const getStockClass = (stock: number) => {
    if (stock === 0) return "product-tile--danger";
    if (stock <= 10) return "product-tile--warning";
    return "product-tile--ok";
  };

  return (
    <div className="page inv-page">
      <div className="page-header">
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate("/inventory")}
        >
          <ArrowLeft size={16} /> Back
        </button>
        <h2 className="page-title">Inventory Overview</h2>
      </div>

      <div className="section-header">
        <h3>All Products</h3>
        <input
          type="text"
          className="search-input"
          placeholder="Search products..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
      </div>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : products.length === 0 ? (
        <div className="empty-state">
          <Package size={48} />
          <p>No products found.</p>
        </div>
      ) : (
        <>
          <div className="inv-list-table-wrapper">
            <table className="inv-list-table">
              <thead>
                <tr>
                  <th>Product Name</th>
                  <th>SKU</th>
                  <th className="text-right">Stock</th>
                  <th>UOM</th>
                  <th className="text-right">Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id} className="inv-list-row">
                    <td className="inv-list-name">{p.name}</td>
                    <td>
                      <span className="inv-list-sku">{p.sku_code}</span>
                    </td>
                    <td className="text-right">
                      <span className="inv-list-stock">
                        {p.stock_at_warehouse}
                      </span>
                    </td>
                    <td>{p.uom || "pcs"}</td>
                    <td className="text-right inv-list-price">
                      ₹{Number(p.price).toFixed(2)}
                    </td>
                    <td>
                      <span
                        className={`inv-list-badge ${getStockClass(p.stock_at_warehouse)}`}
                      >
                        {p.stock_at_warehouse === 0
                          ? "Out of Stock"
                          : p.stock_at_warehouse <= 10
                            ? "Low Stock"
                            : "In Stock"}
                      </span>
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
