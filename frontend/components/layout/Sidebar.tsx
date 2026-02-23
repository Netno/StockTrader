"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart2, LayoutDashboard, LineChart, TrendingUp, Clock, Lightbulb, Settings, LogOut, Menu, X } from "lucide-react";
import { signOut } from "next-auth/react";
import { useState } from "react";

const links = [
  { href: "/dashboard",             label: "Dashboard",     icon: LayoutDashboard },
  { href: "/dashboard/stocks",      label: "Aktier",        icon: LineChart },
  { href: "/dashboard/signals",     label: "Signaler",      icon: TrendingUp },
  { href: "/dashboard/history",     label: "Historik",      icon: Clock },
  { href: "/dashboard/suggestions", label: "Förslag",       icon: Lightbulb },
  { href: "/dashboard/settings",    label: "Inställningar", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* ── Desktop sidebar ── */}
      <aside className="hidden md:flex w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex-col py-6 px-3">
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

      {/* ── Mobile top bar ── */}
      <header className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <BarChart2 className="text-blue-400" size={18} />
          <span className="font-bold text-base tracking-tight">Aktiemotor</span>
        </div>
        <button
          onClick={() => setOpen(true)}
          aria-label="Öppna meny"
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition"
        >
          <Menu size={22} />
        </button>
      </header>

      {/* ── Mobile drawer overlay ── */}
      {open && (
        <div
          className="md:hidden fixed inset-0 z-50 flex"
          role="dialog"
          aria-modal="true"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setOpen(false)}
          />

          {/* Slide-in panel */}
          <nav className="relative z-10 w-64 max-w-[80vw] bg-gray-900 border-r border-gray-800 flex flex-col py-6 px-3 h-full">
            {/* Header row */}
            <div className="flex items-center justify-between px-3 mb-8">
              <div className="flex items-center gap-2">
                <BarChart2 className="text-blue-400" size={18} />
                <span className="font-bold text-base tracking-tight">Aktiemotor</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label="Stäng meny"
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition"
              >
                <X size={20} />
              </button>
            </div>

            {/* Nav links */}
            <div className="flex-1 space-y-1">
              {links.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setOpen(false)}
                    className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm transition ${
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
            </div>

            {/* Logout */}
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="flex items-center gap-3 px-3 py-3 rounded-lg text-sm text-gray-500 hover:text-white hover:bg-gray-800 transition"
            >
              <LogOut size={16} />
              Logga ut
            </button>
          </nav>
        </div>
      )}
    </>
  );
}
