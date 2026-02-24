import { useEffect, useState, useCallback } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Plus, Filter, ArrowUpCircle, ArrowDownCircle } from "lucide-react";

interface Product {
  id: number;
  name: string;
  sku_code: string;
}

interface Transaction {
  id: number;
  product_id: number;
  product_name: string;
  sku_code: string;
  stock_adjusted: number;
  previous_stock: number;
  current_stock: number;
  transaction_at: string;
  reference_no: string | null;
  reason: string;
  created_by_name: string;
}

const REASON_OPTIONS = [
  "stock_in",
  "stock_out",
  "adjustment",
  "return",
  "damage",
  "transfer",
];

export default function InventoryPage() {
  const { authFetch } = useAuth();

  // Products for dropdown
  const [products, setProducts] = useState<Product[]>([]);

  // Transaction list
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterProduct, setFilterProduct] = useState<string>("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Create form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    product_id: "",
    stock_adjusted: "",
    reason: "stock_in",
    reference_no: "",
  });
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  // Fetch products for dropdown
  useEffect(() => {
    authFetch(`${API}/products?per_page=200`)
      .then((r) => r.json())
      .then((data) => setProducts(data.products || []))
      .catch(console.error);
  }, [authFetch]);

  const fetchTransactions = useCallback(() => {
    setLoading(true);
    let url = `${API}/inventory/transactions?page=${page}&per_page=20`;
    if (filterProduct) url += `&product_id=${filterProduct}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;

    authFetch(url)
      .then((r) => r.json())
      .then((data) => {
        setTransactions(data.transactions || []);
        setTotalPages(data.total_pages || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [authFetch, page, filterProduct, startDate, endDate]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setFormSuccess("");

    if (!form.product_id) {
      setFormError("Select a product");
      return;
    }
    const adj = parseInt(form.stock_adjusted);
    if (isNaN(adj) || adj === 0) {
      setFormError("Stock adjustment must be non-zero");
      return;
    }

    setSaving(true);
    try {
      const res = await authFetch(`${API}/inventory/transactions`, {
        method: "POST",
        body: JSON.stringify({
          product_id: parseInt(form.product_id),
          stock_adjusted: adj,
          reason: form.reason,
          reference_no: form.reference_no || "",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to record transaction");
      }
      const result = await res.json();
      setFormSuccess(
        `Transaction recorded! Stock: ${result.previous_stock} → ${result.current_stock}`,
      );
      setForm({
        product_id: "",
        stock_adjusted: "",
        reason: "stock_in",
        reference_no: "",
      });
      fetchTransactions();
      setTimeout(() => setFormSuccess(""), 4000);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">Inventory Transactions</h2>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          <Plus size={16} /> New Transaction
        </button>
      </div>

      {/* Transaction form */}
      {showForm && (
        <div className="card form-card">
          <h3>Record Stock Adjustment</h3>
          <form onSubmit={handleSubmit} className="inline-form">
            {formError && <div className="alert alert-error">{formError}</div>}
            {formSuccess && (
              <div className="alert alert-success">{formSuccess}</div>
            )}

            <div className="form-row">
              <div className="form-group">
                <label>Product</label>
                <select
                  value={form.product_id}
                  onChange={(e) =>
                    setForm({ ...form, product_id: e.target.value })
                  }
                  required
                >
                  <option value="">Select product...</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku_code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Stock Adjustment</label>
                <input
                  type="number"
                  placeholder="e.g. +50 or -10"
                  value={form.stock_adjusted}
                  onChange={(e) =>
                    setForm({ ...form, stock_adjusted: e.target.value })
                  }
                  required
                />
              </div>

              <div className="form-group">
                <label>Reason</label>
                <select
                  value={form.reason}
                  onChange={(e) => setForm({ ...form, reason: e.target.value })}
                >
                  {REASON_OPTIONS.map((r) => (
                    <option key={r} value={r}>
                      {r.replace("_", " ").toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Reference No.</label>
                <input
                  type="text"
                  placeholder="PO-12345"
                  value={form.reference_no}
                  onChange={(e) =>
                    setForm({ ...form, reference_no: e.target.value })
                  }
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : "Record Transaction"}
            </button>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="filter-bar">
        <Filter size={16} />
        <select
          value={filterProduct}
          onChange={(e) => {
            setFilterProduct(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Products</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.sku_code})
            </option>
          ))}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={(e) => {
            setStartDate(e.target.value);
            setPage(1);
          }}
        />
        <span>to</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => {
            setEndDate(e.target.value);
            setPage(1);
          }}
        />
        {(filterProduct || startDate || endDate) && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setFilterProduct("");
              setStartDate("");
              setEndDate("");
              setPage(1);
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Transaction table */}
      {loading ? (
        <div className="loading">Loading...</div>
      ) : transactions.length === 0 ? (
        <div className="empty-state">
          <p>No transactions found.</p>
        </div>
      ) : (
        <>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Product</th>
                  <th>Adjustment</th>
                  <th>Previous</th>
                  <th>Current</th>
                  <th>Reason</th>
                  <th>Reference</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id}>
                    <td>{new Date(t.transaction_at).toLocaleString()}</td>
                    <td>
                      <div className="td-bold">{t.product_name}</div>
                      <div className="td-sub">{t.sku_code}</div>
                    </td>
                    <td>
                      <span
                        className={`adjustment ${t.stock_adjusted >= 0 ? "adjustment--in" : "adjustment--out"}`}
                      >
                        {t.stock_adjusted >= 0 ? (
                          <ArrowUpCircle size={14} />
                        ) : (
                          <ArrowDownCircle size={14} />
                        )}
                        {t.stock_adjusted >= 0 ? "+" : ""}
                        {t.stock_adjusted}
                      </span>
                    </td>
                    <td>{t.previous_stock}</td>
                    <td className="td-bold">{t.current_stock}</td>
                    <td>
                      <span
                        className={`reason-badge reason-badge--${t.reason}`}
                      >
                        {t.reason.replace("_", " ")}
                      </span>
                    </td>
                    <td>{t.reference_no || "—"}</td>
                    <td>{t.created_by_name}</td>
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
