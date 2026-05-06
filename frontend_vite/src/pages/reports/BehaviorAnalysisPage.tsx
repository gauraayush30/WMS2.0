import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

import { API, useAuth } from "../../context/AuthContext";
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

interface ProductRow {
  product_id: number;
  name: string;
  sku_code: string;
  revenue: number;
  units_sold: number;
  active_days: number;
  mean_qty: number;
  std_qty: number;
  cv: number;
  abc_class: "A" | "B" | "C";
  xyz_class: "X" | "Y" | "Z";
  lifecycle: "Active" | "New" | "Dormant";
}

interface BehaviorPayload {
  products: ProductRow[];
  matrix: Record<"A" | "B" | "C", Record<"X" | "Y" | "Z", number>>;
  total_revenue: number;
  window_days: number;
}

const fmtINR = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

const ABC_HINT: Record<string, string> = {
  A: "top 80% revenue",
  B: "next 15% revenue",
  C: "last 5% revenue",
};
const XYZ_HINT: Record<string, string> = {
  X: "stable demand (CV ≤ 0.5)",
  Y: "variable demand (CV 0.5–1.0)",
  Z: "erratic demand (CV > 1.0)",
};

export default function BehaviorAnalysisPage() {
  const { authFetch, effectiveCustomerId } = useAuth();
  const [data, setData] = useState<BehaviorPayload | null>(null);

  useEffect(() => {
    const cs = effectiveCustomerId
      ? `&customer_id=${effectiveCustomerId}`
      : "";
    authFetch(`${API}/analytics/behavior?days=90${cs}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setData);
  }, [authFetch, effectiveCustomerId]);

  if (!data) return <div className="p-6 text-sm">Loading…</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-2">
        <Activity className="text-muted-foreground" />
        <h1 className="text-2xl font-semibold">Behavior analysis</h1>
      </div>

      <p className="text-sm text-muted-foreground">
        SKU segmentation across the last {data.window_days} days · total revenue{" "}
        {fmtINR(data.total_revenue)}.
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">ABC × XYZ matrix</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-2 text-center text-xs">
            <div></div>
            {(["X", "Y", "Z"] as const).map((x) => (
              <div key={x} className="font-semibold">
                {x}
                <div className="text-[10px] font-normal text-muted-foreground">
                  {XYZ_HINT[x]}
                </div>
              </div>
            ))}
            {(["A", "B", "C"] as const).map((a) => (
              <>
                <div key={`label-${a}`} className="font-semibold flex items-center justify-end pr-2">
                  {a}
                  <div className="text-[10px] font-normal text-muted-foreground ml-1">
                    {ABC_HINT[a]}
                  </div>
                </div>
                {(["X", "Y", "Z"] as const).map((x) => (
                  <div
                    key={`${a}${x}`}
                    className="rounded-md border bg-muted/30 p-3 text-2xl font-semibold"
                  >
                    {data.matrix[a][x]}
                  </div>
                ))}
              </>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">SKU breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Revenue</TableHead>
                <TableHead>Units</TableHead>
                <TableHead>Active days</TableHead>
                <TableHead>CV</TableHead>
                <TableHead>ABC</TableHead>
                <TableHead>XYZ</TableHead>
                <TableHead>Lifecycle</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.products.map((p) => (
                <TableRow key={p.product_id}>
                  <TableCell className="font-mono text-xs">{p.sku_code}</TableCell>
                  <TableCell>{p.name}</TableCell>
                  <TableCell>{fmtINR(Number(p.revenue))}</TableCell>
                  <TableCell>{p.units_sold}</TableCell>
                  <TableCell>{p.active_days}</TableCell>
                  <TableCell>{p.cv.toFixed(2)}</TableCell>
                  <TableCell>
                    <Badge variant={p.abc_class === "A" ? "default" : "secondary"}>
                      {p.abc_class}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={p.xyz_class === "X" ? "default" : "secondary"}
                    >
                      {p.xyz_class}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={p.lifecycle === "Active" ? "default" : "secondary"}
                    >
                      {p.lifecycle}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
