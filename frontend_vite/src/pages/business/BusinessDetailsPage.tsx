import { useEffect, useState } from "react";
import { useAuth, API } from "../../context/AuthContext";
import { Building2, MapPin, Save } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

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
      const method = isCreate ? "POST" : "PUT";
      const res = await authFetch(`${API}/business`, {
        method,
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save business");
      }
      const data = await res.json();
      setBusiness(data);
      setIsCreate(false);
      setMessage(isCreate ? "Business created!" : "Business updated!");
      setTimeout(() => setMessage(""), 2500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-52" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-xl font-bold">Business Details</h2>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 size={18} />
            {isCreate ? "Create Your Business" : "Business Details"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <Alert variant="destructive">{error}</Alert>}
          {message && <Alert variant="success">{message}</Alert>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label>Business Name</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="My Warehouse Co."
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label className="flex items-center gap-1.5"><MapPin size={14} />Location</Label>
              <Input
                value={form.location}
                onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
                placeholder="City, Country"
              />
            </div>

            <Button type="submit" disabled={saving}>
              <Save size={14} /> {saving ? "Saving..." : isCreate ? "Create Business" : "Update Business"}
            </Button>
          </form>

          {business && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Business ID</p><p className="text-sm font-semibold">{business.id}</p></CardContent></Card>
              <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Your Role</p><Badge variant="secondary" className="capitalize">{user?.role || "-"}</Badge></CardContent></Card>
              <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Created</p><p className="text-sm font-semibold">{new Date(business.created_at).toLocaleDateString()}</p></CardContent></Card>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
