import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { fmtDateTime, useAuth, useLoad, useTheme } from "../lib/app";
import type { Notification } from "../lib/types";
import { Button, cx } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▦", end: true },
  { to: "/jobs", label: "Find jobs", icon: "⌕" },
  { to: "/saved", label: "Saved jobs", icon: "☆" },
  { to: "/applications", label: "Applications", icon: "▤" },
  { to: "/resumes", label: "Resumes", icon: "▭" },
  { to: "/assistant", label: "AI assistant", icon: "✦" },
  { to: "/interview", label: "Interview practice", icon: "◉" },
  { to: "/skills", label: "Skills & roadmap", icon: "↗" },
  { to: "/reminders", label: "Reminders", icon: "◔" },
  { to: "/settings", label: "Profile & settings", icon: "⚙" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const nav = user?.is_staff ? [...NAV, { to: "/admin", label: "Admin", icon: "⛨" }] : NAV;

  return (
    <div className="min-h-screen lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[200] focus:rounded-lg focus:bg-brand-600 focus:px-3 focus:py-2 focus:text-white">Skip to content</a>
      {open && <div className="fixed inset-0 z-30 bg-slate-950/50 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={cx("fixed inset-y-0 left-0 z-40 w-64 border-r border-c bg-[var(--surface)] p-4 flex flex-col transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")} aria-label="Main navigation">
        <div className="flex items-center gap-2.5 px-2 py-2 mb-4">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-white font-bold">J</div>
          <div><div className="font-semibold leading-tight">JobPilot</div><div className="text-[11px] muted leading-tight">Free · runs on your machine</div></div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => cx("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition", isActive ? "bg-brand-50 text-brand-700 dark:bg-brand-600/20 dark:text-brand-200" : "muted hover:surface-2 hover:text-[var(--text)]")}>
              <span className="w-5 text-center text-base" aria-hidden>{n.icon}</span>{n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-3 border-t border-c pt-3">
          <div className="px-2 mb-2 text-xs muted truncate" title={user?.email}>{user?.first_name ? `${user.first_name} · ` : ""}{user?.email}</div>
          <Button variant="secondary" size="sm" className="w-full" onClick={logout}>Log out</Button>
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-c bg-[var(--surface)]/85 px-4 py-3 backdrop-blur sm:px-6">
          <button className="lg:hidden rounded-lg p-2 hover:surface-2 cursor-pointer" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(true)}>☰</button>
          <div className="flex-1" />
          <Bell />
          <button onClick={toggle} className="rounded-xl border border-c p-2 hover:surface-2 cursor-pointer" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} title="Toggle theme">{dark ? "☀️" : "🌙"}</button>
        </header>
        <main id="main" className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8"><Outlet /></main>
      </div>
    </div>
  );
}

function Bell() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const { data, reload } = useLoad(() => api<{ unread: number; results: Notification[] }>("/notifications/"), []);
  useEffect(() => { const t = setInterval(reload, 60000); return () => clearInterval(t); }, [reload]);
  const markAll = async () => { await api("/notifications/", { method: "POST", body: {} }); reload(); };
  return (
    <div className="relative">
      <button onClick={() => { setOpen(!open); if (!open) reload(); }} className="relative rounded-xl border border-c p-2 hover:surface-2 cursor-pointer" aria-label={`Notifications${data?.unread ? `, ${data.unread} unread` : ""}`} aria-expanded={open}>
        🔔{!!data?.unread && <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">{data.unread}</span>}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="card fade-up absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] p-2 shadow-xl">
            <div className="flex items-center justify-between px-3 py-2"><span className="font-semibold text-sm">Notifications</span>
              <Button variant="ghost" size="sm" onClick={markAll} disabled={!data?.unread}>Mark all read</Button></div>
            <div className="max-h-80 overflow-y-auto">
              {!data?.results.length && <p className="px-3 py-6 text-center text-sm muted">You're all caught up.</p>}
              {data?.results.map((n) => (
                <button key={n.id} onClick={() => { setOpen(false); if (n.link) nav(n.link); }} className={cx("block w-full rounded-lg px-3 py-2 text-left hover:surface-2 cursor-pointer", !n.is_read && "bg-brand-50/60 dark:bg-brand-600/10")}>
                  <div className="text-sm font-medium">{n.title}</div>
                  {n.body && <div className="text-xs muted">{n.body}</div>}
                  <div className="mt-0.5 text-[11px] muted">{fmtDateTime(n.created_at)}</div>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
