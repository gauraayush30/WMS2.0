import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Package,
  ArrowLeftRight,
  Building2,
  Users,
  ChevronLeft,
  ChevronRight,
  FileBarChart,
  Warehouse as WarehouseIcon,
  Briefcase,
  PackagePlus,
  Truck,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { Tooltip } from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "../context/AuthContext";

interface NavItem {
  to: string;
  icon: typeof LayoutDashboard;
  label: string;
  /** Roles that may see this item. Empty array = visible to all authenticated users. */
  roles?: string[];
}

const ALL_NAV_ITEMS: NavItem[] = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/products", icon: Package, label: "Products" },
  { to: "/inbounds", icon: PackagePlus, label: "Inbounds" },
  { to: "/outbounds", icon: Truck, label: "Outbounds" },
  { to: "/inventory", icon: ArrowLeftRight, label: "Inventory" },
  { to: "/customers", icon: Briefcase, label: "Customers", roles: ["warehouse_admin", "warehouse_staff"] },
  { to: "/warehouses", icon: WarehouseIcon, label: "Warehouses", roles: ["warehouse_admin", "warehouse_staff"] },
  { to: "/business", icon: Building2, label: "Business", roles: ["warehouse_admin"] },
  { to: "/reports", icon: FileBarChart, label: "Reports" },
  { to: "/users", icon: Users, label: "Users", roles: ["warehouse_admin"] },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { user } = useAuth();
  const role = user?.role || "";
  const navItems = ALL_NAV_ITEMS.filter(
    (item) => !item.roles || item.roles.includes(role),
  );

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-background transition-all duration-300 ease-in-out",
        collapsed ? "w-16" : "w-60",
      )}
    >
      {/* Brand */}
      <div className="flex h-14 items-center justify-between px-4">
        {!collapsed && (
          <span className="text-lg font-bold tracking-tight">WMS</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={cn(
            "inline-flex items-center justify-center rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors cursor-pointer",
            collapsed && "mx-auto",
          )}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <Separator />

      {/* Nav */}
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive =
            item.to === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.to);

          const link = (
            <NavLink
              key={item.to}
              to={item.to}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
                collapsed && "justify-center px-2",
              )}
            >
              <item.icon size={18} />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );

          return collapsed ? (
            <Tooltip key={item.to} content={item.label} side="right">
              {link}
            </Tooltip>
          ) : (
            link
          );
        })}
      </nav>
    </aside>
  );
}
