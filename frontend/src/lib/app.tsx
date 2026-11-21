import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, setToken, getToken, setUnauthorizedHandler } from "./api";
import type { User } from "./types";

// ---------------------------------------------------------------- auth
interface AuthCtx {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (d: { email: string; password: string; first_name: string; last_name: string }) => Promise<void>;
  logout: () => Promise<void>; refresh: () => Promise<void>;
}
const Auth = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(Auth);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  const refresh = useCallback(async () => {
    try { setUser(await api<User>("/me/")); } catch { setUser(null); setToken(null); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => { setToken(null); setUser(null); });
    if (getToken()) refresh();
  }, [refresh]);

  const finish = async (r: { token: string }) => { setToken(r.token); await refresh(); };
  const value: AuthCtx = {
    user, loading, refresh,
    login: async (email, password) => finish(await api("/auth/login/", { method: "POST", body: { email, password } })),
    register: async (d) => finish(await api("/auth/register/", { method: "POST", body: d })),
    logout: async () => { try { await api("/auth/logout/", { method: "POST" }); } catch { /* already logged out */ } setToken(null); setUser(null); },
  };
  return <Auth.Provider value={value}>{children}</Auth.Provider>;
}

// ---------------------------------------------------------------- theme
export function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("jp_theme", next ? "dark" : "light"); } catch { /* ignore */ }
    setDark(next);
  };
  return { dark, toggle };
}

// ---------------------------------------------------------------- toasts
type Toast = { id: number; kind: "ok" | "err"; text: string };
const ToastCtx = createContext<(text: string, kind?: "ok" | "err") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const n = useRef(0);
  const push = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    const id = ++n.current;
    setItems((x) => [...x.slice(-3), { id, kind, text }]); // keep at most 4 visible
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), kind === "err" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 left-4 sm:left-auto z-[100] flex flex-col gap-2 sm:w-96" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`fade-up rounded-xl px-4 py-3 text-sm shadow-lg border flex gap-2 items-start ${t.kind === "err" ? "bg-red-50 text-red-900 border-red-200 dark:bg-red-950 dark:text-red-100 dark:border-red-900" : "bg-emerald-50 text-emerald-900 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-100 dark:border-emerald-900"}`}>
            <span aria-hidden>{t.kind === "err" ? "⚠️" : "✓"}</span><span className="flex-1">{t.text}</span>
            <button className="opacity-60 hover:opacity-100" aria-label="Dismiss" onClick={() => setItems((x) => x.filter((i) => i.id !== t.id))}>✕</button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------------------------------------------------------------- data hook
export function useLoad<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const run = useCallback(async () => {
    const my = ++seq.current;
    setLoading(true); setError(null);
    try { const d = await fn(); if (my === seq.current) setData(d); }
    catch (e: any) { if (my === seq.current) setError(e.message || "Something went wrong."); }
    finally { if (my === seq.current) setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run, setData };
}

// ---------------------------------------------------------------- formatting
export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "");
export const fmtDateTime = (s?: string | null) => (s ? new Date(s).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "");
export function timeAgo(s?: string | null) {
  if (!s) return "";
  const m = Math.round((Date.now() - new Date(s).getTime()) / 60000);
  if (m < 1) return "just now"; if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60); if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
export const STATUS_LABEL: Record<string, string> = {
  wishlist: "Wishlist", preparing: "Preparing", applied: "Applied", interviewing: "Interviewing", offer: "Offer", rejected: "Rejected", withdrawn: "Withdrawn",
};
/** datetime-local value (local time) for N hours from now. */
export const localInput = (hoursFromNow = 24) => {
  const d = new Date(Date.now() + hoursFromNow * 3600_000 - new Date().getTimezoneOffset() * 60_000);
  return d.toISOString().slice(0, 16);
};
