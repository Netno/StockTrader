"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart2, LayoutDashboard, LineChart, TrendingUp, Clock, Lightbulb, LogOut } from "lucide-react";
import { signOut } from "next-auth/react";

const links = [
  { href: "/dashboard",             label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/stocks",      label: "Aktier",    icon: LineChart },
  { href: "/dashboard/signals",     label: "Signaler",  icon: TrendingUp },
  { href: "/dashboard/history",     label: "Historik",  icon: Clock },
  { href: "/dashboard/suggestions", label: "Forslag",   icon: Lightbulb },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col py-6 px-3">
      <div className="px-3 mb-8">
        <div className="flex items-center gap-2">
          <BarChart2 className="text-blue-400" size={20} />
          <span className="font-bold text-lg tracking-tight">Aktiemotor</span>
        </div>
      </div>

      <nav className="flex-1 space-y-1">
        {links.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition ${
                active
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={() => signOut({ callbackUrl: "/login" })}
        className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-white hover:bg-gray-800 transition"
      >
        <LogOut size={16} />
        Logga ut
      </button>
    </aside>
  );
}
