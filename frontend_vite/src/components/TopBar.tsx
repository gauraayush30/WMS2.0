import { useAuth } from "../context/AuthContext";
import { LogOut, User } from "lucide-react";

export default function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header className="topbar">
      <div className="topbar-left">
        <h1 className="topbar-title">Warehouse Management System</h1>
      </div>
      <div className="topbar-right">
        <div className="topbar-user">
          <User size={16} />
          <span>{user?.name}</span>
          <span className="topbar-role">{user?.role}</span>
        </div>
        <button className="topbar-logout" onClick={logout} title="Logout">
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
