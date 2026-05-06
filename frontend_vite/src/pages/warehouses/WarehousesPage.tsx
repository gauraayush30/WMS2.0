import { useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Warehouse as WarehouseIcon } from "lucide-react";

import { API, useAuth } from "../../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Warehouse {
  id: number;
  name: string;
  code: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  is_active: boolean;
  created_at: string;
}

const EMPTY_FORM = {
  name: "",
  code: "",
  address: "",
  city: "",
  state: "",
  zip_code: "",
  is_active: true,
};

export default function WarehousesPage() {
  const { authFetch, isWarehouseAdmin } = useAuth();
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [loading, setLoading] = useState(true);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Warehouse | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const fetchWarehouses = useCallback(async () => {
    setLoading(true);
    const r = await authFetch(`${API}/warehouses`);
    if (r.ok) {
      const data = await r.json();
      setWarehouses(data.warehouses || []);
    }
    setLoading(false);
  }, [authFetch]);

  useEffect(() => {
    fetchWarehouses();
  }, [fetchWarehouses]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setError("");
    setOpen(true);
  };

  const openEdit = (w: Warehouse) => {
    setEditing(w);
    setForm({
      name: w.name,
      code: w.code,
      address: w.address,
      city: w.city,
      state: w.state,
      zip_code: w.zip_code,
      is_active: w.is_active,
    });
    setError("");
    setOpen(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.name.trim() || !form.code.trim()) {
      setError("Name and code are required");
      return;
    }
    setSaving(true);
    const url = editing
      ? `${API}/warehouses/${editing.id}`
      : `${API}/warehouses`;
    const method = editing ? "PATCH" : "POST";
    const r = await authFetch(url, {
      method,
      body: JSON.stringify(form),
    });
    setSaving(false);
    if (!r.ok) {
      const e2 = await r.json().catch(() => ({}));
      setError(e2.detail || "Failed to save warehouse");
      return;
    }
    setOpen(false);
    fetchWarehouses();
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <WarehouseIcon className="text-muted-foreground" />
          <h1 className="text-2xl font-semibold">Warehouses</h1>
        </div>
        {isWarehouseAdmin && (
          <Button onClick={openCreate}>
            <Plus size={16} /> Add warehouse
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Active warehouses</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : warehouses.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No warehouses yet.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>City</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {warehouses.map((w) => (
                  <TableRow key={w.id}>
                    <TableCell className="font-mono text-xs">{w.code}</TableCell>
                    <TableCell className="font-medium">{w.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {w.city || "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {w.state || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={w.is_active ? "default" : "secondary"}>
                        {w.is_active ? "active" : "inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {isWarehouseAdmin && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(w)}
                          title="Edit"
                        >
                          <Pencil size={14} />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit warehouse" : "Add warehouse"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Name</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div>
                <Label>Code</Label>
                <Input
                  value={form.code}
                  onChange={(e) =>
                    setForm({ ...form, code: e.target.value.toUpperCase() })
                  }
                  required
                />
              </div>
            </div>
            <div>
              <Label>Address</Label>
              <Input
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label>City</Label>
                <Input
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                />
              </div>
              <div>
                <Label>State</Label>
                <Input
                  value={form.state}
                  onChange={(e) => setForm({ ...form, state: e.target.value })}
                />
              </div>
              <div>
                <Label>Zip code</Label>
                <Input
                  value={form.zip_code}
                  onChange={(e) =>
                    setForm({ ...form, zip_code: e.target.value })
                  }
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
