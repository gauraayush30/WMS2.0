import { useNavigate } from "react-router-dom";
import {
  TrendingUp,
  ArrowUpDown,
  Recycle,
  LayoutGrid,
  Activity,
  Download,
  Upload,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";

const reports = [
  {
    to: "/reports/fast-slow-moving",
    icon: TrendingUp,
    label: "Fast vs Slow Moving Goods",
    description:
      "Classify products by outbound movement speed over a configurable period.",
    color: "bg-emerald-50 text-emerald-600",
  },
  {
    to: "/reports/inbound-outbound",
    icon: ArrowUpDown,
    label: "Inbound vs Outbound",
    description:
      "View top inbound & outbound products and track movement trends over time.",
    color: "bg-blue-50 text-blue-600",
  },
  {
    to: "/reports/fifo-fefo",
    icon: Recycle,
    label: "FIFO / FEFO + Aging",
    description:
      "Pick-strategy compliance, age buckets, and ₹-at-risk for expiring stock.",
    color: "bg-amber-50 text-amber-600",
  },
  {
    to: "/reports/complete-analysis",
    icon: LayoutGrid,
    label: "Complete Analysis",
    description:
      "Single-SKU 360 view: inbound, outbound, stock curve, revenue, COGS, margin, DIO, turns.",
    color: "bg-violet-50 text-violet-600",
  },
  {
    to: "/reports/behavior",
    icon: Activity,
    label: "Behavior Analysis",
    description:
      "ABC × XYZ matrix and lifecycle classification across all SKUs.",
    color: "bg-rose-50 text-rose-600",
  },
  {
    to: "/reports/inbound-details",
    icon: Download,
    label: "Inbound Details",
    description:
      "Detailed view of stock-in records, including seller location, pricing, and batch details.",
    color: "bg-teal-50 text-teal-600",
  },
  {
    to: "/reports/outbound-details",
    icon: Upload,
    label: "Outbound Details",
    description:
      "Detailed view of stock-out records, including buyer location, pricing, and batch details.",
    color: "bg-orange-50 text-orange-600",
  },
];

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.05, duration: 0.35 },
  }),
};

export default function ReportsPage() {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Reports</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Analytical reports for your business
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {reports.map((report, i) => {
          const Icon = report.icon;
          return (
            <motion.div
              key={report.to}
              custom={i}
              initial="hidden"
              animate="show"
              variants={fadeUp}
            >
              <Card
                className="cursor-pointer transition-shadow hover:shadow-md"
                onClick={() => navigate(report.to)}
              >
                <CardContent className="flex items-start gap-4 p-5">
                  <div
                    className={`flex items-center justify-center h-11 w-11 rounded-lg shrink-0 ${report.color}`}
                  >
                    <Icon size={20} />
                  </div>
                  <div>
                    <p className="font-medium">{report.label}</p>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      {report.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
