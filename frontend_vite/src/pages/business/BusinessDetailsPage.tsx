import { useEffect, useState } from "react";
import { useAuth, API } from "../../context/AuthContext";
import { Building2, MapPin, Save } from "lucide-react";

interface Business {
  id: number;
  name: string;
  location: string | null;
  created_at: string;
  updated_at: string;
}

export default function BusinessDetailsPage() {
  const { authFetch, user } = useAuth();
  const [business, setBusiness] = useState<Business | null>(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", location: "" });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isCreate, setIsCreate] = useState(false);

  useEffect(() => {
    setLoading(true);
    authFetch(`${API}/business`)
      .then(async (r) => {
        if (r.ok) {
          const data = await r.json();
          setBusiness(data);
          setForm({ name: data.name, location: data.location || "" });
        } else {
          setIsCreate(true);
        }
      })
      .catch(() => setIsCreate(true))
      .finally(() => setLoading(false));
  }, [authFetch]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    if (!form.name.trim()) {
      setError("Business name is required");
      return;
    }
    setSaving(true);
    try {
      const url = `${API}/business`;
      const method = isCreate ? "POST" : "PUT";
      const res = await authFetch(url, {
        method,
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save");
      }
      const data = await res.json();
      setBusiness(data);
      setIsCreate(false);
      setMessage(isCreate ? "Business created!" : "Business updated!");
      setTimeout(() => setMessage(""), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <div className="page">
      <h2 className="page-title">Business Details</h2>

      <div className="card" style={{ maxWidth: 600 }}>
        <div className="card-header-row">
          <Building2 size={24} />
          <h3>{isCreate ? "Create Your Business" : "Business Details"}</h3>
        </div>

        <form onSubmit={handleSubmit} className="form-vertical">
          {error && <div className="alert alert-error">{error}</div>}
          {message && <div className="alert alert-success">{message}</div>}

          <div className="form-group">
            <label>Business Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="My Warehouse Co."
              required
            />
          </div>

          <div className="form-group">
            <label>
              <MapPin size={14} style={{ marginRight: 4 }} />
              Location
            </label>
            <input
              type="text"
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="City, Country"
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={16} />
            {saving
              ? "Saving..."
              : isCreate
                ? "Create Business"
                : "Update Business"}
          </button>
        </form>

        {business && (
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Business ID</span>
              <span className="detail-value">{business.id}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Your Role</span>
              <span className="detail-value">{user?.role || "—"}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Created</span>
              <span className="detail-value">
                {new Date(business.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
