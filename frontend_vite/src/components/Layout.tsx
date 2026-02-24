import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Layout() {
  return (
    <div className="layout">
      <Sidebar />
      <div className="layout-main">
        <TopBar />
        <div className="layout-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
