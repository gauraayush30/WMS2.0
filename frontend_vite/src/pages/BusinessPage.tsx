import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Building2, UserPlus, ChevronRight, Mail, MapPin } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { motion } from "framer-motion";

export default function BusinessPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const tiles = [
    {
      to: "/business/details",
      icon: Building2,
      title: "Business Details",
      desc: user?.business_id
        ? "View and update your business information"
        : "Create your business to get started",
      color: "bg-blue-50 text-blue-600",
    },
    {
      to: "/business/invites",
      icon: isAdmin ? UserPlus : Mail,
      title: isAdmin ? "Manage Invites" : "My Invites",
      desc: isAdmin
        ? "Invite users to your business and track sent invites"
        : "View and respond to business invitations",
      color: "bg-amber-50 text-amber-600",
    },
    {
      to: "/business/delivery-locations",
      icon: MapPin,
      title: "Delivery Locations",
      desc: "Manage delivery locations for your business",
      color: "bg-emerald-50 text-emerald-600",
    },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Business</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {tiles.map((tile, i) => (
          <motion.div key={tile.to} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
            <Link to={tile.to} className="block">
              <Card className="transition-all hover:shadow-md hover:border-primary/40">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <span className={`h-8 w-8 rounded-lg flex items-center justify-center ${tile.color}`}>
                      <tile.icon size={16} />
                    </span>
                    {tile.title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>{tile.desc}</span>
                  <ChevronRight size={16} />
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
