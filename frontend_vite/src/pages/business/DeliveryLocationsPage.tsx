import { useEffect, useState, useCallback } from "react";
import { useAuth, API } from "../../context/AuthContext";
import {
  MapPin,
  Plus,
  Pencil,
  Trash2,
  X,
  Phone,
  User,
  FileText,
  ArrowLeft,
} from "lucide-react";

/* ── Types ───────────────────────────────────────────────────── */
interface DeliveryLocation {
  id: number;
  business_id: number;
  name: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  contact_person: string;
  contact_phone: string;
  notes: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

const EMPTY_FORM = {
  name: "",
  address: "",
  city: "",
  state: "",
  zip_code: "",
  contact_person: "",
  contact_phone: "",
  notes: "",
  is_active: true,
};

export default function DeliveryLocationsPage() {
  const { authFetch } = useAuth();

  const [locations, setLocations] = useState<DeliveryLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInactive, setShowInactive] = useState(false);

  /* ── Modal state ───────────────────────────────────────────── */
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<DeliveryLocation | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");

  /* ── Fetch ─────────────────────────────────────────────────── */
  const fetchLocations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(
        `${API}/delivery-locations?include_inactive=${showInactive}`,
      );
      if (res.ok) {
        const data = await res.json();
        setLocations(data.locations || []);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [authFetch, showInactive]);

  useEffect(() => {
    fetchLocations();
  }, [fetchLocations]);

  /* ── Open modal ────────────────────────────────────────────── */
  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setFormError("");
    setFormSuccess("");
    setModalOpen(true);
  };

  const openEdit = (loc: DeliveryLocation) => {
    setEditing(loc);
    setForm({
      name: loc.name,
      address: loc.address,
      city: loc.city,
      state: loc.state,
      zip_code: loc.zip_code,
      contact_person: loc.contact_person,
      contact_phone: loc.contact_phone,
      notes: loc.notes,
      is_active: loc.is_active,
    });
    setFormError("");
    setFormSuccess("");
    setModalOpen(true);
  };

  /* ── Submit create / edit ──────────────────────────────────── */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    setFormSuccess("");
    if (!form.name.trim()) {
      setFormError("Location name is required");
      return;
    }
    setSaving(true);
    try {
      const isEdit = !!editing;
      const url = isEdit
        ? `${API}/delivery-locations/${editing!.id}`
        : `${API}/delivery-locations`;
      const method = isEdit ? "PUT" : "POST";
      const res = await authFetch(url, {
        method,
        body: JSON.stringify({
          name: form.name.trim(),
          address: form.address.trim(),
          city: form.city.trim(),
          state: form.state.trim(),
          zip_code: form.zip_code.trim(),
          contact_person: form.contact_person.trim(),
          contact_phone: form.contact_phone.trim(),
          notes: form.notes.trim(),
          ...(isEdit ? { is_active: form.is_active } : {}),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save");
      }
      setFormSuccess(
        isEdit
          ? "Location updated successfully!"
          : "Location created successfully!",
      );
      fetchLocations();
      setTimeout(() => {
        setModalOpen(false);
        setFormSuccess("");
      }, 1200);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  /* ── Delete ────────────────────────────────────────────────── */
  const handleDelete = async (loc: DeliveryLocation) => {
    if (
      !confirm(
        `Are you sure you want to delete "${loc.name}"? This cannot be undone.`,
      )
    )
      return;
    try {
      const res = await authFetch(`${API}/delivery-locations/${loc.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to delete");
        return;
      }
      fetchLocations();
    } catch {
      alert("Error deleting location");
    }
  };

  /* ── Render ────────────────────────────────────────────────── */
  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => window.history.back()}
        >
          <ArrowLeft size={16} /> Back
        </button>
        <h2 className="page-title" style={{ marginBottom: 0 }}>
          Delivery Locations
        </h2>
        <div
          style={{
            marginLeft: "auto",
            display: "flex",
            gap: 8,
            alignItems: "center",
          }}
        >
          <label
            style={{
              fontSize: 13,
              display: "flex",
              alignItems: "center",
              gap: 4,
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
            />
            Show inactive
          </label>
          <button className="btn btn-primary" onClick={openCreate}>
            <Plus size={16} /> Add Location
          </button>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="loading">Loading...</div>
      ) : locations.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <MapPin size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <p style={{ color: "var(--text-secondary)" }}>
            No delivery locations yet. Click "Add Location" to create one.
          </p>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Address</th>
                <th>City</th>
                <th>State</th>
                <th>Contact</th>
                <th>Phone</th>
                <th>Status</th>
                <th style={{ width: 100 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {locations.map((loc) => (
                <tr key={loc.id} style={{ opacity: loc.is_active ? 1 : 0.55 }}>
                  <td className="td-bold">{loc.name}</td>
                  <td>{loc.address || "—"}</td>
                  <td>{loc.city || "—"}</td>
                  <td>{loc.state || "—"}</td>
                  <td>{loc.contact_person || "—"}</td>
                  <td>{loc.contact_phone || "—"}</td>
                  <td>
                    <span
                      className={`stock-badge ${loc.is_active ? "stock-badge--ok" : "stock-badge--danger"}`}
                    >
                      {loc.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button
                        className="btn-icon"
                        title="Edit"
                        onClick={() => openEdit(loc)}
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        className="btn-icon btn-icon--danger"
                        title="Delete"
                        onClick={() => handleDelete(loc)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modal ──────────────────────────────────────────────── */}
      {modalOpen && (
        <div className="modal-overlay" onClick={() => setModalOpen(false)}>
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 600 }}
          >
            <div className="modal-header">
              <h3 style={{ margin: 0 }}>
                <MapPin
                  size={18}
                  style={{ marginRight: 6, verticalAlign: -3 }}
                />
                {editing ? "Edit Location" : "New Delivery Location"}
              </h3>
              <button className="btn-icon" onClick={() => setModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form
              onSubmit={handleSubmit}
              className="form-vertical"
              style={{ padding: 20 }}
            >
              {formError && (
                <div className="alert alert-error">{formError}</div>
              )}
              {formSuccess && (
                <div className="alert alert-success">{formSuccess}</div>
              )}

              <div className="form-group">
                <label>
                  <MapPin size={14} style={{ marginRight: 4 }} />
                  Location Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Main Warehouse, Downtown Hub"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label>Address</label>
                <textarea
                  rows={2}
                  placeholder="Street address"
                  value={form.address}
                  onChange={(e) =>
                    setForm({ ...form, address: e.target.value })
                  }
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>City</label>
                  <input
                    type="text"
                    placeholder="City"
                    value={form.city}
                    onChange={(e) => setForm({ ...form, city: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>State</label>
                  <input
                    type="text"
                    placeholder="State / Province"
                    value={form.state}
                    onChange={(e) =>
                      setForm({ ...form, state: e.target.value })
                    }
                  />
                </div>
                <div className="form-group">
                  <label>ZIP Code</label>
                  <input
                    type="text"
                    placeholder="ZIP / Postal code"
                    value={form.zip_code}
                    onChange={(e) =>
                      setForm({ ...form, zip_code: e.target.value })
                    }
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>
                    <User size={14} style={{ marginRight: 4 }} />
                    Contact Person
                  </label>
                  <input
                    type="text"
                    placeholder="Contact name"
                    value={form.contact_person}
                    onChange={(e) =>
                      setForm({ ...form, contact_person: e.target.value })
                    }
                  />
                </div>
                <div className="form-group">
                  <label>
                    <Phone size={14} style={{ marginRight: 4 }} />
                    Contact Phone
                  </label>
                  <input
                    type="text"
                    placeholder="Phone number"
                    value={form.contact_phone}
                    onChange={(e) =>
                      setForm({ ...form, contact_phone: e.target.value })
                    }
                  />
                </div>
              </div>

              <div className="form-group">
                <label>
                  <FileText size={14} style={{ marginRight: 4 }} />
                  Notes
                </label>
                <textarea
                  rows={2}
                  placeholder="Any additional details..."
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </div>

              {editing && (
                <div className="form-group">
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={(e) =>
                        setForm({ ...form, is_active: e.target.checked })
                      }
                    />
                    Active
                  </label>
                </div>
              )}

              <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={saving}
                >
                  {saving
                    ? "Saving..."
                    : editing
                      ? "Update Location"
                      : "Create Location"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setModalOpen(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
