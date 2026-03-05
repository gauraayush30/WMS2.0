import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import {
  ArrowLeft,
  Plus,
  Upload,
  Download,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Trash2,
} from "lucide-react";

/* ── Types ──────────────────────────────────────────────────── */
interface CsvRow {
  row: number;
  name: string;
  sku_code: string;
  price: string;
  stock_at_warehouse: string;
  uom: string;
  errors: string[];
}

interface BulkResultItem {
  row: number;
  name: string;
  sku_code: string;
  status: "created" | "error";
  message?: string;
}

/* ── Constants ──────────────────────────────────────────────── */
const SAMPLE_CSV = `name,sku_code,price,stock_at_warehouse,uom
Widget Alpha,SKU-001,29.99,100,pcs
Widget Beta,SKU-002,14.50,250,kg
Widget Gamma,SKU-003,5.00,0,litre`;

export default function CreateProduct() {
  const { authFetch } = useAuth();
  const navigate = useNavigate();

  /* ── Single product form state ────────────────────────────── */
  const [form, setForm] = useState({
    name: "",
    sku_code: "",
    price: "0",
    stock_at_warehouse: "0",
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

  /* ── Bulk CSV state ───────────────────────────────────────── */
  const [activeTab, setActiveTab] = useState<"single" | "bulk">("single");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [csvRows, setCsvRows] = useState<CsvRow[]>([]);
  const [bulkResults, setBulkResults] = useState<BulkResultItem[]>([]);
  const [bulkError, setBulkError] = useState("");
  const [bulkUploading, setBulkUploading] = useState(false);
  const [fileName, setFileName] = useState("");

  /* ── Handlers: single product ─────────────────────────────── */
  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setFormSuccess("");
    if (!form.name.trim() || !form.sku_code.trim()) {
      setFormError("Name and SKU Code are required");
      return;
    }
    setSaving(true);
    try {
      const res = await authFetch(`${API}/products`, {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          sku_code: form.sku_code.trim(),
          price: parseFloat(form.price) || 0,
          stock_at_warehouse: parseInt(form.stock_at_warehouse) || 0,
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
        throw new Error(err.detail || "Failed to create product");
      }
      setFormSuccess(`Product "${form.name.trim()}" created successfully!`);
      setForm({
        name: "",
        sku_code: "",
        price: "0",
        stock_at_warehouse: "0",
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
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  /* ── Handlers: CSV ────────────────────────────────────────── */
  const downloadSample = () => {
    const blob = new Blob([SAMPLE_CSV], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "products_sample.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const parseCsv = async (text: string): Promise<CsvRow[]> => {
    const lines = text
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length < 2) return [];

    const header = lines[0]
      .toLowerCase()
      .split(",")
      .map((h) => h.trim());
    const nameIdx = header.indexOf("name");
    const skuIdx = header.indexOf("sku_code");
    const priceIdx = header.indexOf("price");
    const stockIdx = header.indexOf("stock_at_warehouse");
    const uomIdx = header.indexOf("uom");

    if (nameIdx === -1 || skuIdx === -1) {
      setBulkError(
        'CSV must have "name" and "sku_code" columns. Download the sample for reference.',
      );
      return [];
    }

    const rows: CsvRow[] = [];
    const allSkus: string[] = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",").map((c) => c.trim());
      const name = cols[nameIdx] || "";
      const sku_code = cols[skuIdx] || "";
      const price = priceIdx !== -1 ? cols[priceIdx] || "0" : "0";
      const stock = stockIdx !== -1 ? cols[stockIdx] || "0" : "0";
      const uom = uomIdx !== -1 ? cols[uomIdx] || "pcs" : "pcs";
      const errors: string[] = [];

      if (!name) errors.push("Name is required");
      if (!sku_code) errors.push("SKU Code is required");
      if (priceIdx !== -1 && price && isNaN(Number(price)))
        errors.push("Price must be a number");
      if (priceIdx !== -1 && Number(price) < 0)
        errors.push("Price cannot be negative");
      if (stockIdx !== -1 && stock && isNaN(Number(stock)))
        errors.push("Stock must be a number");
      if (stockIdx !== -1 && Number(stock) < 0)
        errors.push("Stock cannot be negative");

      if (sku_code) allSkus.push(sku_code);
      rows.push({
        row: i + 1,
        name,
        sku_code,
        price,
        stock_at_warehouse: stock,
        uom,
        errors,
      });
    }

    // Check for duplicate SKUs within CSV
    const skuMap = new Map<string, number[]>();
    rows.forEach((r) => {
      if (r.sku_code) {
        const key = r.sku_code.toLowerCase();
        if (!skuMap.has(key)) skuMap.set(key, []);
        skuMap.get(key)!.push(r.row);
      }
    });
    skuMap.forEach((rowNums, sku) => {
      if (rowNums.length > 1) {
        rows
          .filter((r) => r.sku_code.toLowerCase() === sku)
          .forEach((r) =>
            r.errors.push(`Duplicate SKU "${r.sku_code}" in CSV`),
          );
      }
    });

    // Check which SKUs already exist in the database
    if (allSkus.length > 0) {
      try {
        const res = await authFetch(`${API}/products/check-skus`, {
          method: "POST",
          body: JSON.stringify({ sku_codes: allSkus }),
        });
        if (res.ok) {
          const data = await res.json();
          const existingSet = new Set(
            (data.existing as string[]).map((s) => s.toLowerCase()),
          );
          rows.forEach((r) => {
            if (r.sku_code && existingSet.has(r.sku_code.toLowerCase())) {
              r.errors.push("SKU Code already exists in database");
            }
          });
        }
      } catch {
        // If the check fails, let the server-side catch it during creation
      }
    }

    return rows;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setBulkError("");
    setBulkResults([]);
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".csv")) {
      setBulkError("Please upload a .csv file");
      return;
    }

    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = async (ev) => {
      const text = ev.target?.result as string;
      const rows = await parseCsv(text);
      setCsvRows(rows);
    };
    reader.readAsText(file);
    // Reset so user can re-upload the same file
    e.target.value = "";
  };

  const removeRow = (rowNum: number) => {
    setCsvRows((prev) => prev.filter((r) => r.row !== rowNum));
  };

  const handleBulkUpload = async () => {
    if (csvRows.length === 0) return;
    const hasErrors = csvRows.some((r) => r.errors.length > 0);
    if (hasErrors) {
      setBulkError("Fix all validation errors before uploading");
      return;
    }

    setBulkUploading(true);
    setBulkError("");
    setBulkResults([]);

    try {
      const products = csvRows.map((r) => ({
        name: r.name,
        sku_code: r.sku_code,
        price: parseFloat(r.price) || 0,
        stock_at_warehouse: parseInt(r.stock_at_warehouse) || 0,
        uom: r.uom || "pcs",
      }));

      const res = await authFetch(`${API}/products/bulk`, {
        method: "POST",
        body: JSON.stringify({ products }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Bulk upload failed");
      }

      const data = await res.json();
      setBulkResults(data.results || []);
      // Clear csvRows on success
      const allCreated = (data.results || []).every(
        (r: BulkResultItem) => r.status === "created",
      );
      if (allCreated) setCsvRows([]);
    } catch (err: unknown) {
      setBulkError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBulkUploading(false);
    }
  };

  const validCount = csvRows.filter((r) => r.errors.length === 0).length;
  const errorCount = csvRows.filter((r) => r.errors.length > 0).length;

  /* ── Render ───────────────────────────────────────────────── */
  return (
    <div className="page create-product-page">
      {/* Header */}
      <div className="page-header">
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate("/products")}
        >
          <ArrowLeft size={16} /> Back
        </button>
        <h2 className="page-title" style={{ marginBottom: 0 }}>
          Add Products
        </h2>
      </div>

      {/* Tab switcher */}
      <div className="cp-tabs">
        <button
          className={`cp-tab ${activeTab === "single" ? "cp-tab--active" : ""}`}
          onClick={() => setActiveTab("single")}
        >
          <Plus size={16} /> Single Product
        </button>
        <button
          className={`cp-tab ${activeTab === "bulk" ? "cp-tab--active" : ""}`}
          onClick={() => setActiveTab("bulk")}
        >
          <Upload size={16} /> Bulk Upload (CSV)
        </button>
      </div>

      {/* ── Single Product Tab ──────────────────────────────── */}
      {activeTab === "single" && (
        <div className="card cp-card">
          <h3 className="cp-card-title">Create a Product</h3>
          {formError && <div className="alert alert-error">{formError}</div>}
          {formSuccess && (
            <div className="alert alert-success">{formSuccess}</div>
          )}
          <form onSubmit={handleSingleSubmit} className="form-vertical">
            <div className="form-row">
              <div className="form-group">
                <label>Product Name *</label>
                <input
                  type="text"
                  placeholder="e.g. Widget Alpha"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>SKU Code *</label>
                <input
                  type="text"
                  placeholder="e.g. SKU-001"
                  value={form.sku_code}
                  onChange={(e) =>
                    setForm({ ...form, sku_code: e.target.value })
                  }
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
            </div>
            <div className="form-row">
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
                  title="Periodic Automatic Replenishment level — ideal stock to maintain"
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
                  title="Number of days it takes to receive new stock after ordering"
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
                  title="Maximum stock capacity for this product"
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
          </form>
        </div>
      )}

      {/* ── Bulk Upload Tab ─────────────────────────────────── */}
      {activeTab === "bulk" && (
        <div className="cp-bulk">
          {/* Step 1: Download sample */}
          <div className="card cp-card">
            <div className="cp-step-header">
              <span className="cp-step-num">1</span>
              <div>
                <h3 className="cp-card-title" style={{ marginBottom: 2 }}>
                  Download Sample CSV
                </h3>
                <p className="cp-step-desc">
                  Download the template, fill in your product data, then upload
                  it below.
                </p>
              </div>
            </div>
            <button className="btn btn-secondary" onClick={downloadSample}>
              <Download size={16} /> Download Template
            </button>
            <div className="cp-csv-format">
              <p className="cp-csv-format-title">
                <FileSpreadsheet size={14} /> Expected columns:
              </p>
              <div className="cp-csv-cols">
                <span className="cp-csv-col cp-csv-col--req">name *</span>
                <span className="cp-csv-col cp-csv-col--req">sku_code *</span>
                <span className="cp-csv-col">price</span>
                <span className="cp-csv-col">stock_at_warehouse</span>
                <span className="cp-csv-col">uom</span>
              </div>
            </div>
          </div>

          {/* Step 2: Upload */}
          <div className="card cp-card">
            <div className="cp-step-header">
              <span className="cp-step-num">2</span>
              <div>
                <h3 className="cp-card-title" style={{ marginBottom: 2 }}>
                  Upload Your CSV
                </h3>
                <p className="cp-step-desc">
                  Select your filled CSV file. We'll validate it before creating
                  products.
                </p>
              </div>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: "none" }}
              onChange={handleFileChange}
            />

            <button
              className="btn btn-primary"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={16} /> Choose CSV File
            </button>

            {fileName && (
              <span className="cp-file-name">
                <FileSpreadsheet size={14} /> {fileName}
              </span>
            )}

            {bulkError && (
              <div className="alert alert-error" style={{ marginTop: 12 }}>
                {bulkError}
              </div>
            )}
          </div>

          {/* Step 3: Preview & Validate */}
          {csvRows.length > 0 && (
            <div className="card cp-card">
              <div className="cp-step-header">
                <span className="cp-step-num">3</span>
                <div>
                  <h3 className="cp-card-title" style={{ marginBottom: 2 }}>
                    Preview & Validate
                  </h3>
                  <p className="cp-step-desc">
                    {validCount} valid, {errorCount} with errors out of{" "}
                    {csvRows.length} rows
                  </p>
                </div>
              </div>

              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Name</th>
                      <th>SKU Code</th>
                      <th>Price</th>
                      <th>Stock</th>
                      <th>UOM</th>
                      <th>Status</th>
                      <th style={{ width: 50 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {csvRows.map((r) => (
                      <tr
                        key={r.row}
                        className={r.errors.length > 0 ? "cp-row-error" : ""}
                      >
                        <td>{r.row}</td>
                        <td className="td-bold">{r.name || "—"}</td>
                        <td>
                          <code>{r.sku_code || "—"}</code>
                        </td>
                        <td>₹{Number(r.price || 0).toFixed(2)}</td>
                        <td>{r.stock_at_warehouse}</td>
                        <td>{r.uom || "pcs"}</td>
                        <td>
                          {r.errors.length > 0 ? (
                            <span className="cp-validation-err">
                              <AlertTriangle size={13} />
                              {r.errors.join("; ")}
                            </span>
                          ) : (
                            <span className="cp-validation-ok">
                              <CheckCircle2 size={13} /> Valid
                            </span>
                          )}
                        </td>
                        <td>
                          <button
                            className="btn-icon btn-icon--danger"
                            title="Remove row"
                            onClick={() => removeRow(r.row)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
                <button
                  className="btn btn-primary"
                  disabled={bulkUploading || errorCount > 0}
                  onClick={handleBulkUpload}
                >
                  {bulkUploading
                    ? "Uploading..."
                    : `Create ${validCount} Product${validCount !== 1 ? "s" : ""}`}
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setCsvRows([]);
                    setBulkResults([]);
                    setFileName("");
                  }}
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {/* Bulk results */}
          {bulkResults.length > 0 && (
            <div className="card cp-card">
              <h3 className="cp-card-title">Upload Results</h3>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Name</th>
                      <th>SKU</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bulkResults.map((r, i) => (
                      <tr key={i}>
                        <td>{r.row}</td>
                        <td className="td-bold">{r.name}</td>
                        <td>
                          <code>{r.sku_code}</code>
                        </td>
                        <td>
                          {r.status === "created" ? (
                            <span className="cp-validation-ok">
                              <CheckCircle2 size={13} /> Created
                            </span>
                          ) : (
                            <span className="cp-validation-err">
                              <XCircle size={13} /> {r.message}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: 12 }}>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => navigate("/products")}
                >
                  Go to Products
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
