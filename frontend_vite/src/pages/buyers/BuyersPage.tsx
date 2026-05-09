import { useCallback, useEffect, useState } from "react";
import {
  Plus,
  Pencil,
  ShoppingCart,
  MapPin,
  Trash2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { motion } from "framer-motion";

/* ── Types ─────────────────────────────────────────────────── */

interface Buyer {
  id: number;
  name: string;
  gstin: string;
  contact_name: string;
  contact_phone: string;
  is_active: boolean;
  customer_id: number;
  created_at: string;
}

interface BuyerLocation {
  id: number;
  buyer_id: number;
  name: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  contact_person: string;
  contact_phone: string;
  is_active: boolean;
}

interface Customer {
  id: number;
  name: string;
}

/* ── Empty forms ───────────────────────────────────────────── */

const EMPTY_BUYER = {
  name: "",
  gstin: "",
  contact_name: "",
  contact_phone: "",
  is_active: true,
};

const EMPTY_LOC = {
  name: "",
  address: "",
  city: "",
  state: "",
  zip_code: "",
  contact_person: "",
  contact_phone: "",
};

/* ── Component ─────────────────────────────────────────────── */

export default function BuyersPage() {
  const { authFetch, isWarehouse, effectiveCustomerId, isWarehouseAdmin } =
    useAuth();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerId, setCustomerId] = useState<number | "">(
    effectiveCustomerId ?? ""
  );
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [loading, setLoading] = useState(true);

  /* buyer dialog */
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<Buyer | null>(null);
  const [form, setForm] = useState({ ...EMPTY_BUYER });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  /* locations */
  const [expandedBuyer, setExpandedBuyer] = useState<number | null>(null);
  const [locations, setLocations] = useState<BuyerLocation[]>([]);
  const [locsLoading, setLocsLoading] = useState(false);

  /* location dialog */
  const [locDialogOpen, setLocDialogOpen] = useState(false);
  const [locEditing, setLocEditing] = useState<BuyerLocation | null>(null);
  const [locForm, setLocForm] = useState({ ...EMPTY_LOC });
  const [locSaving, setLocSaving] = useState(false);
  const [locError, setLocError] = useState("");

  /* fetch customers for warehouse roles */
  useEffect(() => {
    if (!isWarehouse) return;
    authFetch(`${API}/customers`)
      .then((r) => (r.ok ? r.json() : { customers: [] }))
      .then((d) => setCustomers(d.customers || []));
  }, [authFetch, isWarehouse]);

  /* fetch buyers */
  const fetchBuyers = useCallback(async () => {
    if (!customerId && isWarehouse) {
      setBuyers([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const params = new URLSearchParams();
    if (customerId) params.set("customer_id", String(customerId));
    const r = await authFetch(`${API}/buyers?${params.toString()}`);
    if (r.ok) {
      const d = await r.json();
      setBuyers(d.buyers || []);
    }
    setLoading(false);
  }, [authFetch, customerId, isWarehouse]);

  useEffect(() => {
    fetchBuyers();
  }, [fetchBuyers]);

  /* fetch locations for expanded buyer */
  const fetchLocations = useCallback(
    async (buyerId: number) => {
      setLocsLoading(true);
      const r = await authFetch(`${API}/buyers/${buyerId}/locations`);
      if (r.ok) {
        const d = await r.json();
        setLocations(d.locations || []);
      }
      setLocsLoading(false);
    },
    [authFetch]
  );

  const toggleExpand = (buyerId: number) => {
    if (expandedBuyer === buyerId) {
      setExpandedBuyer(null);
      setLocations([]);
    } else {
      setExpandedBuyer(buyerId);
      fetchLocations(buyerId);
    }
  };

  /* buyer CRUD */
  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_BUYER });
    setError("");
    setEditOpen(true);
  };

  const openEdit = (b: Buyer) => {
    setEditing(b);
    setForm({
      name: b.name,
      gstin: b.gstin,
      contact_name: b.contact_name,
      contact_phone: b.contact_phone,
      is_active: b.is_active,
    });
    setError("");
    setEditOpen(true);
  };

  const submitBuyer = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    const url = editing
      ? `${API}/buyers/${editing.id}`
      : `${API}/buyers`;
    const method = editing ? "PATCH" : "POST";
    const body: any = { ...form };
    if (!editing) body.customer_id = customerId || undefined;
    const r = await authFetch(url, { method, body: JSON.stringify(body) });
    setSaving(false);
    if (!r.ok) {
      const e2 = await r.json().catch(() => ({}));
      setError(e2.detail || "Failed to save");
      return;
    }
    setEditOpen(false);
    fetchBuyers();
  };

  /* location CRUD */
  const openLocCreate = () => {
    setLocEditing(null);
    setLocForm({ ...EMPTY_LOC });
    setLocError("");
    setLocDialogOpen(true);
  };

  const openLocEdit = (loc: BuyerLocation) => {
    setLocEditing(loc);
    setLocForm({
      name: loc.name,
      address: loc.address,
      city: loc.city,
      state: loc.state,
      zip_code: loc.zip_code,
      contact_person: loc.contact_person,
      contact_phone: loc.contact_phone,
    });
    setLocError("");
    setLocDialogOpen(true);
  };

  const submitLoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!expandedBuyer) return;
    setLocError("");
    if (!locForm.name.trim()) {
      setLocError("Location name is required");
      return;
    }
    setLocSaving(true);
    const url = locEditing
      ? `${API}/buyers/${expandedBuyer}/locations/${locEditing.id}`
      : `${API}/buyers/${expandedBuyer}/locations`;
    const method = locEditing ? "PATCH" : "POST";
    const r = await authFetch(url, { method, body: JSON.stringify(locForm) });
    setLocSaving(false);
    if (!r.ok) {
      const e2 = await r.json().catch(() => ({}));
      setLocError(e2.detail || "Failed to save location");
      return;
    }
    setLocDialogOpen(false);
    fetchLocations(expandedBuyer);
  };

  const deleteLoc = async (locId: number) => {
    if (!expandedBuyer) return;
    if (!confirm("Delete this location?")) return;
    await authFetch(`${API}/buyers/${expandedBuyer}/locations/${locId}`, {
      method: "DELETE",
    });
    fetchLocations(expandedBuyer);
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShoppingCart className="text-muted-foreground" />
          <h1 className="text-2xl font-semibold">Buyers</h1>
        </div>
        <div className="flex items-center gap-3">
          {isWarehouse && (
            <Select
              value={customerId === "" ? "" : String(customerId)}
              onValueChange={(v) => {
                setCustomerId(Number(v));
                setExpandedBuyer(null);
              }}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Select customer" />
              </SelectTrigger>
              <SelectContent>
                {customers.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button onClick={openCreate} disabled={!customerId && isWarehouse}>
            <Plus size={16} /> Add buyer
          </Button>
        </div>
      </div>

      {/* Buyers table */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              {isWarehouse && !customerId
                ? "Select a customer to view buyers"
                : `All buyers`}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground">Loading…</div>
            ) : buyers.length === 0 ? (
              <div className="text-sm text-muted-foreground py-8 text-center">
                {isWarehouse && !customerId
                  ? "Please select a customer first."
                  : "No buyers yet. Add one to get started."}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10" />
                    <TableHead>Name</TableHead>
                    <TableHead>GSTIN</TableHead>
                    <TableHead>Contact</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {buyers.map((b) => (
                    <>
                      <TableRow
                        key={b.id}
                        className="cursor-pointer hover:bg-muted/30"
                        onClick={() => toggleExpand(b.id)}
                      >
                        <TableCell>
                          {expandedBuyer === b.id ? (
                            <ChevronDown size={14} />
                          ) : (
                            <ChevronRight size={14} />
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{b.name}</TableCell>
                        <TableCell className="font-mono text-xs">
                          {b.gstin || "—"}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {b.contact_name || "—"}
                          {b.contact_phone ? ` · ${b.contact_phone}` : ""}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={b.is_active ? "default" : "secondary"}
                          >
                            {b.is_active ? "active" : "inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              openEdit(b);
                            }}
                            title="Edit"
                          >
                            <Pencil size={14} />
                          </Button>
                        </TableCell>
                      </TableRow>

                      {/* Expanded locations row */}
                      {expandedBuyer === b.id && (
                        <TableRow key={`loc-${b.id}`}>
                          <TableCell colSpan={6} className="bg-muted/20 p-4">
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2 text-sm font-medium">
                                  <MapPin size={14} className="text-primary" />
                                  Locations
                                  <Badge variant="outline" className="text-xs">
                                    {locations.length}
                                  </Badge>
                                </div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openLocCreate();
                                  }}
                                >
                                  <Plus size={12} /> Add location
                                </Button>
                              </div>

                              {locsLoading ? (
                                <p className="text-xs text-muted-foreground">
                                  Loading…
                                </p>
                              ) : locations.length === 0 ? (
                                <p className="text-xs text-muted-foreground py-4 text-center">
                                  No locations yet for this buyer.
                                </p>
                              ) : (
                                <div className="grid gap-2">
                                  {locations.map((loc) => (
                                    <div
                                      key={loc.id}
                                      className="flex items-center justify-between rounded-lg border bg-background px-3 py-2"
                                    >
                                      <div>
                                        <p className="text-sm font-medium">
                                          {loc.name}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                          {[
                                            loc.address,
                                            loc.city,
                                            loc.state,
                                            loc.zip_code,
                                          ]
                                            .filter(Boolean)
                                            .join(", ") || "No address"}
                                        </p>
                                        {loc.contact_person && (
                                          <p className="text-xs text-muted-foreground">
                                            {loc.contact_person}
                                            {loc.contact_phone
                                              ? ` · ${loc.contact_phone}`
                                              : ""}
                                          </p>
                                        )}
                                      </div>
                                      <div className="flex gap-1">
                                        <Button
                                          variant="ghost"
                                          size="icon"
                                          className="h-7 w-7"
                                          onClick={() => openLocEdit(loc)}
                                        >
                                          <Pencil size={12} />
                                        </Button>
                                        <Button
                                          variant="ghost"
                                          size="icon"
                                          className="h-7 w-7 text-destructive"
                                          onClick={() => deleteLoc(loc.id)}
                                        >
                                          <Trash2 size={12} />
                                        </Button>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Buyer Create/Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit buyer" : "Add buyer"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={submitBuyer} className="space-y-3">
            <div>
              <Label>Name</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>GSTIN</Label>
                <Input
                  value={form.gstin}
                  onChange={(e) => setForm({ ...form, gstin: e.target.value })}
                />
              </div>
              <div>
                <Label>Contact name</Label>
                <Input
                  value={form.contact_name}
                  onChange={(e) =>
                    setForm({ ...form, contact_name: e.target.value })
                  }
                />
              </div>
            </div>
            <div>
              <Label>Contact phone</Label>
              <Input
                value={form.contact_phone}
                onChange={(e) =>
                  setForm({ ...form, contact_phone: e.target.value })
                }
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setEditOpen(false)}
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

      {/* Location Create/Edit Dialog */}
      <Dialog open={locDialogOpen} onOpenChange={setLocDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {locEditing ? "Edit location" : "Add location"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={submitLoc} className="space-y-3">
            <div>
              <Label>Location name</Label>
              <Input
                value={locForm.name}
                onChange={(e) =>
                  setLocForm({ ...locForm, name: e.target.value })
                }
                required
              />
            </div>
            <div>
              <Label>Address</Label>
              <Input
                value={locForm.address}
                onChange={(e) =>
                  setLocForm({ ...locForm, address: e.target.value })
                }
              />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label>City</Label>
                <Input
                  value={locForm.city}
                  onChange={(e) =>
                    setLocForm({ ...locForm, city: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>State</Label>
                <Input
                  value={locForm.state}
                  onChange={(e) =>
                    setLocForm({ ...locForm, state: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>ZIP</Label>
                <Input
                  value={locForm.zip_code}
                  onChange={(e) =>
                    setLocForm({ ...locForm, zip_code: e.target.value })
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Contact person</Label>
                <Input
                  value={locForm.contact_person}
                  onChange={(e) =>
                    setLocForm({ ...locForm, contact_person: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Contact phone</Label>
                <Input
                  value={locForm.contact_phone}
                  onChange={(e) =>
                    setLocForm({ ...locForm, contact_phone: e.target.value })
                  }
                />
              </div>
            </div>
            {locError && <p className="text-sm text-destructive">{locError}</p>}
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setLocDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={locSaving}>
                {locSaving ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
