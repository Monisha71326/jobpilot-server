import { useEffect, useId, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(" ");

// ---------------------------------------------------------------- Button
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md"; loading?: boolean };
export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }: BtnProps) {
  const v = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm shadow-brand-600/20",
    secondary: "border border-c surface-2 hover:brightness-95 dark:hover:brightness-125",
    ghost: "hover:surface-2 muted hover:text-[var(--text)]",
    danger: "bg-red-600 text-white hover:bg-red-700",
  }[variant];
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx("inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer", size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2.5 text-sm", v, className)}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}

export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={cx("spinner", className)} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// ---------------------------------------------------------------- Fields
const inputCls = "w-full rounded-xl border border-c bg-[var(--surface)] px-3 py-2.5 text-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30";
export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">{label}</label>
      {children(id)}
      {hint && !error && <p className="text-xs muted">{hint}</p>}
      {error && <p className="text-xs text-red-600 dark:text-red-400" role="alert">{error}</p>}
    </div>
  );
}
export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) { return <input {...p} className={cx(inputCls, className)} />; }
export function Textarea({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea {...p} className={cx(inputCls, "leading-relaxed", className)} />; }
export function Select({ className, ...p }: SelectHTMLAttributes<HTMLSelectElement>) { return <select {...p} className={cx(inputCls, "pr-8", className)} />; }

// ---------------------------------------------------------------- Display
export function Card({ children, className, pad = true }: { children: ReactNode; className?: string; pad?: boolean }) {
  return <div className={cx("card", pad && "p-5", className)}>{children}</div>;
}
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm muted max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
const tones: Record<string, string> = {
  gray: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  brand: "bg-brand-100 text-brand-700 dark:bg-brand-600/20 dark:text-brand-200",
  green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  amber: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  red: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
  blue: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
};
export function Badge({ children, tone = "gray", title }: { children: ReactNode; tone?: keyof typeof tones; title?: string }) {
  return <span title={title} className={cx("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap", tones[tone])}>{children}</span>;
}
export function scoreTone(score: number | null | undefined) {
  if (score == null) return "gray";
  return score >= 75 ? "green" : score >= 60 ? "blue" : score >= 40 ? "amber" : "red";
}
export function ScoreRing({ score, size = 56, label }: { score: number | null | undefined; size?: number; label?: string }) {
  if (score == null) return <div className="text-xs muted text-center" style={{ width: size }}>No score</div>;
  const r = (size - 8) / 2, c = 2 * Math.PI * r;
  const color = score >= 75 ? "#10b981" : score >= 60 ? "#0ea5e9" : score >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`${label ?? "Score"} ${score} out of 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth="5" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)} />
      </svg>
      <span className="absolute inset-0 grid place-items-center text-sm font-semibold">{score}</span>
    </div>
  );
}
export function Bar({ value, max = 100, tone = "brand" }: { value: number; max?: number; tone?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = tone === "green" ? "bg-emerald-500" : tone === "amber" ? "bg-amber-500" : "bg-brand-500";
  return <div className="h-2 w-full rounded-full surface-2 overflow-hidden"><div className={cx("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} /></div>;
}
export function Skill({ children, state }: { children: ReactNode; state?: "have" | "missing" }) {
  return <Badge tone={state === "have" ? "green" : state === "missing" ? "red" : "gray"}>{state === "have" ? "✓ " : state === "missing" ? "✗ " : ""}{children}</Badge>;
}
export function EngineBadge({ engine, model }: { engine?: string; model?: string }) {
  if (!engine) return null;
  return engine === "ollama"
    ? <Badge tone="brand" title="Generated by your local open-source model">Local AI{model ? ` · ${model}` : ""}</Badge>
    : <Badge tone="gray" title="Generated by built-in rules. Install Ollama for AI-written text.">Rule-based</Badge>;
}

// ---------------------------------------------------------------- States
export function Loading({ text = "Loading…" }: { text?: string }) {
  return <div className="flex items-center justify-center gap-3 py-16 muted" role="status"><Spinner /> <span className="text-sm">{text}</span></div>;
}
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card p-8 text-center" role="alert">
      <div className="text-3xl mb-2" aria-hidden>⚠️</div>
      <p className="text-sm mb-4">{message}</p>
      {onRetry && <Button variant="secondary" onClick={onRetry}>Try again</Button>}
    </div>
  );
}
export function Empty({ icon = "📭", title, text, action }: { icon?: string; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="card border-dashed p-10 text-center">
      <div className="text-4xl mb-3" aria-hidden>{icon}</div>
      <h3 className="font-semibold">{title}</h3>
      {text && <p className="text-sm muted mt-1 max-w-md mx-auto">{text}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}
export function Notice({ tone = "amber", children }: { tone?: "amber" | "blue" | "green" | "red"; children: ReactNode }) {
  const t = {
    amber: "bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
    blue: "bg-sky-50 border-sky-200 text-sky-900 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
    green: "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
    red: "bg-red-50 border-red-200 text-red-900 dark:bg-red-500/10 dark:border-red-500/30 dark:text-red-200",
  }[tone];
  return <div className={cx("rounded-xl border px-4 py-3 text-sm", t)}>{children}</div>;
}

// ---------------------------------------------------------------- Modal / Tabs
export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; prev?.focus(); };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm" onClick={onClose} />
      <div ref={ref} tabIndex={-1} className={cx("card fade-up relative w-full max-h-[92vh] overflow-y-auto rounded-b-none sm:rounded-b-2xl p-5 sm:p-6", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close dialog" className="rounded-lg p-1.5 muted hover:surface-2 cursor-pointer">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-xl surface-2 p-1">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cx("rounded-lg px-3.5 py-1.5 text-sm font-medium transition cursor-pointer", value === t.id ? "bg-[var(--surface)] shadow-sm" : "muted hover:text-[var(--text)]")}>
          {t.label}
        </button>
      ))}
    </div>
  );
}
export function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null;
  return (
    <div className="mt-5 flex items-center justify-center gap-3 text-sm">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>← Previous</Button>
      <span className="muted">Page {page} of {pages}</span>
      <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next →</Button>
    </div>
  );
}
/** Comma/enter separated tag editor for skills, roles and locations. */
export function TagInput({ value, onChange, placeholder, id }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string; id?: string }) {
  const ref = useRef<HTMLInputElement>(null);
  const add = (raw: string) => {
    const items = raw.split(",").map((s) => s.trim()).filter(Boolean);
    if (!items.length) return;
    const seen = new Set(value.map((v) => v.toLowerCase()));
    onChange([...value, ...items.filter((i) => !seen.has(i.toLowerCase()) && seen.add(i.toLowerCase()))]);
    if (ref.current) ref.current.value = "";
  };
  return (
    <div className={cx(inputCls, "flex flex-wrap gap-1.5 !py-2")} onClick={() => ref.current?.focus()}>
      {value.map((v) => (
        <span key={v} className="inline-flex items-center gap-1 rounded-full bg-brand-100 text-brand-700 dark:bg-brand-600/20 dark:text-brand-200 px-2.5 py-0.5 text-xs font-medium">
          {v}<button type="button" aria-label={`Remove ${v}`} className="opacity-60 hover:opacity-100 cursor-pointer" onClick={() => onChange(value.filter((x) => x !== v))}>✕</button>
        </span>
      ))}
      <input id={id} ref={ref} placeholder={value.length ? "" : placeholder} className="min-w-[8rem] flex-1 bg-transparent outline-none text-sm"
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add((e.target as HTMLInputElement).value); } else if (e.key === "Backspace" && !(e.target as HTMLInputElement).value && value.length) onChange(value.slice(0, -1)); }}
        onBlur={(e) => add(e.target.value)} />
    </div>
  );
}
export { cx };
