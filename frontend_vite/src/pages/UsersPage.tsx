import { useEffect, useState } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Users, Shield } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface UserItem {
  id: number;
  username: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const ROLE_OPTIONS = ["admin", "manager", "employee"];

export default function UsersPage() {
  const { authFetch, user } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const fetchUsers = () => {
    setLoading(true);
    setError("");
    authFetch(`${API}/users`)
      .then((r) => r.json())
      .then((data) => setUsers(data.users || []))
      .catch(() => setError("Failed to load users"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleRoleChange = async (targetId: number, newRole: string) => {
    setUpdatingId(targetId);
    setError("");
    try {
      const res = await authFetch(`${API}/users/${targetId}/role`, {
        method: "PUT",
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Failed to update role");
        return;
      }
      fetchUsers();
    } catch {
      setError("Error updating role");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-bold flex items-center gap-2"><Users size={20} /> Users & Employees</h2>
        <Badge variant="secondary">{users.length} members</Badge>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}

      {loading ? (
        <div className="space-y-3">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
      ) : users.length === 0 ? (
        <Card><CardContent className="py-10 text-center text-muted-foreground">No users found in your business.</CardContent></Card>
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Joined</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="text-sm font-medium">
                    {u.name}
                    {u.id === user?.id && <Badge variant="outline" className="ml-2">You</Badge>}
                  </TableCell>
                  <TableCell className="text-sm">{u.username || "-"}</TableCell>
                  <TableCell className="text-sm">{u.email}</TableCell>
                  <TableCell>
                    {user?.role === "admin" && u.id !== user?.id ? (
                      <Select
                        value={u.role}
                        disabled={updatingId === u.id}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      >
                        {ROLE_OPTIONS.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </Select>
                    ) : (
                      <Badge variant="secondary" className="capitalize">
                        <Shield size={12} className="mr-1" /> {u.role}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">{new Date(u.created_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
