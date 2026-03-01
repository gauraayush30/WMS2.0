import { useEffect, useState, useCallback } from "react";
import { useAuth, API } from "../../context/AuthContext";
import {
  Search,
  UserPlus,
  Check,
  X,
  Clock,
  CheckCircle2,
  XCircle,
  Send,
  Inbox,
} from "lucide-react";

/* ── Types ────────────────────────────────────────────────────── */
interface AvailableUser {
  id: number;
  username: string;
  name: string;
  email: string;
  created_at: string;
}

interface SentInvite {
  id: number;
  to_user_id: number;
  to_user_name: string;
  to_user_email: string;
  status: string;
  created_at: string;
}

interface ReceivedInvite {
  id: number;
  from_business_id: number;
  business_name: string;
  business_location: string | null;
  from_user_name: string;
  status: string;
  created_at: string;
}

export default function InvitesPage() {
  const { authFetch, user, updateUser } = useAuth();
  const isAdmin = user?.role === "admin";
  const hasBusiness = !!user?.business_id;

  /* ── Admin state: search users + sent invites ─────────────── */
  const [search, setSearch] = useState("");
  const [availableUsers, setAvailableUsers] = useState<AvailableUser[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [sentInvites, setSentInvites] = useState<SentInvite[]>([]);
  const [sentLoading, setSentLoading] = useState(false);
  const [sendingTo, setSendingTo] = useState<number | null>(null);

  /* ── Employee state: received invites ─────────────────────── */
  const [receivedInvites, setReceivedInvites] = useState<ReceivedInvite[]>([]);
  const [receivedLoading, setReceivedLoading] = useState(false);
  const [actioningId, setActioningId] = useState<number | null>(null);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  /* ── Fetch functions ──────────────────────────────────────── */
  const searchUsers = useCallback(async () => {
    setSearchLoading(true);
    try {
      const res = await authFetch(
        `${API}/invites/users-without-business?search=${encodeURIComponent(search)}`,
      );
      if (res.ok) {
        const data = await res.json();
        setAvailableUsers(data.users || []);
      }
    } catch {
      /* ignore */
    } finally {
      setSearchLoading(false);
    }
  }, [authFetch, search]);

  const fetchSentInvites = useCallback(async () => {
    setSentLoading(true);
    try {
      const res = await authFetch(`${API}/invites/sent`);
      if (res.ok) {
        const data = await res.json();
        setSentInvites(data.invites || []);
      }
    } catch {
      /* ignore */
    } finally {
      setSentLoading(false);
    }
  }, [authFetch]);

  const fetchReceivedInvites = useCallback(async () => {
    setReceivedLoading(true);
    try {
      const res = await authFetch(`${API}/invites/received`);
      if (res.ok) {
        const data = await res.json();
        setReceivedInvites(data.invites || []);
      }
    } catch {
      /* ignore */
    } finally {
      setReceivedLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    if (isAdmin && hasBusiness) {
      fetchSentInvites();
    }
    // All users can see received invites
    fetchReceivedInvites();
  }, [isAdmin, hasBusiness, fetchSentInvites, fetchReceivedInvites]);

  /* ── Handlers ─────────────────────────────────────────────── */
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    searchUsers();
  };

  const handleSendInvite = async (toUserId: number) => {
    setError("");
    setMessage("");
    setSendingTo(toUserId);
    try {
      const res = await authFetch(`${API}/invites`, {
        method: "POST",
        body: JSON.stringify({ to_user_id: toUserId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to send invite");
      }
      setMessage("Invite sent successfully!");
      setTimeout(() => setMessage(""), 3000);
      // Refresh both lists
      searchUsers();
      fetchSentInvites();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setSendingTo(null);
    }
  };

  const handleAccept = async (inviteId: number) => {
    setError("");
    setMessage("");
    setActioningId(inviteId);
    try {
      const res = await authFetch(`${API}/invites/${inviteId}/accept`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to accept invite");
      }
      setMessage("Invite accepted! You've joined the business.");
      // Refresh user data from server
      const meRes = await authFetch(`${API}/auth/me`);
      if (meRes.ok) {
        const freshUser = await meRes.json();
        updateUser(freshUser);
      }
      fetchReceivedInvites();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setActioningId(null);
    }
  };

  const handleReject = async (inviteId: number) => {
    setError("");
    setMessage("");
    setActioningId(inviteId);
    try {
      const res = await authFetch(`${API}/invites/${inviteId}/reject`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to reject invite");
      }
      setMessage("Invite rejected.");
      setTimeout(() => setMessage(""), 3000);
      fetchReceivedInvites();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setActioningId(null);
    }
  };

  const statusBadge = (s: string) => {
    if (s === "pending")
      return (
        <span className="inv-status inv-status--pending">
          <Clock size={13} /> Pending
        </span>
      );
    if (s === "accepted")
      return (
        <span className="inv-status inv-status--accepted">
          <CheckCircle2 size={13} /> Accepted
        </span>
      );
    return (
      <span className="inv-status inv-status--rejected">
        <XCircle size={13} /> Rejected
      </span>
    );
  };

  /* ── Render ───────────────────────────────────────────────── */
  return (
    <div className="page invites-page">
      <h2 className="page-title">
        {isAdmin && hasBusiness ? "Manage Invites" : "My Invites"}
      </h2>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      {/* ── ADMIN VIEW: Search + Send + Sent invites ────────── */}
      {isAdmin && hasBusiness && (
        <>
          {/* Search users without business */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header-row">
              <UserPlus size={20} />
              <h3>Invite Users</h3>
            </div>
            <p style={{ color: "var(--text-secondary)", marginBottom: 12 }}>
              Search for users who haven't joined a business yet and send them
              an invite.
            </p>
            <form
              onSubmit={handleSearch}
              style={{ display: "flex", gap: 8, marginBottom: 16 }}
            >
              <div className="search-box" style={{ flex: 1 }}>
                <Search size={16} />
                <input
                  type="text"
                  placeholder="Search by name or email..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <button type="submit" className="btn btn-primary">
                Search
              </button>
            </form>

            {searchLoading ? (
              <div className="loading">Searching...</div>
            ) : availableUsers.length > 0 ? (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Joined</th>
                      <th style={{ width: 120 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {availableUsers.map((u) => (
                      <tr key={u.id}>
                        <td className="td-bold">{u.name}</td>
                        <td>{u.email}</td>
                        <td>{new Date(u.created_at).toLocaleDateString()}</td>
                        <td>
                          <button
                            className="btn btn-primary btn-sm"
                            disabled={sendingTo === u.id}
                            onClick={() => handleSendInvite(u.id)}
                          >
                            <Send size={14} />{" "}
                            {sendingTo === u.id ? "Sending..." : "Invite"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : search ? (
              <p style={{ color: "var(--text-secondary)" }}>
                No users found matching "{search}".
              </p>
            ) : null}
          </div>

          {/* Sent invites */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header-row">
              <Send size={20} />
              <h3>Sent Invites</h3>
            </div>
            {sentLoading ? (
              <div className="loading">Loading...</div>
            ) : sentInvites.length === 0 ? (
              <p style={{ color: "var(--text-secondary)" }}>
                No invites sent yet.
              </p>
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Invited User</th>
                      <th>Email</th>
                      <th>Status</th>
                      <th>Sent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sentInvites.map((inv) => (
                      <tr key={inv.id}>
                        <td className="td-bold">{inv.to_user_name}</td>
                        <td>{inv.to_user_email}</td>
                        <td>{statusBadge(inv.status)}</td>
                        <td>{new Date(inv.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── RECEIVED INVITES (visible to all) ───────────────── */}
      <div className="card">
        <div className="card-header-row">
          <Inbox size={20} />
          <h3>Received Invites</h3>
        </div>
        {receivedLoading ? (
          <div className="loading">Loading...</div>
        ) : receivedInvites.length === 0 ? (
          <p style={{ color: "var(--text-secondary)" }}>No invites received.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Location</th>
                  <th>Invited By</th>
                  <th>Status</th>
                  <th>Received</th>
                  <th style={{ width: 160 }}></th>
                </tr>
              </thead>
              <tbody>
                {receivedInvites.map((inv) => (
                  <tr key={inv.id}>
                    <td className="td-bold">{inv.business_name}</td>
                    <td>{inv.business_location || "—"}</td>
                    <td>{inv.from_user_name}</td>
                    <td>{statusBadge(inv.status)}</td>
                    <td>{new Date(inv.created_at).toLocaleDateString()}</td>
                    <td>
                      {inv.status === "pending" && (
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            className="btn btn-primary btn-sm"
                            disabled={actioningId === inv.id}
                            onClick={() => handleAccept(inv.id)}
                          >
                            <Check size={14} /> Accept
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            disabled={actioningId === inv.id}
                            onClick={() => handleReject(inv.id)}
                          >
                            <X size={14} /> Reject
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
