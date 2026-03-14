import { useAuth } from "../context/AuthContext";
import { LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-6 shrink-0">
      <h1 className="text-sm font-semibold text-foreground tracking-tight">
        Warehouse Management System
      </h1>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <User size={15} />
          <span className="font-medium text-foreground">{user?.name}</span>
          <Badge
            variant="secondary"
            className="text-[10px] uppercase tracking-wider"
          >
            {user?.role}
          </Badge>
        </div>
        <Separator orientation="vertical" className="h-5" />
        <Button
          variant="ghost"
          size="icon"
          onClick={logout}
          title="Logout"
          className="text-muted-foreground hover:text-destructive"
        >
          <LogOut size={16} />
        </Button>
      </div>
    </header>
  );
}
