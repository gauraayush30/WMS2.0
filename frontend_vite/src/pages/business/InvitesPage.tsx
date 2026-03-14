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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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

  const [search, setSearch] = useState("");
  const [availableUsers, setAvailableUsers] = useState<AvailableUser[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [sentInvites, setSentInvites] = useState<SentInvite[]>([]);
  const [sentLoading, setSentLoading] = useState(false);
  const [sendingTo, setSendingTo] = useState<number | null>(null);

  const [receivedInvites, setReceivedInvites] = useState<ReceivedInvite[]>([]);
  const [receivedLoading, setReceivedLoading] = useState(false);
  const [actioningId, setActioningId] = useState<number | null>(null);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

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
    } finally {
      setReceivedLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    if (isAdmin && hasBusiness) fetchSentInvites();
    fetchReceivedInvites();
  }, [isAdmin, hasBusiness, fetchSentInvites, fetchReceivedInvites]);

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
      setTimeout(() => setMessage(""), 2500);
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
      const res = await authFetch(`${API}/invites/${inviteId}/accept`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to accept invite");
      }
      setMessage("Invite accepted! You joined the business.");
      const meRes = await authFetch(`${API}/auth/me`);
      if (meRes.ok) updateUser(await meRes.json());
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
      const res = await authFetch(`${API}/invites/${inviteId}/reject`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to reject invite");
      }
      setMessage("Invite rejected.");
      setTimeout(() => setMessage(""), 2000);
      fetchReceivedInvites();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setActioningId(null);
    }
  };

  const statusBadge = (s: string) => {
    if (s === "pending") return <Badge variant="warning"><Clock size={12} className="mr-1" />Pending</Badge>;
    if (s === "accepted") return <Badge variant="success"><CheckCircle2 size={12} className="mr-1" />Accepted</Badge>;
    return <Badge variant="destructive"><XCircle size={12} className="mr-1" />Rejected</Badge>;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">{isAdmin && hasBusiness ? "Manage Invites" : "My Invites"}</h2>

      {error && <Alert variant="destructive">{error}</Alert>}
      {message && <Alert variant="success">{message}</Alert>}

      {isAdmin && hasBusiness && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2"><UserPlus size={16} /> Invite Users</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">Search for users who have not joined a business and send invites.</p>
              <form onSubmit={handleSearch} className="flex gap-2">
                <Input placeholder="Search by name or email..." value={search} onChange={(e) => setSearch(e.target.value)} />
                <Button type="submit"><Search size={14} /> Search</Button>
              </form>

              {searchLoading ? (
                <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
              ) : availableUsers.length > 0 ? (
                <div className="rounded-lg border overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Joined</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {availableUsers.map((u) => (
                        <TableRow key={u.id}>
                          <TableCell className="text-sm font-medium">{u.name}</TableCell>
                          <TableCell className="text-sm">{u.email}</TableCell>
                          <TableCell className="text-sm">{new Date(u.created_at).toLocaleDateString()}</TableCell>
                          <TableCell>
                            <Button size="sm" disabled={sendingTo === u.id} onClick={() => handleSendInvite(u.id)}>
                              <Send size={13} /> {sendingTo === u.id ? "Sending..." : "Invite"}
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : search ? (
                <p className="text-sm text-muted-foreground">No users found matching "{search}".</p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2"><Send size={16} /> Sent Invites</CardTitle>
            </CardHeader>
            <CardContent>
              {sentLoading ? (
                <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
              ) : sentInvites.length === 0 ? (
                <p className="text-sm text-muted-foreground">No invites sent yet.</p>
              ) : (
                <div className="rounded-lg border overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Invited User</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Sent</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sentInvites.map((inv) => (
                        <TableRow key={inv.id}>
                          <TableCell className="text-sm font-medium">{inv.to_user_name}</TableCell>
                          <TableCell className="text-sm">{inv.to_user_email}</TableCell>
                          <TableCell>{statusBadge(inv.status)}</TableCell>
                          <TableCell className="text-sm">{new Date(inv.created_at).toLocaleDateString()}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2"><Inbox size={16} /> Received Invites</CardTitle>
        </CardHeader>
        <CardContent>
          {receivedLoading ? (
            <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}</div>
          ) : receivedInvites.length === 0 ? (
            <p className="text-sm text-muted-foreground">No invites received.</p>
          ) : (
            <div className="rounded-lg border overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Business</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Invited By</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Received</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {receivedInvites.map((inv) => (
                    <TableRow key={inv.id}>
                      <TableCell className="text-sm font-medium">{inv.business_name}</TableCell>
                      <TableCell className="text-sm">{inv.business_location || "-"}</TableCell>
                      <TableCell className="text-sm">{inv.from_user_name}</TableCell>
                      <TableCell>{statusBadge(inv.status)}</TableCell>
                      <TableCell className="text-sm">{new Date(inv.created_at).toLocaleDateString()}</TableCell>
                      <TableCell>
                        {inv.status === "pending" && (
                          <div className="flex gap-2">
                            <Button size="sm" disabled={actioningId === inv.id} onClick={() => handleAccept(inv.id)}>
                              <Check size={13} /> Accept
                            </Button>
                            <Button size="sm" variant="destructive" disabled={actioningId === inv.id} onClick={() => handleReject(inv.id)}>
                              <X size={13} /> Reject
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
