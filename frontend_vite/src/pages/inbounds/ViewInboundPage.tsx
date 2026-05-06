import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2 } from "lucide-react";

import { API, useAuth } from "../../context/AuthContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface InboundLine {
  id: number;
  product_id: number;
  expected_qty: number;
  received_qty: number;
  unit_cost: number;
  line_amount: number;
  expires_at: string | null;
  batch_code: string;
}

interface InboundOrder {
  id: number;
  grn_number: string;
  status: string;
  total_qty: number;
  total_amount: number;
  received_at: string;
  po_number: string;
  invoice_number: string;
  notes: string;
  lines: InboundLine[];
}

export default function ViewInboundPage() {
  const { id } = useParams();
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const [order, setOrder] = useState<InboundOrder | null>(null);
  const [committing, setCommitting] = useState(false);
  const [error, setError] = useState("");

  const fetchOrder = async () => {
    const r = await authFetch(`${API}/inbounds/${id}`);
    if (r.ok) setOrder(await r.json());
  };

  useEffect(() => {
    fetchOrder();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const receive = async () => {
    setError("");
    setCommitting(true);
    const r = await authFetch(`${API}/inbounds/${id}/receive`, { method: "POST" });
    setCommitting(false);
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      setError(e.detail || "Failed to receive");
      return;
    }
    setOrder(await r.json());
  };

  if (!order) return <div className="p-6 text-sm">Loading…</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => navigate("/inbounds")}>
            <ArrowLeft size={18} />
          </Button>
          <h1 className="text-2xl font-semibold font-mono">{order.grn_number}</h1>
          <Badge>{order.status}</Badge>
        </div>
        {order.status === "draft" && (
          <Button onClick={receive} disabled={committing}>
            <CheckCircle2 size={16} />
            {committing ? "Receiving…" : "Receive (commit to stock)"}
          </Button>
        )}
      </div>

      {error && <div className="text-sm text-destructive">{error}</div>}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Header</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div>
            <div className="text-muted-foreground text-xs">PO #</div>
            <div>{order.po_number || "—"}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Invoice #</div>
            <div>{order.invoice_number || "—"}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Received at</div>
            <div>{new Date(order.received_at).toLocaleString()}</div>
          </div>
          <div className="md:col-span-3">
            <div className="text-muted-foreground text-xs">Notes</div>
            <div>{order.notes || "—"}</div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Line items</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product #</TableHead>
                <TableHead>Expected</TableHead>
                <TableHead>Received</TableHead>
                <TableHead>Unit cost (₹)</TableHead>
                <TableHead>Line amount (₹)</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead>Batch</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {order.lines.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="font-mono text-xs">{l.product_id}</TableCell>
                  <TableCell>{l.expected_qty}</TableCell>
                  <TableCell>{l.received_qty}</TableCell>
                  <TableCell>{Number(l.unit_cost).toFixed(2)}</TableCell>
                  <TableCell>{Number(l.line_amount).toFixed(2)}</TableCell>
                  <TableCell>{l.expires_at || "—"}</TableCell>
                  <TableCell>{l.batch_code || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
