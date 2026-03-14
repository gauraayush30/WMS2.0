import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "../../context/AuthContext";
import { MapPin, Plus, Pencil, Trash2, Phone, User, FileText, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

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
  const navigate = useNavigate();

  const [locations, setLocations] = useState<DeliveryLocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInactive, setShowInactive] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<DeliveryLocation | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");

  const fetchLocations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API}/delivery-locations?include_inactive=${showInactive}`);
      if (res.ok) {
        const data = await res.json();
        setLocations(data.locations || []);
      }
    } finally {
      setLoading(false);
    }
  }, [authFetch, showInactive]);

  useEffect(() => {
    fetchLocations();
  }, [fetchLocations]);

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
      const url = isEdit ? `${API}/delivery-locations/${editing!.id}` : `${API}/delivery-locations`;
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
      setFormSuccess(isEdit ? "Location updated successfully!" : "Location created successfully!");
      fetchLocations();
      setTimeout(() => {
        setModalOpen(false);
        setFormSuccess("");
      }, 1000);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (loc: DeliveryLocation) => {
    if (!confirm(`Are you sure you want to delete "${loc.name}"?`)) return;
    try {
      const res = await authFetch(`${API}/delivery-locations/${loc.id}`, { method: "DELETE" });
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

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => navigate("/business")}>
          <ArrowLeft size={14} /> Back
        </Button>
        <h2 className="text-xl font-bold">Delivery Locations</h2>
        <div className="ml-auto flex items-center gap-3">
          <label className="text-sm text-muted-foreground flex items-center gap-2">
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
            Show inactive
          </label>
          <Button size="sm" onClick={openCreate}><Plus size={14} /> Add Location</Button>
        </div>
      </div>

      {loading ? (
        <Card><CardContent className="py-10 text-center text-muted-foreground">Loading...</CardContent></Card>
      ) : locations.length === 0 ? (
        <Card>
          <CardContent className="text-center py-10 text-muted-foreground">
            <MapPin size={38} className="mx-auto mb-2 opacity-60" />
            No delivery locations yet. Click Add Location to create one.
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Address</TableHead>
                <TableHead>City</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Status</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {locations.map((loc) => (
                <TableRow key={loc.id} className={!loc.is_active ? "opacity-60" : ""}>
                  <TableCell className="text-sm font-medium">{loc.name}</TableCell>
                  <TableCell className="text-sm">{loc.address || "-"}</TableCell>
                  <TableCell className="text-sm">{loc.city || "-"}</TableCell>
                  <TableCell className="text-sm">{loc.state || "-"}</TableCell>
                  <TableCell className="text-sm">{loc.contact_person || "-"}</TableCell>
                  <TableCell className="text-sm">{loc.contact_phone || "-"}</TableCell>
                  <TableCell>
                    <Badge variant={loc.is_active ? "success" : "destructive"}>{loc.is_active ? "Active" : "Inactive"}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => openEdit(loc)}><Pencil size={13} /></Button>
                      <Button variant="destructive" size="icon" className="h-7 w-7" onClick={() => handleDelete(loc)}><Trash2 size={13} /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-2xl" onClose={() => setModalOpen(false)}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MapPin size={16} /> {editing ? "Edit Location" : "New Delivery Location"}
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="space-y-4 mt-4">
            {formError && <Alert variant="destructive">{formError}</Alert>}
            {formSuccess && <Alert variant="success">{formSuccess}</Alert>}

            <div className="space-y-1.5">
              <Label>Location Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </div>

            <div className="space-y-1.5">
              <Label>Address</Label>
              <Textarea rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1.5"><Label>City</Label><Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></div>
              <div className="space-y-1.5"><Label>State</Label><Input value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} /></div>
              <div className="space-y-1.5"><Label>ZIP Code</Label><Input value={form.zip_code} onChange={(e) => setForm({ ...form, zip_code: e.target.value })} /></div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="flex items-center gap-1"><User size={13} /> Contact Person</Label>
                <Input value={form.contact_person} onChange={(e) => setForm({ ...form, contact_person: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label className="flex items-center gap-1"><Phone size={13} /> Contact Phone</Label>
                <Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="flex items-center gap-1"><FileText size={13} /> Notes</Label>
              <Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>

            {editing && (
              <label className="text-sm text-muted-foreground flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                Active
              </label>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={saving}>{saving ? "Saving..." : editing ? "Update Location" : "Create Location"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
