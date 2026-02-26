// import { useEffect, useState, useCallback } from "react";
// import { useAuth, API } from "../context/AuthContext";
// import {
//   ArrowLeft,
//   ArrowUpCircle,
//   ArrowDownCircle,
//   Package,
//   Warehouse,
//   AlertTriangle,
//   TrendingDown,
//   ClipboardList,
//   Eye,
//   Plus,
//   Filter,
//   ChevronRight,
//   X,
// } from "lucide-react";

// /* ─── Types ──────────────────────────────────────────────────── */

// interface Summary {
//   total_products: number;
//   total_stock: number;
//   out_of_stock: number;
//   low_stock: number;
// }

// interface ProductStock {
//   id: number;
//   name: string;
//   sku_code: string;
//   price: number;
//   stock_at_warehouse: number;
//   updated_at: string;
// }

// interface Batch {
//   id: number;
//   reason: string;
//   reference_no: string | null;
//   notes: string;
//   total_items: number;
//   total_amount: number;
//   transaction_at: string;
//   created_at: string;
//   created_by_name: string;
// }

// interface BatchLineItem {
//   id: number;
//   product_id: number;
//   product_name: string;
//   sku_code: string;
//   price: number;
//   stock_adjusted: number;
//   previous_stock: number;
//   current_stock: number;
// }

// interface BatchDetail extends Batch {
//   items: BatchLineItem[];
// }

// interface Product {
//   id: number;
//   name: string;
//   sku_code: string;
//   price: number;
// }

// type View = "hub" | "overview" | "history";

// const REASON_OPTIONS = [
//   "delivery",
//   "shipment",
//   "adjustment",
//   "return",
//   "damage",
//   "transfer",
// ];

// /* ─── Hub tile data ──────────────────────────────────────────── */

// const HUB_TILES: {
//   key: View;
//   icon: React.ReactNode;
//   title: string;
//   desc: string;
//   color: string;
// }[] = [
//   {
//     key: "overview",
//     icon: <Eye size={28} />,
//     title: "Inventory Overview",
//     desc: "View current stock levels for all products",
//     color: "var(--hub-blue)",
//   },
//   {
//     key: "history",
//     icon: <ClipboardList size={28} />,
//     title: "Inventory History",
//     desc: "Browse batch transactions and detailed line items",
//     color: "var(--hub-purple)",
//   },
// ];

// /* ═══════════════════════════════════════════════════════════════
//    Main component
//    ═══════════════════════════════════════════════════════════════ */

// export default function InventoryPage() {
//   const { authFetch } = useAuth();
//   const [view, setView] = useState<View>("hub");

//   return (
//     <div className="page inv-page">
//       {view === "hub" && <HubView onNav={setView} authFetch={authFetch} />}
//       {view === "overview" && (
//         <OverviewView onBack={() => setView("hub")} authFetch={authFetch} />
//       )}
//       {view === "history" && (
//         <HistoryView onBack={() => setView("hub")} authFetch={authFetch} />
//       )}
//     </div>
//   );
// }

// /* ═══════════════════════════════════════════════════════════════
//    Hub View – tiles
//    ═══════════════════════════════════════════════════════════════ */

// function HubView({
//   onNav,
//   authFetch,
// }: {
//   onNav: (v: View) => void;
//   authFetch: (url: string, init?: RequestInit) => Promise<Response>;
// }) {
//   const [summary, setSummary] = useState<Summary | null>(null);

//   useEffect(() => {
//     authFetch(`${API}/inventory/summary`)
//       .then((r) => r.json())
//       .then(setSummary)
//       .catch(console.error);
//   }, [authFetch]);

//   return (
//     <>
//       <h2 className="page-title">Inventory</h2>

//       {/* Summary cards */}
//       <div className="summary-cards">
//         <div className="summary-card">
//           <div className="summary-card-icon summary-card-icon--blue">
//             <Package size={24} />
//           </div>
//           <div>
//             <div className="summary-card-label">Total Products</div>
//             <div className="summary-card-value">
//               {summary?.total_products ?? "—"}
//             </div>
//           </div>
//         </div>
//         <div className="summary-card">
//           <div className="summary-card-icon summary-card-icon--green">
//             <Warehouse size={24} />
//           </div>
//           <div>
//             <div className="summary-card-label">Total Stock</div>
//             <div className="summary-card-value">
//               {summary?.total_stock ?? "—"}
//             </div>
//           </div>
//         </div>
//         <div className="summary-card">
//           <div className="summary-card-icon summary-card-icon--red">
//             <AlertTriangle size={24} />
//           </div>
//           <div>
//             <div className="summary-card-label">Out of Stock</div>
//             <div className="summary-card-value">
//               {summary?.out_of_stock ?? "—"}
//             </div>
//           </div>
//         </div>
//         <div className="summary-card">
//           <div className="summary-card-icon summary-card-icon--yellow">
//             <TrendingDown size={24} />
//           </div>
//           <div>
//             <div className="summary-card-label">Low Stock</div>
//             <div className="summary-card-value">
//               {summary?.low_stock ?? "—"}
//             </div>
//           </div>
//         </div>
//       </div>

//       {/* Navigation tiles */}
//       <div className="inv-hub-tiles">
//         {HUB_TILES.map((t) => (
//           <button
//             key={t.key}
//             className="inv-hub-tile"
//             onClick={() => onNav(t.key)}
//           >
//             <div className="inv-hub-tile__icon" style={{ background: t.color }}>
//               {t.icon}
//             </div>
//             <div className="inv-hub-tile__body">
//               <span className="inv-hub-tile__title">{t.title}</span>
//               <span className="inv-hub-tile__desc">{t.desc}</span>
//             </div>
//             <ChevronRight size={20} className="inv-hub-tile__arrow" />
//           </button>
//         ))}
//       </div>
//     </>
//   );
// }

// /* ═══════════════════════════════════════════════════════════════
//    Overview View – product stock tiles
//    ═══════════════════════════════════════════════════════════════ */

// function OverviewView({
//   onBack,
//   authFetch,
// }: {
//   onBack: () => void;
//   authFetch: (url: string, init?: RequestInit) => Promise<Response>;
// }) {
//   const [products, setProducts] = useState<ProductStock[]>([]);
//   const [page, setPage] = useState(1);
//   const [totalPages, setTotalPages] = useState(0);
//   const [search, setSearch] = useState("");
//   const [loading, setLoading] = useState(true);

//   useEffect(() => {
//     let cancelled = false;
//     const load = async () => {
//       try {
//         const r = await authFetch(
//           `${API}/inventory/overview?page=${page}&per_page=18&search=${encodeURIComponent(search)}`,
//         );
//         const data = await r.json();
//         if (!cancelled) {
//           setProducts(data.products || []);
//           setTotalPages(data.total_pages || 0);
//         }
//       } catch (err) {
//         console.error(err);
//       } finally {
//         if (!cancelled) setLoading(false);
//       }
//     };
//     setLoading(true);
//     load();
//     return () => {
//       cancelled = true;
//     };
//   }, [authFetch, page, search]);

//   const getStockClass = (stock: number) => {
//     if (stock === 0) return "product-tile--danger";
//     if (stock <= 10) return "product-tile--warning";
//     return "product-tile--ok";
//   };

//   return (
//     <>
//       <div className="page-header">
//         <button className="btn btn-secondary btn-sm" onClick={onBack}>
//           <ArrowLeft size={16} /> Back
//         </button>
//         <h2 className="page-title">Inventory Overview</h2>
//       </div>

//       <div className="section-header">
//         <h3>All Products</h3>
//         <input
//           type="text"
//           className="search-input"
//           placeholder="Search products..."
//           value={search}
//           onChange={(e) => {
//             setSearch(e.target.value);
//             setPage(1);
//           }}
//         />
//       </div>

//       {loading ? (
//         <div className="loading">Loading...</div>
//       ) : products.length === 0 ? (
//         <div className="empty-state">
//           <Package size={48} />
//           <p>No products found.</p>
//         </div>
//       ) : (
//         <>
//           <div className="product-tiles">
//             {products.map((p) => (
//               <div
//                 key={p.id}
//                 className={`product-tile ${getStockClass(p.stock_at_warehouse)}`}
//               >
//                 <div className="product-tile-header">
//                   <span className="product-tile-name">{p.name}</span>
//                   <span className="product-tile-sku">{p.sku_code}</span>
//                 </div>
//                 <div className="product-tile-stock">{p.stock_at_warehouse}</div>
//                 <div className="product-tile-label">units in stock</div>
//                 <div className="product-tile-price">
//                   ${Number(p.price).toFixed(2)}
//                 </div>
//               </div>
//             ))}
//           </div>

//           {totalPages > 1 && (
//             <div className="pagination">
//               <button
//                 disabled={page <= 1}
//                 onClick={() => setPage((p) => p - 1)}
//               >
//                 Previous
//               </button>
//               <span>
//                 Page {page} of {totalPages}
//               </span>
//               <button
//                 disabled={page >= totalPages}
//                 onClick={() => setPage((p) => p + 1)}
//               >
//                 Next
//               </button>
//             </div>
//           )}
//         </>
//       )}
//     </>
//   );
// }

// /* ═══════════════════════════════════════════════════════════════
//    History View – split pane (batch list + detail)
//    ═══════════════════════════════════════════════════════════════ */

// function HistoryView({
//   onBack,
//   authFetch,
// }: {
//   onBack: () => void;
//   authFetch: (url: string, init?: RequestInit) => Promise<Response>;
// }) {
//   const [batches, setBatches] = useState<Batch[]>([]);
//   const [page, setPage] = useState(1);
//   const [totalPages, setTotalPages] = useState(0);
//   const [loading, setLoading] = useState(true);

//   // Filters
//   const [filterReason, setFilterReason] = useState("");
//   const [startDate, setStartDate] = useState("");
//   const [endDate, setEndDate] = useState("");

//   // Detail pane
//   const [selectedBatch, setSelectedBatch] = useState<BatchDetail | null>(null);
//   const [detailLoading, setDetailLoading] = useState(false);

//   // Create form
//   const [showForm, setShowForm] = useState(false);

//   const fetchBatches = useCallback(() => {
//     setLoading(true);
//     let url = `${API}/inventory/batches?page=${page}&per_page=15`;
//     if (filterReason) url += `&reason=${filterReason}`;
//     if (startDate) url += `&start_date=${startDate}`;
//     if (endDate) url += `&end_date=${endDate}`;

//     authFetch(url)
//       .then((r) => r.json())
//       .then((data) => {
//         setBatches(data.batches || []);
//         setTotalPages(data.total_pages || 0);
//       })
//       .catch(console.error)
//       .finally(() => setLoading(false));
//   }, [authFetch, page, filterReason, startDate, endDate]);

//   useEffect(() => {
//     fetchBatches();
//   }, [fetchBatches]);

//   const loadDetail = async (batchId: number) => {
//     setDetailLoading(true);
//     try {
//       const res = await authFetch(`${API}/inventory/batches/${batchId}`);
//       const data = await res.json();
//       setSelectedBatch(data);
//     } catch (err) {
//       console.error(err);
//     } finally {
//       setDetailLoading(false);
//     }
//   };

//   return (
//     <>
//       <div className="page-header">
//         <button className="btn btn-secondary btn-sm" onClick={onBack}>
//           <ArrowLeft size={16} /> Back
//         </button>
//         <h2 className="page-title">Inventory History</h2>
//       </div>

//       {showForm && (
//         <BatchForm
//           authFetch={authFetch}
//           onClose={() => setShowForm(false)}
//           onCreated={() => {
//             setShowForm(false);
//             fetchBatches();
//           }}
//         />
//       )}

//       {/* Filters */}
//       <div className="filter-bar">
//         <Filter size={16} />
//         <select
//           value={filterReason}
//           onChange={(e) => {
//             setFilterReason(e.target.value);
//             setPage(1);
//           }}
//         >
//           <option value="">All Reasons</option>
//           {REASON_OPTIONS.map((r) => (
//             <option key={r} value={r}>
//               {r.charAt(0).toUpperCase() + r.slice(1)}
//             </option>
//           ))}
//         </select>
//         <input
//           type="date"
//           value={startDate}
//           onChange={(e) => {
//             setStartDate(e.target.value);
//             setPage(1);
//           }}
//         />
//         <span>to</span>
//         <input
//           type="date"
//           value={endDate}
//           onChange={(e) => {
//             setEndDate(e.target.value);
//             setPage(1);
//           }}
//         />
//         {(filterReason || startDate || endDate) && (
//           <button
//             className="btn btn-secondary btn-sm"
//             onClick={() => {
//               setFilterReason("");
//               setStartDate("");
//               setEndDate("");
//               setPage(1);
//             }}
//           >
//             Clear
//           </button>
//         )}
//       </div>

//       {/* Split pane */}
//       <div className="inv-split">
//         {/* Left: batch list */}
//         <div className="inv-split__list">
//           {loading ? (
//             <div className="loading">Loading...</div>
//           ) : batches.length === 0 ? (
//             <div className="empty-state">
//               <ClipboardList size={40} />
//               <p>No batch transactions yet.</p>
//             </div>
//           ) : (
//             <>
//               {batches.map((b) => (
//                 <button
//                   key={b.id}
//                   className={`inv-batch-card${selectedBatch?.id === b.id ? " inv-batch-card--active" : ""}`}
//                   onClick={() => loadDetail(b.id)}
//                 >
//                   <div className="inv-batch-card__top">
//                     <span className={`reason-badge reason-badge--${b.reason}`}>
//                       {b.reason.replace("_", " ")}
//                     </span>
//                     <span className="inv-batch-card__date">
//                       {new Date(b.transaction_at).toLocaleDateString()}
//                     </span>
//                   </div>
//                   <div className="inv-batch-card__mid">
//                     <span className="inv-batch-card__ref">
//                       {b.reference_no || "No reference"}
//                     </span>
//                     <span className="inv-batch-card__by">
//                       {b.created_by_name}
//                     </span>
//                   </div>
//                   <div className="inv-batch-card__bot">
//                     <span>{b.total_items} items</span>
//                     <span className="inv-batch-card__amount">
//                       ${Number(b.total_amount).toFixed(2)}
//                     </span>
//                   </div>
//                 </button>
//               ))}

//               {totalPages > 1 && (
//                 <div className="pagination" style={{ padding: "12px 0" }}>
//                   <button
//                     disabled={page <= 1}
//                     onClick={() => setPage((p) => p - 1)}
//                   >
//                     Prev
//                   </button>
//                   <span>
//                     {page}/{totalPages}
//                   </span>
//                   <button
//                     disabled={page >= totalPages}
//                     onClick={() => setPage((p) => p + 1)}
//                   >
//                     Next
//                   </button>
//                 </div>
//               )}
//             </>
//           )}
//         </div>

//         {/* Right: detail pane */}
//         <div className="inv-split__detail">
//           {detailLoading ? (
//             <div className="loading">Loading details...</div>
//           ) : selectedBatch ? (
//             <BatchDetailPane batch={selectedBatch} />
//           ) : (
//             <div className="inv-split__placeholder">
//               <ClipboardList size={48} strokeWidth={1.2} />
//               <p>Select a transaction to view details</p>
//             </div>
//           )}
//         </div>
//       </div>
//     </>
//   );
// }

// /* ─── Batch Detail Pane ──────────────────────────────────────── */

// function BatchDetailPane({ batch }: { batch: BatchDetail }) {
//   return (
//     <div className="inv-detail">
//       <div className="inv-detail__header">
//         <div>
//           <span className={`reason-badge reason-badge--${batch.reason}`}>
//             {batch.reason.replace("_", " ")}
//           </span>
//           <h3 className="inv-detail__title">
//             {batch.reference_no || "No Reference"}
//           </h3>
//         </div>
//         <span className="inv-detail__date">
//           {new Date(batch.transaction_at).toLocaleString()}
//         </span>
//       </div>

//       {/* Summary row */}
//       <div className="inv-detail__summary">
//         <div className="inv-detail__stat">
//           <span className="inv-detail__stat-label">Total Items</span>
//           <span className="inv-detail__stat-value">{batch.total_items}</span>
//         </div>
//         <div className="inv-detail__stat">
//           <span className="inv-detail__stat-label">Total Amount</span>
//           <span className="inv-detail__stat-value">
//             ${Number(batch.total_amount).toFixed(2)}
//           </span>
//         </div>
//         <div className="inv-detail__stat">
//           <span className="inv-detail__stat-label">Products</span>
//           <span className="inv-detail__stat-value">{batch.items.length}</span>
//         </div>
//         <div className="inv-detail__stat">
//           <span className="inv-detail__stat-label">Created By</span>
//           <span className="inv-detail__stat-value">
//             {batch.created_by_name}
//           </span>
//         </div>
//       </div>

//       {batch.notes && (
//         <div className="inv-detail__notes">
//           <strong>Notes:</strong> {batch.notes}
//         </div>
//       )}

//       {/* Line items table */}
//       <h4 className="inv-detail__section-title">Line Items</h4>
//       <div className="table-wrapper">
//         <table>
//           <thead>
//             <tr>
//               <th>Product</th>
//               <th>Adjustment</th>
//               <th>Before</th>
//               <th>After</th>
//               <th>Value</th>
//             </tr>
//           </thead>
//           <tbody>
//             {batch.items.map((item) => (
//               <tr key={item.id}>
//                 <td>
//                   <div className="td-bold">{item.product_name}</div>
//                   <div className="td-sub">{item.sku_code}</div>
//                 </td>
//                 <td>
//                   <span
//                     className={`adjustment ${item.stock_adjusted >= 0 ? "adjustment--in" : "adjustment--out"}`}
//                   >
//                     {item.stock_adjusted >= 0 ? (
//                       <ArrowUpCircle size={14} />
//                     ) : (
//                       <ArrowDownCircle size={14} />
//                     )}
//                     {item.stock_adjusted >= 0 ? "+" : ""}
//                     {item.stock_adjusted}
//                   </span>
//                 </td>
//                 <td>{item.previous_stock}</td>
//                 <td className="td-bold">{item.current_stock}</td>
//                 <td>
//                   ${(Math.abs(item.stock_adjusted) * item.price).toFixed(2)}
//                 </td>
//               </tr>
//             ))}
//           </tbody>
//         </table>
//       </div>
//     </div>
//   );
// }

// /* ─── Batch Creation Form ────────────────────────────────────── */

// function BatchForm({
//   authFetch,
//   onClose,
//   onCreated,
// }: {
//   authFetch: (url: string, init?: RequestInit) => Promise<Response>;
//   onClose: () => void;
//   onCreated: () => void;
// }) {
//   const [products, setProducts] = useState<Product[]>([]);
//   const [reason, setReason] = useState("delivery");
//   const [referenceNo, setReferenceNo] = useState("");
//   const [notes, setNotes] = useState("");
//   const [items, setItems] = useState<
//     { product_id: string; stock_adjusted: string }[]
//   >([{ product_id: "", stock_adjusted: "" }]);
//   const [error, setError] = useState("");
//   const [saving, setSaving] = useState(false);

//   useEffect(() => {
//     authFetch(`${API}/products?per_page=200`)
//       .then((r) => r.json())
//       .then((data) => setProducts(data.products || []))
//       .catch(console.error);
//   }, [authFetch]);

//   const addLine = () =>
//     setItems([...items, { product_id: "", stock_adjusted: "" }]);

//   const removeLine = (idx: number) => {
//     if (items.length <= 1) return;
//     setItems(items.filter((_, i) => i !== idx));
//   };

//   const updateLine = (
//     idx: number,
//     field: "product_id" | "stock_adjusted",
//     value: string,
//   ) => {
//     const copy = [...items];
//     copy[idx] = { ...copy[idx], [field]: value };
//     setItems(copy);
//   };

//   const handleSubmit = async (e: React.FormEvent) => {
//     e.preventDefault();
//     setError("");

//     const parsed = items
//       .filter((i) => i.product_id && i.stock_adjusted)
//       .map((i) => ({
//         product_id: parseInt(i.product_id),
//         stock_adjusted: parseInt(i.stock_adjusted),
//       }));

//     if (parsed.length === 0) {
//       setError("Add at least one product with a stock adjustment");
//       return;
//     }
//     if (parsed.some((p) => isNaN(p.stock_adjusted) || p.stock_adjusted === 0)) {
//       setError("Each line must have a non-zero adjustment");
//       return;
//     }

//     setSaving(true);
//     try {
//       const res = await authFetch(`${API}/inventory/batches`, {
//         method: "POST",
//         body: JSON.stringify({
//           reason,
//           reference_no: referenceNo,
//           notes,
//           items: parsed,
//         }),
//       });
//       if (!res.ok) {
//         const err = await res.json().catch(() => ({}));
//         throw new Error(err.detail || "Failed to create batch");
//       }
//       onCreated();
//     } catch (err: unknown) {
//       setError(err instanceof Error ? err.message : "Error");
//     } finally {
//       setSaving(false);
//     }
//   };

//   return (
//     <div className="card form-card inv-batch-form">
//       <div className="inv-batch-form__header">
//         <h3>New Batch Transaction</h3>
//         <button className="btn-icon" onClick={onClose}>
//           <X size={18} />
//         </button>
//       </div>

//       <form onSubmit={handleSubmit}>
//         {error && <div className="alert alert-error">{error}</div>}

//         <div className="form-row">
//           <div className="form-group">
//             <label>Reason</label>
//             <select value={reason} onChange={(e) => setReason(e.target.value)}>
//               {REASON_OPTIONS.map((r) => (
//                 <option key={r} value={r}>
//                   {r.charAt(0).toUpperCase() + r.slice(1)}
//                 </option>
//               ))}
//             </select>
//           </div>
//           <div className="form-group">
//             <label>Reference / Invoice No.</label>
//             <input
//               type="text"
//               placeholder="INV-2026-001"
//               value={referenceNo}
//               onChange={(e) => setReferenceNo(e.target.value)}
//             />
//           </div>
//           <div className="form-group">
//             <label>Notes</label>
//             <input
//               type="text"
//               placeholder="Optional notes..."
//               value={notes}
//               onChange={(e) => setNotes(e.target.value)}
//             />
//           </div>
//         </div>

//         <h4 style={{ margin: "8px 0 12px", fontSize: "0.9rem" }}>Line Items</h4>

//         <div className="inv-line-items">
//           {items.map((item, idx) => (
//             <div key={idx} className="inv-line-item">
//               <select
//                 value={item.product_id}
//                 onChange={(e) => updateLine(idx, "product_id", e.target.value)}
//                 required
//               >
//                 <option value="">Select product...</option>
//                 {products.map((p) => (
//                   <option key={p.id} value={p.id}>
//                     {p.name} ({p.sku_code})
//                   </option>
//                 ))}
//               </select>
//               <input
//                 type="number"
//                 placeholder="e.g. +50 or -10"
//                 value={item.stock_adjusted}
//                 onChange={(e) =>
//                   updateLine(idx, "stock_adjusted", e.target.value)
//                 }
//                 required
//               />
//               <button
//                 type="button"
//                 className="btn-icon btn-icon--danger"
//                 title="Remove"
//                 onClick={() => removeLine(idx)}
//                 disabled={items.length <= 1}
//               >
//                 <X size={16} />
//               </button>
//             </div>
//           ))}
//         </div>

//         <button
//           type="button"
//           className="btn btn-secondary btn-sm"
//           onClick={addLine}
//           style={{ marginTop: 8 }}
//         >
//           <Plus size={14} /> Add Line
//         </button>

//         <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
//           <button type="submit" className="btn btn-primary" disabled={saving}>
//             {saving ? "Saving..." : "Create Batch Transaction"}
//           </button>
//           <button type="button" className="btn btn-secondary" onClick={onClose}>
//             Cancel
//           </button>
//         </div>
//       </form>
//     </div>
//   );
// }

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth, API } from "../context/AuthContext";
import {
  Package,
  Warehouse,
  AlertTriangle,
  TrendingDown,
  Eye,
  ClipboardList,
  ChevronRight,
} from "lucide-react";

interface Summary {
  total_products: number;
  total_stock: number;
  out_of_stock: number;
  low_stock: number;
}

export default function InventoryPage() {
  const { authFetch } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    authFetch(`${API}/inventory/summary`)
      .then((r) => r.json())
      .then(setSummary)
      .catch(console.error);
  }, [authFetch]);

  return (
    <div className="page inv-page">
      <h2 className="page-title">Inventory</h2>

      {/* Summary cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-card-icon summary-card-icon--blue">
            <Package size={24} />
          </div>
          <div>
            <div className="summary-card-label">Total Products</div>
            <div className="summary-card-value">
              {summary?.total_products ?? "\u2014"}
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
              {summary?.total_stock ?? "\u2014"}
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
              {summary?.out_of_stock ?? "\u2014"}
            </div>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-card-icon summary-card-icon--yellow">
            {" "}
            <TrendingDown size={24} />
          </div>
          <div>
            <div className="summary-card-label">Low Stock</div>
            <div className="summary-card-value">
              {summary?.low_stock ?? "\u2014"}
            </div>
          </div>
        </div>
      </div>

      {/* Navigation tiles */}
      <div className="inv-hub-tiles">
        <Link to="/inventory/overview" className="inv-hub-tile">
          <div
            className="inv-hub-tile__icon"
            style={{ background: "var(--hub-blue)" }}
          >
            <Eye size={28} />
          </div>
          <div className="inv-hub-tile__body">
            <span className="inv-hub-tile__title">Inventory Overview</span>
            <span className="inv-hub-tile__desc">
              View current stock levels for all products
            </span>
          </div>
          <ChevronRight size={20} className="inv-hub-tile__arrow" />
        </Link>

        <Link to="/inventory/history" className="inv-hub-tile">
          <div
            className="inv-hub-tile__icon"
            style={{ background: "var(--hub-purple)" }}
          >
            <ClipboardList size={28} />
          </div>
          <div className="inv-hub-tile__body">
            <span className="inv-hub-tile__title">Inventory History</span>
            <span className="inv-hub-tile__desc">
              Browse batch transactions and detailed line items
            </span>
          </div>
          <ChevronRight size={20} className="inv-hub-tile__arrow" />
        </Link>
      </div>
    </div>
  );
}
