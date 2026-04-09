import { useEffect, useState, useCallback } from "react";
import { useAuth, API } from "../../context/AuthContext";
import {
  TrendingUp,
  TrendingDown,
  Ban,
  ArrowUpDown,
  Download,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { motion } from "framer-motion";

interface ReportItem {
  product_id: number;
  product_name: string;
  sku_code: string;
  price: number;
  current_stock: number;
  total_outbound: number;
  total_inbound: number;
  tx_count: number;
  avg_daily_outbound: number;
  category: "fast" | "medium" | "slow" | "non_moving";
}

interface ReportSummary {
  fast: number;
  medium: number;
  slow: number;
  non_moving: number;
  total: number;
}

interface ReportThresholds {
  fast_min: number;
  slow_max: number;
  avg_outbound: number;
}

interface ReportData {
  days: number;
  summary: ReportSummary;
  thresholds: ReportThresholds;
  items: ReportItem[];
}

const CATEGORY_CONFIG = {
  fast: {
    label: "Fast Moving",
    icon: TrendingUp,
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    badge: "success" as const,
  },
  medium: {
    label: "Medium Moving",
    icon: ArrowUpDown,
    color: "text-blue-600",
    bg: "bg-blue-50",
    badge: "default" as const,
  },
  slow: {
    label: "Slow Moving",
    icon: TrendingDown,
    color: "text-amber-600",
    bg: "bg-amber-50",
    badge: "warning" as const,
  },
  non_moving: {
    label: "Non-Moving",
    icon: Ban,
    color: "text-red-600",
    bg: "bg-red-50",
    badge: "destructive" as const,
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.05, duration: 0.35 },
  }),
};

export default function FastSlowMovingPage() {
  const { authFetch } = useAuth();
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState("30");
  const [filterCategory, setFilterCategory] = useState("all");
  const [search, setSearch] = useState("");

  const fetchReport = useCallback(() => {
    setLoading(true);
    authFetch(`${API}/reports/fast-slow-moving?days=${days}`)
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [authFetch, days]);

  // eslint-disable-next-line
  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const filteredItems = (data?.items ?? []).filter((item) => {
    if (filterCategory !== "all" && item.category !== filterCategory)
      return false;
    if (
      search &&
      !item.product_name.toLowerCase().includes(search.toLowerCase()) &&
      !item.sku_code.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    return true;
  });

  const exportCSV = () => {
    if (!filteredItems.length) return;
    const headers = [
      "Product",
      "SKU",
      "Category",
      "Total Outbound",
      "Total Inbound",
      "Avg Daily Outbound",
      "Current Stock",
      "Transactions",
      "Price",
    ];
    const rows = filteredItems.map((item) => [
      item.product_name,
      item.sku_code,
      CATEGORY_CONFIG[item.category].label,
      item.total_outbound,
      item.total_inbound,
      item.avg_daily_outbound,
      item.current_stock,
      item.tx_count,
      item.price,
    ]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `fast-slow-moving-${days}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  const summary = data?.summary ?? {
    fast: 0,
    medium: 0,
    slow: 0,
    non_moving: 0,
    total: 0,
  };

  const summaryCards = [
    { key: "fast" as const, count: summary.fast },
    { key: "medium" as const, count: summary.medium },
    { key: "slow" as const, count: summary.slow },
    { key: "non_moving" as const, count: summary.non_moving },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            Fast vs Slow Moving Goods
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Product movement analysis over the last{" "}
            <span className="font-medium">{days} days</span>
            {data?.thresholds && (
              <>
                {" "}
                &middot; Fast &ge; {data.thresholds.fast_min} units &middot;
                Slow &le; {data.thresholds.slow_max} units
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={days}
            onChange={(e) => setDays(e.target.value)}
            className="w-35"
          >
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
            <option value="60">Last 60 days</option>
            <option value="90">Last 90 days</option>
            <option value="180">Last 180 days</option>
            <option value="365">Last 365 days</option>
          </Select>
          <Button variant="outline" size="sm" onClick={exportCSV}>
            <Download size={16} className="mr-1.5" />
            Export
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((card, i) => {
          const cfg = CATEGORY_CONFIG[card.key];
          const Icon = cfg.icon;
          return (
            <motion.div
              key={card.key}
              custom={i}
              initial="hidden"
              animate="show"
              variants={fadeUp}
            >
              <Card
                className={`cursor-pointer transition-shadow hover:shadow-md ${
                  filterCategory === card.key ? "ring-2 ring-primary" : ""
                }`}
                onClick={() =>
                  setFilterCategory((prev) =>
                    prev === card.key ? "all" : card.key,
                  )
                }
              >
                <CardContent className="flex items-center gap-4 p-5">
                  <div
                    className={`flex items-center justify-center h-12 w-12 rounded-lg ${cfg.bg}`}
                  >
                    <Icon size={22} className={cfg.color} />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">{cfg.label}</p>
                    <p className="text-2xl font-bold">{card.count}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <Input
          placeholder="Search by product name or SKU..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Badge variant="outline" className="self-start px-3 py-1.5 text-sm">
          {filteredItems.length} product{filteredItems.length !== 1 ? "s" : ""}
        </Badge>
      </div>

      {/* Table */}
      {filteredItems.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No products found for the selected filters.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[30%]">Product</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Total Outbound</TableHead>
                  <TableHead className="text-right">Total Inbound</TableHead>
                  <TableHead className="text-right">Avg Daily Out</TableHead>
                  <TableHead className="text-right">Current Stock</TableHead>
                  <TableHead className="text-right">Transactions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((item) => {
                  const cfg = CATEGORY_CONFIG[item.category];
                  return (
                    <TableRow key={item.product_id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {item.sku_code}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={cfg.badge}>{cfg.label}</Badge>
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {item.total_outbound.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        {item.total_inbound.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        {item.avg_daily_outbound}
                      </TableCell>
                      <TableCell className="text-right">
                        {item.current_stock.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        {item.tx_count}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
