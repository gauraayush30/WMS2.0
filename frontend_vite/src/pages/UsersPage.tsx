import { useEffect, useState } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Users, Shield } from "lucide-react";

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

  const fetchUsers = () => {
    setLoading(true);
    authFetch(`${API}/users`)
      .then((r) => r.json())
      .then((data) => setUsers(data.users || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRoleChange = async (targetId: number, newRole: string) => {
    setUpdatingId(targetId);
    try {
      const res = await authFetch(`${API}/users/${targetId}/role`, {
        method: "PUT",
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Failed to update role");
        return;
      }
      fetchUsers();
    } catch {
      alert("Error updating role");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">
          <Users size={22} /> Users & Employees
        </h2>
        <span className="page-count">{users.length} members</span>
      </div>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : users.length === 0 ? (
        <div className="empty-state">
          <p>No users found in your business.</p>
        </div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Username</th>
                <th>Email</th>
                <th>Role</th>
                <th>Joined</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="td-bold">
                    {u.name}
                    {u.id === user?.id && (
                      <span className="badge badge--you">You</span>
                    )}
                  </td>
                  <td>{u.username || "—"}</td>
                  <td>{u.email}</td>
                  <td>
                    {user?.role === "admin" && u.id !== user?.id ? (
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        disabled={updatingId === u.id}
                        className="role-select"
                      >
                        {ROLE_OPTIONS.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className={`role-badge role-badge--${u.role}`}>
                        <Shield size={12} /> {u.role}
                      </span>
                    )}
                  </td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
