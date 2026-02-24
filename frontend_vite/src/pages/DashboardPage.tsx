import { useEffect, useState } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Package, Warehouse, AlertTriangle, TrendingDown } from "lucide-react";

interface Summary {
  total_products: number;
  total_stock: number;
  out_of_stock: number;
  low_stock: number;
}

interface ProductStock {
  id: number;
  name: string;
  sku_code: string;
  price: number;
  stock_at_warehouse: number;
  updated_at: string;
}

export default function DashboardPage() {
  const { authFetch } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [products, setProducts] = useState<ProductStock[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authFetch(`${API}/inventory/summary`)
      .then((r) => r.json())
      .then(setSummary)
      .catch(console.error);
  }, [authFetch]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await authFetch(
          `${API}/inventory/overview?page=${page}&per_page=12&search=${encodeURIComponent(search)}`,
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
    if (stock === 0) return "tile--danger";
    if (stock <= 10) return "tile--warning";
    return "tile--ok";
  };

  return (
    <div className="page">
      <h2 className="page-title">Dashboard</h2>

      {/* Summary cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-card-icon summary-card-icon--blue">
            <Package size={24} />
          </div>
          <div>
            <div className="summary-card-label">Total Products</div>
            <div className="summary-card-value">
              {summary?.total_products ?? "—"}
            </div>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-card-icon summary-card-icon--green">
            <Warehouse size={24} />
          </div>
          <div>
            <div className="summary-card-label">Total Stock</div>
            <div className="summary-card-value">
              {summary?.total_stock ?? "—"}
            </div>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-card-icon summary-card-icon--red">
            <AlertTriangle size={24} />
          </div>
          <div>
            <div className="summary-card-label">Out of Stock</div>
            <div className="summary-card-value">
              {summary?.out_of_stock ?? "—"}
            </div>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-card-icon summary-card-icon--yellow">
            <TrendingDown size={24} />
          </div>
          <div>
            <div className="summary-card-label">Low Stock</div>
            <div className="summary-card-value">
              {summary?.low_stock ?? "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Inventory overview tiles */}
      <div className="section-header">
        <h3>Inventory Overview</h3>
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
          <p>No products found. Add products from the Products module.</p>
        </div>
      ) : (
        <>
          <div className="product-tiles">
            {products.map((p) => (
              <div
                key={p.id}
                className={`product-tile ${getStockClass(p.stock_at_warehouse)}`}
              >
                <div className="product-tile-header">
                  <span className="product-tile-name">{p.name}</span>
                  <span className="product-tile-sku">{p.sku_code}</span>
                </div>
                <div className="product-tile-stock">{p.stock_at_warehouse}</div>
                <div className="product-tile-label">units in stock</div>
                <div className="product-tile-price">
                  ${Number(p.price).toFixed(2)}
                </div>
              </div>
            ))}
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
