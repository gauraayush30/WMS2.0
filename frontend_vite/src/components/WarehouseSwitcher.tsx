import { useEffect, useState } from "react";
import { Warehouse as WarehouseIcon } from "lucide-react";

import { API, useAuth } from "../context/AuthContext";

interface Warehouse {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
}

export default function WarehouseSwitcher() {
  const { authFetch, selectedWarehouseId, setSelectedWarehouseId } = useAuth();
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    authFetch(`${API}/warehouses`)
      .then((r) => (r.ok ? r.json() : { warehouses: [] }))
      .then((data) => {
        if (!mounted) return;
        setWarehouses(data.warehouses || []);
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [authFetch]);

  // If only one warehouse exists, hide the switcher (no choice to make).
  if (!loading && warehouses.length <= 1) return null;

  return (
    <div className="flex items-center gap-2 text-sm">
      <WarehouseIcon size={14} className="text-muted-foreground" />
      <select
        className="flex h-8 w-44 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        value={selectedWarehouseId === null ? "ALL" : String(selectedWarehouseId)}
        onChange={(e) =>
          setSelectedWarehouseId(
            e.target.value === "ALL" ? null : Number(e.target.value)
          )
        }
      >
        <option value="ALL">All warehouses</option>
        {warehouses.map((w) => (
          <option key={w.id} value={String(w.id)}>
            {w.name} {w.code ? `(${w.code})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
