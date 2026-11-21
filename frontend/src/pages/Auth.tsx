import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Button, Field, Input, Notice } from "../components/ui";
import { useAuth, useTheme } from "../lib/app";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, login, register } = useAuth();
  const nav = useNavigate();
  const { dark, toggle } = useTheme();
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (mode === "login") await login(f.email, f.password); else await register(f);
      nav("/", { replace: true });
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-600 to-indigo-900 p-12 text-white">
        <div className="flex items-center gap-2.5"><div className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 font-bold">J</div><span className="text-lg font-semibold">JobPilot</span></div>
        <div>
          <h2 className="text-4xl font-semibold leading-tight tracking-tight">Your job search,<br />organised and AI-assisted.</h2>
          <ul className="mt-8 space-y-3 text-brand-100">
            {["Resume analysis & ATS checks", "Explainable job-match scores", "Cover letters from a local AI model", "Kanban tracker with reminders", "Assisted apply — you always review and submit"].map((t) => <li key={t} className="flex gap-3"><span aria-hidden>✓</span>{t}</li>)}
          </ul>
        </div>
        <p className="text-sm text-brand-200">100% free · open-source · your data stays on your computer.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-2xl font-semibold tracking-tight">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
            <button onClick={toggle} className="rounded-xl border border-c p-2 cursor-pointer" aria-label="Toggle theme">{dark ? "☀️" : "🌙"}</button>
          </div>
          <form onSubmit={submit} className="space-y-4" noValidate>
            {err && <Notice tone="red"><span role="alert">{err}</span></Notice>}
            {mode === "register" && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="First name">{(id) => <Input id={id} autoComplete="given-name" value={f.first_name} onChange={set("first_name")} />}</Field>
                <Field label="Last name">{(id) => <Input id={id} autoComplete="family-name" value={f.last_name} onChange={set("last_name")} />}</Field>
              </div>
            )}
            <Field label="Email">{(id) => <Input id={id} type="email" autoComplete="email" required value={f.email} onChange={set("email")} />}</Field>
            <Field label="Password" hint={mode === "register" ? "At least 8 characters; avoid common passwords." : undefined}>
              {(id) => <Input id={id} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={8} value={f.password} onChange={set("password")} />}
            </Field>
            <Button type="submit" className="w-full" loading={busy}>{mode === "login" ? "Log in" : "Create account"}</Button>
          </form>
          <p className="mt-5 text-center text-sm muted">
            {mode === "login" ? <>New here? <Link className="font-medium text-brand-600 hover:underline" to="/register">Create an account</Link></> : <>Already registered? <Link className="font-medium text-brand-600 hover:underline" to="/login">Log in</Link></>}
          </p>
        </div>
      </div>
    </div>
  );
}
