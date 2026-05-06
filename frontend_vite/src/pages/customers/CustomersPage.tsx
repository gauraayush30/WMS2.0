import { useCallback, useEffect, useState } from "react";
import { Plus, Pencil, Briefcase, UserPlus } from "lucide-react";

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

interface Customer {
  id: number;
  name: string;
  code: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  is_active: boolean;
  created_at: string;
}

interface CustomerUser {
  id: number;
  username: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const EMPTY_FORM = {
  name: "",
  code: "",
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  is_active: true,
};

const EMPTY_USER_FORM = {
  username: "",
  name: "",
  email: "",
  password: "",
  role: "customer_staff" as "customer_admin" | "customer_staff",
};

export default function CustomersPage() {
  const { authFetch, isWarehouseAdmin } = useAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [usersOpen, setUsersOpen] = useState(false);
  const [usersFor, setUsersFor] = useState<Customer | null>(null);
  const [users, setUsers] = useState<CustomerUser[]>([]);
  const [userForm, setUserForm] = useState({ ...EMPTY_USER_FORM });
  const [userSaving, setUserSaving] = useState(false);
  const [userError, setUserError] = useState("");

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    const r = await authFetch(`${API}/customers`);
    if (r.ok) {
      const data = await r.json();
      setCustomers(data.customers || []);
    }
    setLoading(false);
  }, [authFetch]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setError("");
    setEditOpen(true);
  };

  const openEdit = (c: Customer) => {
    setEditing(c);
    setForm({
      name: c.name,
      code: c.code,
      contact_name: c.contact_name,
      contact_email: c.contact_email,
      contact_phone: c.contact_phone,
      is_active: c.is_active,
    });
    setError("");
    setEditOpen(true);
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
      ? `${API}/customers/${editing.id}`
      : `${API}/customers`;
    const method = editing ? "PATCH" : "POST";
    const r = await authFetch(url, {
      method,
      body: JSON.stringify(form),
    });
    setSaving(false);
    if (!r.ok) {
      const e2 = await r.json().catch(() => ({}));
      setError(e2.detail || "Failed to save customer");
      return;
    }
    setEditOpen(false);
    fetchCustomers();
  };

  const openUsers = async (c: Customer) => {
    setUsersFor(c);
    setUserForm({ ...EMPTY_USER_FORM });
    setUserError("");
    const r = await authFetch(`${API}/customers/${c.id}/users`);
    setUsers(r.ok ? (await r.json()).users || [] : []);
    setUsersOpen(true);
  };

  const submitUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usersFor) return;
    setUserError("");
    setUserSaving(true);
    const r = await authFetch(`${API}/customers/${usersFor.id}/users`, {
      method: "POST",
      body: JSON.stringify(userForm),
    });
    setUserSaving(false);
    if (!r.ok) {
      const e2 = await r.json().catch(() => ({}));
      setUserError(e2.detail || "Failed to create user");
      return;
    }
    setUserForm({ ...EMPTY_USER_FORM });
    const r2 = await authFetch(`${API}/customers/${usersFor.id}/users`);
    setUsers(r2.ok ? (await r2.json()).users || [] : []);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Briefcase className="text-muted-foreground" />
          <h1 className="text-2xl font-semibold">Customers</h1>
        </div>
        {isWarehouseAdmin && (
          <Button onClick={openCreate}>
            <Plus size={16} /> Add customer
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">All customers</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : customers.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No customers yet. Add one to start onboarding tenants.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono text-xs">{c.code}</TableCell>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {c.contact_name || "—"}
                      {c.contact_email ? ` · ${c.contact_email}` : ""}
                    </TableCell>
                    <TableCell>
                      <Badge variant={c.is_active ? "default" : "secondary"}>
                        {c.is_active ? "active" : "inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openUsers(c)}
                        title="Manage users"
                      >
                        <UserPlus size={14} />
                      </Button>
                      {isWarehouseAdmin && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(c)}
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

      {/* Create/Edit dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit customer" : "Add customer"}
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
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Contact name</Label>
                <Input
                  value={form.contact_name}
                  onChange={(e) =>
                    setForm({ ...form, contact_name: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Contact email</Label>
                <Input
                  type="email"
                  value={form.contact_email}
                  onChange={(e) =>
                    setForm({ ...form, contact_email: e.target.value })
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

      {/* Users dialog */}
      <Dialog open={usersOpen} onOpenChange={setUsersOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              Users for {usersFor?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3">
            {users.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                No users yet. Add one below.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell>{u.name}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {u.email}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{u.role}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            <form
              onSubmit={submitUser}
              className="space-y-3 border-t pt-3 mt-3"
            >
              <div className="text-sm font-semibold">Add a user</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Username</Label>
                  <Input
                    value={userForm.username}
                    onChange={(e) =>
                      setUserForm({ ...userForm, username: e.target.value })
                    }
                    required
                  />
                </div>
                <div>
                  <Label>Display name</Label>
                  <Input
                    value={userForm.name}
                    onChange={(e) =>
                      setUserForm({ ...userForm, name: e.target.value })
                    }
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={userForm.email}
                    onChange={(e) =>
                      setUserForm({ ...userForm, email: e.target.value })
                    }
                    required
                  />
                </div>
                <div>
                  <Label>Temporary password</Label>
                  <Input
                    type="password"
                    minLength={6}
                    value={userForm.password}
                    onChange={(e) =>
                      setUserForm({ ...userForm, password: e.target.value })
                    }
                    required
                  />
                </div>
              </div>
              <div>
                <Label>Role</Label>
                <Select
                  value={userForm.role}
                  onValueChange={(v) =>
                    setUserForm({
                      ...userForm,
                      role: v as "customer_admin" | "customer_staff",
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="customer_staff">customer_staff</SelectItem>
                    <SelectItem value="customer_admin">customer_admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {userError && <p className="text-sm text-destructive">{userError}</p>}
              <Button type="submit" disabled={userSaving}>
                <UserPlus size={14} />
                {userSaving ? "Adding…" : "Add user"}
              </Button>
            </form>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
