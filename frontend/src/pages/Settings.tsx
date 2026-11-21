import { useEffect, useState } from "react";
import { api, setToken } from "../lib/api";
import { useAuth, useLoad, useToast } from "../lib/app";
import type { AIStatus, Profile } from "../lib/types";
import { Badge, Bar, Button, Card, ErrorState, Field, Input, Loading, Modal, Notice, PageHeader, Select, TagInput, Textarea } from "../components/ui";

export default function Settings() {
  const { user, refresh, logout } = useAuth();
  const toast = useToast();
  const [p, setP] = useState<Profile | null>(null);
  const [names, setNames] = useState({ first_name: "", last_name: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const ai = useLoad(() => api<AIStatus>("/ai/status/"), []);
  const usage = useLoad(() => api<{ usage: Record<string, { used: number; limit: number }> }>("/usage/"), []);
  const key = useLoad(() => api<{ autofill_key: string }>("/profile/autofill-key/"), []);
  const [showKey, setShowKey] = useState(false);
  const [pw, setPw] = useState({ old_password: "", new_password: "" });
  const [del, setDel] = useState(false);
  const [delPw, setDelPw] = useState("");

  useEffect(() => { if (user) { setP(structuredClone(user.profile)); setNames({ first_name: user.first_name, last_name: user.last_name }); } }, [user]);
  if (!p) return <Loading />;
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v });
  const run = async (k: string, fn: () => Promise<any>, ok: string) => { setBusy(k); try { await fn(); toast(ok); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(null); } };

  const save = () => run("save", async () => {
    await api("/me/", { method: "PATCH", body: names });
    await api("/profile/", { method: "PATCH", body: { ...p, years_experience: Number(p.years_experience) || 0, notice_period_days: p.notice_period_days === null || (p.notice_period_days as any) === "" ? null : Number(p.notice_period_days) } });
    await refresh();
  }, "Profile saved");

  return (
    <div className="space-y-6">
      <PageHeader title="Profile & settings" subtitle="Your profile powers matching, cover letters and form autofill. It is stored only in your local database." actions={<Button loading={busy === "save"} onClick={save}>Save profile</Button>} />

      <Card>
        <h2 className="mb-4 font-semibold">About you</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="First name">{(i) => <Input id={i} value={names.first_name} onChange={(e) => setNames({ ...names, first_name: e.target.value })} />}</Field>
          <Field label="Last name">{(i) => <Input id={i} value={names.last_name} onChange={(e) => setNames({ ...names, last_name: e.target.value })} />}</Field>
          <Field label="Headline" hint="e.g. Python developer with 2 years of experience">{(i) => <Input id={i} maxLength={160} value={p.headline} onChange={(e) => set("headline", e.target.value)} />}</Field>
          <Field label="Phone">{(i) => <Input id={i} type="tel" value={p.phone} onChange={(e) => set("phone", e.target.value)} />}</Field>
          <Field label="Current location">{(i) => <Input id={i} placeholder="Chennai, India" value={p.location} onChange={(e) => set("location", e.target.value)} />}</Field>
          <Field label="Years of experience">{(i) => <Input id={i} type="number" min={0} max={60} step={0.5} value={p.years_experience} onChange={(e) => set("years_experience", e.target.value)} />}</Field>
          <div className="sm:col-span-2"><Field label="Summary">{(i) => <Textarea id={i} rows={3} value={p.summary} onChange={(e) => set("summary", e.target.value)} />}</Field></div>
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 font-semibold">Job preferences</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><Field label="Skills" hint="Press Enter or comma after each. Used for matching.">{(i) => <TagInput id={i} value={p.skills} onChange={(v) => set("skills", v)} placeholder="Python, Django, React…" />}</Field></div>
          <Field label="Target roles">{(i) => <TagInput id={i} value={p.desired_roles} onChange={(v) => set("desired_roles", v)} placeholder="Backend Developer…" />}</Field>
          <Field label="Preferred locations">{(i) => <TagInput id={i} value={p.desired_locations} onChange={(v) => set("desired_locations", v)} placeholder="Chennai, Remote…" />}</Field>
          <Field label="Work mode">{(i) => <Select id={i} value={p.remote_preference} onChange={(e) => set("remote_preference", e.target.value as Profile["remote_preference"])}><option value="any">Any</option><option value="remote">Remote only</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></Select>}</Field>
          <Field label="Notice period (days)">{(i) => <Input id={i} type="number" min={0} value={p.notice_period_days ?? ""} onChange={(e) => set("notice_period_days", e.target.value === "" ? null : Number(e.target.value))} />}</Field>
          {(["linkedin", "github", "portfolio"] as const).map((k) => (
            <Field key={k} label={k[0].toUpperCase() + k.slice(1) + " URL"}>{(i) => <Input id={i} type="url" placeholder="https://…" value={p.links[k] || ""} onChange={(e) => set("links", { ...p.links, [k]: e.target.value })} />}</Field>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Local AI (Ollama)</h2><Button size="sm" variant="ghost" onClick={() => api<AIStatus>("/ai/status/", { query: { refresh: 1 } }).then((d) => { ai.setData(d); toast(d.ready ? "Local AI is ready" : "Local AI is not ready yet", d.ready ? "ok" : "err"); })}>Re-check</Button></div>
          {ai.loading && !ai.data ? <Loading /> : ai.error ? <ErrorState message={ai.error} onRetry={ai.reload} /> : ai.data && (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2"><Badge tone={ai.data.enabled ? "green" : "gray"}>{ai.data.enabled ? "Enabled" : "Disabled"}</Badge><Badge tone={ai.data.reachable ? "green" : "red"}>{ai.data.reachable ? "Ollama running" : "Ollama not reachable"}</Badge><Badge tone={ai.data.model_installed ? "green" : "amber"}>{ai.data.model_installed ? `${ai.data.model} installed` : `${ai.data.model} missing`}</Badge></div>
              {ai.data.ready ? <Notice tone="green">AI features use <strong>{ai.data.model}</strong> on this computer. Nothing is sent to the cloud.</Notice> : (
                <Notice tone="blue"><p className="font-medium">Everything works without AI, using built-in rules. To enable AI-written text for free:</p>
                  <ol className="mt-2 list-decimal space-y-1 pl-5"><li>Install Ollama from <a className="underline" href="https://ollama.com/download" target="_blank" rel="noreferrer">ollama.com/download</a></li><li>Run <code className="rounded bg-black/10 px-1">ollama pull {ai.data.model}</code></li><li>Press <strong>Re-check</strong> above.</li></ol>
                  <p className="mt-2 text-xs">Low on RAM (under 6 GB)? Use <code>llama3.2:1b</code> or <code>qwen2.5:1.5b</code> and set OLLAMA_MODEL in backend/.env.</p></Notice>)}
              {!!ai.data.installed_models.length && <p className="text-xs muted">Installed: {ai.data.installed_models.join(", ")}</p>}
            </div>)}
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">Today's free usage</h2>
          {usage.loading && !usage.data ? <Loading /> : usage.error ? <ErrorState message={usage.error} onRetry={usage.reload} /> : (
            <div className="space-y-3">{Object.entries(usage.data?.usage || {}).map(([k, v]) => (<div key={k} className="text-xs"><div className="mb-1 flex justify-between"><span className="muted">{k.replace(/_/g, " ")}</span><span>{v.used}/{v.limit}</span></div><Bar value={v.used} max={v.limit} /></div>))}</div>)}
          <p className="mt-3 text-xs muted">Subscriptions exist in the code as a disabled architecture. They stay off — everything here is free.</p>
        </Card>
      </div>

      <Card>
        <h2 className="mb-1 font-semibold">Browser autofill key</h2>
        <p className="mb-3 text-sm muted">Paste this key into the JobPilot browser extension. It can only read your autofill data and report which fields were filled — it can't edit your account, and it can never submit a form. Regenerate it if you think it leaked.</p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input readOnly aria-label="Autofill key" className="font-mono" type={showKey ? "text" : "password"} value={key.data?.autofill_key ?? "…"} />
          <Button variant="secondary" onClick={() => setShowKey(!showKey)}>{showKey ? "Hide" : "Show"}</Button>
          <Button variant="secondary" onClick={async () => { try { await navigator.clipboard.writeText(key.data?.autofill_key || ""); toast("Key copied"); } catch { toast("Your browser blocked copying. Select the key and press Ctrl+C.", "err"); } }}>Copy</Button>
          <Button variant="secondary" loading={busy === "key"} onClick={() => { if (confirm("Regenerate the key? The extension will stop working until you paste the new one.")) run("key", async () => key.setData(await api("/profile/autofill-key/", { method: "POST" })), "New key generated"); }}>Regenerate</Button>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold">Change password</h2>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); run("pw", async () => { const r = await api<{ token: string }>("/auth/password/", { method: "POST", body: pw }); setToken(r.token); setPw({ old_password: "", new_password: "" }); }, "Password changed"); }}>
            <Field label="Current password">{(i) => <Input id={i} type="password" autoComplete="current-password" required value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} />}</Field>
            <Field label="New password" hint="At least 8 characters.">{(i) => <Input id={i} type="password" autoComplete="new-password" required minLength={8} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />}</Field>
            <Button type="submit" variant="secondary" loading={busy === "pw"}>Update password</Button>
          </form>
        </Card>
        <Card>
          <h2 className="mb-1 font-semibold">Delete my account</h2>
          <p className="mb-3 text-sm muted">Permanently removes your profile, resumes (including uploaded files), applications, chats and every other record. This cannot be undone.</p>
          <Button variant="danger" onClick={() => setDel(true)}>Delete account…</Button>
        </Card>
      </div>

      <Modal open={del} onClose={() => setDel(false)} title="Delete account permanently?">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); run("del", async () => { await api("/me/", { method: "DELETE", body: { password: delPw } }); await logout(); }, "Account deleted"); }}>
          <Field label="Enter your password to confirm">{(i) => <Input id={i} type="password" required autoComplete="current-password" value={delPw} onChange={(e) => setDelPw(e.target.value)} />}</Field>
          <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={() => setDel(false)}>Cancel</Button><Button type="submit" variant="danger" loading={busy === "del"}>Delete everything</Button></div>
        </form>
      </Modal>
    </div>
  );
}
