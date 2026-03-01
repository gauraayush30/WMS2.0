import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Building2, UserPlus, ChevronRight, Mail } from "lucide-react";

export default function BusinessPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <div className="page">
      <h2 className="page-title">Business</h2>

      <div className="inv-hub-tiles">
        {/* Business Details tile – visible to admins (or anyone to create) */}
        <Link to="/business/details" className="inv-hub-tile">
          <div
            className="inv-hub-tile__icon"
            style={{ background: "var(--hub-blue)" }}
          >
            <Building2 size={28} />
          </div>
          <div className="inv-hub-tile__body">
            <span className="inv-hub-tile__title">Business Details</span>
            <span className="inv-hub-tile__desc">
              {user?.business_id
                ? "View and update your business information"
                : "Create your business to get started"}
            </span>
          </div>
          <ChevronRight size={20} className="inv-hub-tile__arrow" />
        </Link>

        {/* Invites tile */}
        <Link to="/business/invites" className="inv-hub-tile">
          <div
            className="inv-hub-tile__icon"
            style={{ background: "var(--hub-purple)" }}
          >
            {isAdmin ? <UserPlus size={28} /> : <Mail size={28} />}
          </div>
          <div className="inv-hub-tile__body">
            <span className="inv-hub-tile__title">
              {isAdmin ? "Manage Invites" : "My Invites"}
            </span>
            <span className="inv-hub-tile__desc">
              {isAdmin
                ? "Invite users to your business and track sent invites"
                : "View and respond to business invitations"}
            </span>
          </div>
          <ChevronRight size={20} className="inv-hub-tile__arrow" />
        </Link>
      </div>
    </div>
  );
}
