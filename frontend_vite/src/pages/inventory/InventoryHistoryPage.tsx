import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import {
  ArrowLeft,
  ArrowUpCircle,
  ArrowDownCircle,
  ClipboardList,
  Filter,
} from "lucide-react";

/* ─── Types ──────────────────────────────────────────────────── */

interface Batch {
  id: number;
  reason: string;
  reference_no: string | null;
  notes: string;
  total_items: number;
  total_amount: number;
  transaction_at: string;
  created_at: string;
  created_by_name: string;
}

interface BatchLineItem {
  id: number;
  product_id: number;
  product_name: string;
  sku_code: string;
  price: number;
  stock_adjusted: number;
  previous_stock: number;
  current_stock: number;
}

interface BatchDetail extends Batch {
  items: BatchLineItem[];
}

const REASON_OPTIONS = [
  "delivery",
  "shipment",
  "adjustment",
  "return",
  "damage",
  "transfer",
];

/* ═══════════════════════════════════════════════════════════════
   Inventory History Page
   ═══════════════════════════════════════════════════════════════ */

export default function InventoryHistoryPage() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();

  const [batches, setBatches] = useState<Batch[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterReason, setFilterReason] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // Detail pane
  const [selectedBatch, setSelectedBatch] = useState<BatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Create form

  const fetchBatches = useCallback(() => {
    setLoading(true);
    let url = `${API}/inventory/batches?page=${page}&per_page=15`;
    if (filterReason) url += `&reason=${filterReason}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;

    authFetch(url)
      .then((r) => r.json())
      .then((data) => {
        setBatches(data.batches || []);
        setTotalPages(data.total_pages || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [authFetch, page, filterReason, startDate, endDate]);

  useEffect(() => {
    fetchBatches();
  }, [fetchBatches]);

  const loadDetail = async (batchId: number) => {
    setDetailLoading(true);
    try {
      const res = await authFetch(`${API}/inventory/batches/${batchId}`);
      const data = await res.json();
      setSelectedBatch(data);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
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
        <h2 className="page-title">Inventory History</h2>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <Filter size={16} />
        <select
          value={filterReason}
          onChange={(e) => {
            setFilterReason(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Reasons</option>
          {REASON_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r.charAt(0).toUpperCase() + r.slice(1)}
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
        {(filterReason || startDate || endDate) && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setFilterReason("");
              setStartDate("");
              setEndDate("");
              setPage(1);
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Split pane */}
      <div className="inv-split">
        {/* Left: batch list */}
        <div className="inv-split__list">
          {loading ? (
            <div className="loading">Loading...</div>
          ) : batches.length === 0 ? (
            <div className="empty-state">
              <ClipboardList size={40} />
              <p>No batch transactions yet.</p>
            </div>
          ) : (
            <>
              {batches.map((b) => (
                <button
                  key={b.id}
                  className={`inv-batch-card${selectedBatch?.id === b.id ? " inv-batch-card--active" : ""}`}
                  onClick={() => loadDetail(b.id)}
                >
                  <div className="inv-batch-card__top">
                    <span className={`reason-badge reason-badge--${b.reason}`}>
                      {b.reason.replace("_", " ")}
                    </span>
                    <span className="inv-batch-card__date">
                      {new Date(b.transaction_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="inv-batch-card__mid">
                    <span className="inv-batch-card__ref">
                      {b.reference_no || "No reference"}
                    </span>
                    <span className="inv-batch-card__by">
                      {b.created_by_name}
                    </span>
                  </div>
                  <div className="inv-batch-card__bot">
                    <span>{b.total_items} items</span>
                    <span className="inv-batch-card__amount">
                      ${Number(b.total_amount).toFixed(2)}
                    </span>
                  </div>
                </button>
              ))}

              {totalPages > 1 && (
                <div className="pagination" style={{ padding: "12px 0" }}>
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Prev
                  </button>
                  <span>
                    {page}/{totalPages}
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

        {/* Right: detail pane */}
        <div className="inv-split__detail">
          {detailLoading ? (
            <div className="loading">Loading details...</div>
          ) : selectedBatch ? (
            <BatchDetailPane batch={selectedBatch} />
          ) : (
            <div className="inv-split__placeholder">
              <ClipboardList size={48} strokeWidth={1.2} />
              <p>Select a transaction to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Batch Detail Pane ──────────────────────────────────────── */

function BatchDetailPane({ batch }: { batch: BatchDetail }) {
  return (
    <div className="inv-detail">
      <div className="inv-detail__header">
        <div>
          <span className={`reason-badge reason-badge--${batch.reason}`}>
            {batch.reason.replace("_", " ")}
          </span>
          <h3 className="inv-detail__title">
            {batch.reference_no || "No Reference"}
          </h3>
        </div>
        <span className="inv-detail__date">
          {new Date(batch.transaction_at).toLocaleString()}
        </span>
      </div>

      {/* Summary row */}
      <div className="inv-detail__summary">
        <div className="inv-detail__stat">
          <span className="inv-detail__stat-label">Total Items</span>
          <span className="inv-detail__stat-value">{batch.total_items}</span>
        </div>
        <div className="inv-detail__stat">
          <span className="inv-detail__stat-label">Total Amount</span>
          <span className="inv-detail__stat-value">
            ${Number(batch.total_amount).toFixed(2)}
          </span>
        </div>
        <div className="inv-detail__stat">
          <span className="inv-detail__stat-label">Products</span>
          <span className="inv-detail__stat-value">{batch.items.length}</span>
        </div>
        <div className="inv-detail__stat">
          <span className="inv-detail__stat-label">Created By</span>
          <span className="inv-detail__stat-value">
            {batch.created_by_name}
          </span>
        </div>
      </div>

      {batch.notes && (
        <div className="inv-detail__notes">
          <strong>Notes:</strong> {batch.notes}
        </div>
      )}

      {/* Line items table */}
      <h4 className="inv-detail__section-title">Line Items</h4>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Adjustment</th>
              <th>Before</th>
              <th>After</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {batch.items.map((item) => (
              <tr key={item.id}>
                <td>
                  <div className="td-bold">{item.product_name}</div>
                  <div className="td-sub">{item.sku_code}</div>
                </td>
                <td>
                  <span
                    className={`adjustment ${item.stock_adjusted >= 0 ? "adjustment--in" : "adjustment--out"}`}
                  >
                    {item.stock_adjusted >= 0 ? (
                      <ArrowUpCircle size={14} />
                    ) : (
                      <ArrowDownCircle size={14} />
                    )}
                    {item.stock_adjusted >= 0 ? "+" : ""}
                    {item.stock_adjusted}
                  </span>
                </td>
                <td>{item.previous_stock}</td>
                <td className="td-bold">{item.current_stock}</td>
                <td>
                  ${(Math.abs(item.stock_adjusted) * item.price).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
