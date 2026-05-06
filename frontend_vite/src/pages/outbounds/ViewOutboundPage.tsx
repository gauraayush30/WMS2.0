import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Eye, Truck } from "lucide-react";

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

interface Line {
  id: number;
  product_id: number;
  requested_qty: number;
  picked_qty: number;
  unit_price: number;
  line_amount: number;
  avg_cogs: number;
}

interface Pick {
  id: number;
  outbound_line_id: number;
  stock_batch_id: number;
  qty: number;
  unit_cost: number;
}

interface Outbound {
  id: number;
  shipment_number: string;
  status: string;
  total_qty: number;
  total_amount: number;
  shipped_at: string;
  pick_strategy: string;
  so_number: string;
  notes: string;
  lines: Line[];
  picks: Pick[];
}

interface PlanLine {
  outbound_line_id: number;
  product_id: number;
  requested_qty: number;
  strategy: string;
  plan: { stock_batch_id: number; qty: number; unit_cost: number }[];
}

export default function ViewOutboundPage() {
  const { id } = useParams();
  const { authFetch } = useAuth();
  const navigate = useNavigate();
  const [order, setOrder] = useState<Outbound | null>(null);
  const [plan, setPlan] = useState<PlanLine[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const fetchOrder = async () => {
    const r = await authFetch(`${API}/outbounds/${id}`);
    if (r.ok) setOrder(await r.json());
  };

  useEffect(() => {
    fetchOrder();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const previewPlan = async () => {
    setError("");
    setBusy(true);
    const r = await authFetch(`${API}/outbounds/${id}/pick-plan`, {
      method: "POST",
    });
    setBusy(false);
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      setError(e.detail || "Failed to compute pick plan");
      return;
    }
    const d = await r.json();
    setPlan(d.lines);
  };

  const ship = async () => {
    setError("");
    setBusy(true);
    const r = await authFetch(`${API}/outbounds/${id}/ship`, { method: "POST" });
    setBusy(false);
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      setError(e.detail || "Failed to ship");
      return;
    }
    setPlan(null);
    setOrder(await r.json());
  };

  if (!order) return <div className="p-6 text-sm">Loading…</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => navigate("/outbounds")}>
            <ArrowLeft size={18} />
          </Button>
          <h1 className="text-2xl font-semibold font-mono">
            {order.shipment_number}
          </h1>
          <Badge>{order.status}</Badge>
          <Badge variant="outline">{order.pick_strategy}</Badge>
        </div>
        {order.status === "draft" && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={previewPlan} disabled={busy}>
              <Eye size={14} /> Preview pick plan
            </Button>
            <Button onClick={ship} disabled={busy}>
              <Truck size={14} />
              {busy ? "Shipping…" : "Ship (commit)"}
            </Button>
          </div>
        )}
      </div>

      {error && <div className="text-sm text-destructive">{error}</div>}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Header</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div>
            <div className="text-muted-foreground text-xs">SO #</div>
            <div>{order.so_number || "—"}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Shipped at</div>
            <div>{new Date(order.shipped_at).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Total</div>
            <div>
              ₹{Number(order.total_amount).toLocaleString("en-IN")} ·{" "}
              {order.total_qty} units
            </div>
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
                <TableHead>Requested</TableHead>
                <TableHead>Picked</TableHead>
                <TableHead>Unit price (₹)</TableHead>
                <TableHead>Avg COGS (₹)</TableHead>
                <TableHead>Line amount (₹)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {order.lines.map((l) => (
                <TableRow key={l.id}>
                  <TableCell className="font-mono text-xs">{l.product_id}</TableCell>
                  <TableCell>{l.requested_qty}</TableCell>
                  <TableCell>{l.picked_qty}</TableCell>
                  <TableCell>{Number(l.unit_price).toFixed(2)}</TableCell>
                  <TableCell>{Number(l.avg_cogs).toFixed(2)}</TableCell>
                  <TableCell>{Number(l.line_amount).toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {plan && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Pick plan preview ({order.pick_strategy})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {plan.map((pl) => (
              <div key={pl.outbound_line_id} className="border rounded p-3">
                <div className="text-sm font-medium">
                  Product #{pl.product_id} — request {pl.requested_qty}
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Stock batch</TableHead>
                      <TableHead>Qty to pick</TableHead>
                      <TableHead>Unit cost (₹)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pl.plan.map((p, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-mono text-xs">
                          #{p.stock_batch_id}
                        </TableCell>
                        <TableCell>{p.qty}</TableCell>
                        <TableCell>{p.unit_cost.toFixed(2)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {order.picks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Actual picks</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Line</TableHead>
                  <TableHead>Stock batch</TableHead>
                  <TableHead>Qty</TableHead>
                  <TableHead>Unit cost (₹)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.picks.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-mono text-xs">
                      L{p.outbound_line_id}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      #{p.stock_batch_id}
                    </TableCell>
                    <TableCell>{p.qty}</TableCell>
                    <TableCell>{Number(p.unit_cost).toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
