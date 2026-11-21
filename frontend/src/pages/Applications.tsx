import { useState } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { STATUS_LABEL, fmtDateTime, localInput, timeAgo, useLoad, useToast } from "../lib/app";
import type { AIResult, AppStatus, Application, Attempt, ResumeSummary } from "../lib/types";
import { Badge, Button, Card, Empty, EngineBadge, ErrorState, Field, Input, Loading, Modal, Notice, PageHeader, ScoreRing, Select, Textarea, cx, scoreTone } from "../components/ui";

const COLUMNS: AppStatus[] = ["wishlist", "preparing", "applied", "interviewing", "offer", "rejected", "withdrawn"];
const COL_TONE: Record<string, string> = { wishlist: "bg-slate-400", preparing: "bg-amber-500", applied: "bg-sky-500", interviewing: "bg-brand-500", offer: "bg-emerald-500", rejected: "bg-red-400", withdrawn: "bg-slate-300" };

interface ListResp { columns: AppStatus[]; results: Application[] }

// ------------------------------------------------------------------ kanban
export default function Applications() {
  const toast = useToast();
  const [sp] = useSearchParams();
  const openId = sp.get("open");
  const { data, error, loading, reload, setData } = useLoad(() => api<ListResp>("/applications/"), []);
  const [dragId, setDragId] = useState<number | null>(null);
  const [over, setOver] = useState<AppStatus | null>(null);
  const [add, setAdd] = useState(false);
  const [confirmApp, setConfirmApp] = useState<Application | null>(null);
  const [q, setQ] = useState("");

  const move = async (a: Application, status: AppStatus, extra: Record<string, any> = {}) => {
    if (a.status === status) return;
    if (status === "applied" && !extra.confirm_submitted) { setConfirmApp(a); return; }
    const prev = data;
    setData(data && { ...data, results: data.results.map((x) => (x.id === a.id ? { ...x, status } : x)) }); // optimistic
    try { await api(`/applications/${a.id}/move/`, { method: "POST", body: { status, ...extra } }); toast(`Moved to ${STATUS_LABEL[status]}`); reload(); }
    catch (e: any) { setData(prev); toast(e.message, "err"); }
  };

  if (openId && /^\d+$/.test(openId)) return <Navigate to={`/applications/${openId}`} replace />;
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorState message={error || "Could not load applications."} onRetry={reload} />;
  const filtered = data.results.filter((a) => !q || `${a.job_title} ${a.company}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <PageHeader title="Application tracker" subtitle="Drag cards between columns, or use the Move menu on each card. 'Applied' is only set after you confirm you really submitted on the employer's site."
        actions={<><Input aria-label="Filter applications" placeholder="Filter…" className="!w-40" value={q} onChange={(e) => setQ(e.target.value)} /><Button onClick={() => setAdd(true)}>+ Add application</Button></>} />
      {!data.results.length ? (
        <Empty icon="🗂️" title="Your board is empty" text="Add an application manually, or press 'Track' on any job." action={<div className="flex gap-2"><Button onClick={() => setAdd(true)}>Add application</Button><Link to="/jobs"><Button variant="secondary">Browse jobs</Button></Link></div>} />
      ) : (
        <div className="-mx-4 overflow-x-auto px-4 pb-4 sm:mx-0 sm:px-0">
          <div className="flex gap-4" style={{ minWidth: COLUMNS.length * 280 }}>
            {COLUMNS.map((col) => {
              const items = filtered.filter((a) => a.status === col);
              return (
                <section key={col} aria-label={`${STATUS_LABEL[col]} column`} onDragOver={(e) => { e.preventDefault(); setOver(col); }} onDragLeave={() => setOver(null)}
                  onDrop={(e) => { e.preventDefault(); setOver(null); const a = data.results.find((x) => x.id === dragId); if (a) move(a, col); setDragId(null); }}
                  className={cx("w-[270px] shrink-0 rounded-2xl p-3 transition", over === col ? "bg-brand-50 dark:bg-brand-600/10 ring-2 ring-brand-400" : "surface-2")}>
                  <h2 className="mb-3 flex items-center gap-2 px-1 text-sm font-semibold"><span className={`h-2.5 w-2.5 rounded-full ${COL_TONE[col]}`} />{STATUS_LABEL[col]}<span className="ml-auto text-xs font-normal muted">{items.length}</span></h2>
                  <div className="space-y-2.5 min-h-[3rem]">
                    {items.map((a) => (
                      <article key={a.id} draggable onDragStart={() => setDragId(a.id)} onDragEnd={() => { setDragId(null); setOver(null); }} className={cx("card cursor-grab p-3 text-sm active:cursor-grabbing", dragId === a.id && "opacity-40")}>
                        <div className="flex items-start gap-2">
                          <div className="min-w-0 flex-1"><Link to={`/applications/${a.id}`} className="block truncate font-medium hover:text-brand-600">{a.job_title}</Link><div className="truncate text-xs muted">{a.company}</div></div>
                          {a.match_score != null && <Badge tone={scoreTone(a.match_score)}>{a.match_score}</Badge>}
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] muted">
                          {a.submission_confirmed && <Badge tone="green">✓ Submitted</Badge>}
                          {a.has_cover_letter && <Badge>Letter</Badge>}
                          <span>{timeAgo(a.updated_at)}</span>
                        </div>
                        <label className="mt-2 block"><span className="sr-only">Move {a.job_title} to</span>
                          <select className="w-full rounded-lg border border-c bg-[var(--surface)] px-2 py-1 text-xs" value={a.status} onChange={(e) => move(a, e.target.value as AppStatus)}>
                            {COLUMNS.map((c) => <option key={c} value={c}>{c === a.status ? `Status: ${STATUS_LABEL[c]}` : `Move to ${STATUS_LABEL[c]}`}</option>)}
                          </select></label>
                      </article>
                    ))}
                    {!items.length && <p className="px-1 py-3 text-xs muted">Drop cards here</p>}
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      )}
      <AddModal open={add} onClose={() => setAdd(false)} onDone={() => { setAdd(false); reload(); }} />
      {confirmApp && <ConfirmSubmitted app={confirmApp} onClose={() => setConfirmApp(null)} onConfirm={async (via) => { const a = confirmApp; setConfirmApp(null); await move(a, "applied", { confirm_submitted: true, applied_via: via }); }} />}
    </div>
  );
}

export function ConfirmSubmitted({ app, onClose, onConfirm }: { app: Pick<Application, "job_title" | "company">; onClose: () => void; onConfirm: (via: string) => void }) {
  const [checked, setChecked] = useState(false);
  const [via, setVia] = useState("manual");
  return (
    <Modal open onClose={onClose} title="Did you actually submit this?">
      <p className="text-sm">JobPilot can't see the employer's site, so it never assumes an application was sent. Mark <strong>{app.job_title}</strong> at {app.company} as applied only if you submitted it yourself.</p>
      <div className="mt-4"><Field label="How did you apply?">{(id) => <Select id={id} value={via} onChange={(e) => setVia(e.target.value)}><option value="manual">On the employer's site (manual)</option><option value="assisted">With autofill help, submitted by me</option><option value="other">Email, referral or other</option></Select>}</Field></div>
      <label className="mt-4 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={checked} onChange={(e) => setChecked(e.target.checked)} /> Yes, I submitted this application and saw it go through.</label>
      <div className="mt-5 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Not yet</Button><Button disabled={!checked} onClick={() => onConfirm(via)}>Mark as applied</Button></div>
    </Modal>
  );
}

function AddModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ job_title: "", company: "", location: "", apply_url: "" });
  const [busy, setBusy] = useState(false);
  const [dup, setDup] = useState<{ message: string; id: number } | null>(null);
  const submit = async (force = false) => {
    setBusy(true);
    try { await api("/applications/", { method: "POST", body: { ...f, force } }); toast("Application added"); setF({ job_title: "", company: "", location: "", apply_url: "" }); setDup(null); onDone(); }
    catch (e: any) { if (e.code === "duplicate") setDup({ message: e.message, id: e.data.existing_id }); else toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Add an application">
      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-4">
        {dup && <Notice tone="amber">{dup.message} <Link className="underline" to={`/applications/${dup.id}`}>Open it</Link> or <button type="button" className="underline cursor-pointer" onClick={() => submit(true)}>add anyway</button>.</Notice>}
        <Field label="Job title">{(id) => <Input id={id} required value={f.job_title} onChange={(e) => setF({ ...f, job_title: e.target.value })} />}</Field>
        <Field label="Company">{(id) => <Input id={id} required value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} />}</Field>
        <Field label="Location">{(id) => <Input id={id} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} />}</Field>
        <Field label="Application link" hint="Where you will apply on the employer's site.">{(id) => <Input id={id} type="url" placeholder="https://…" value={f.apply_url} onChange={(e) => setF({ ...f, apply_url: e.target.value })} />}</Field>
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" loading={busy}>Add to wishlist</Button></div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ detail + assisted apply
interface Prepared { eligibility: { ready: boolean; checks: { label: string; passed: boolean; detail: string }[]; warnings: string[] }; attempt: Attempt; form_data: Record<string, string>; steps: string[] }

export function ApplicationDetail() {
  const { id } = useParams();
  const toast = useToast();
  const { data: app, error, loading, reload } = useLoad(() => api<Application>(`/applications/${id}/`), [id]);
  const resumes = useLoad(() => api<ResumeSummary[]>("/resumes/"), []);
  const [prep, setPrep] = useState<Prepared | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [letter, setLetter] = useState<string | null>(null);
  const [letterMeta, setLetterMeta] = useState<AIResult | null>(null);
  const [notes, setNotes] = useState<string | null>(null);
  const [ack, setAck] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [rem, setRem] = useState({ title: "", due_at: localInput(48) });

  if (loading && !app) return <Loading />;
  if (error || !app) return <ErrorState message={error || "Application not found."} onRetry={reload} />;
  const call = async (key: string, fn: () => Promise<any>, ok?: string) => { setBusy(key); try { const r = await fn(); if (ok) toast(ok); await reload(); return r; } catch (e: any) { toast(e.message, "err"); } finally { setBusy(null); } };
  const closed = ["applied", "interviewing", "offer", "rejected", "withdrawn"].includes(app.status);
  const activeAttempt = app.attempts?.find((a) => ["prepared", "autofilled"].includes(a.state));
  const letterText = letter ?? app.cover_letter ?? "";
  const notesText = notes ?? app.notes ?? "";

  const prepare = async () => { const r = await call("prep", () => api<Prepared>(`/applications/${app.id}/prepare/`, { method: "POST" })); if (r) { setPrep(r); setAck(false); } };
  const generate = async () => {
    const r = await call("gen", () => api<AIResult>("/writing/generate/", { method: "POST", body: { application_id: app.id, kind: "cover_letter", save: true } }), "Cover letter drafted and saved");
    if (r) { setLetter(r.text); setLetterMeta(r); }
  };

  return (
    <div className="space-y-6">
      <Link to="/applications" className="text-sm muted hover:underline">← Back to tracker</Link>
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex gap-4">
            <ScoreRing score={app.match_score} label="Match" size={64} />
            <div><h1 className="text-2xl font-semibold tracking-tight">{app.job_title}</h1><p className="muted">{app.company}{app.location && ` · ${app.location}`}</p>
              <div className="mt-2 flex flex-wrap gap-2"><Badge tone="brand">{STATUS_LABEL[app.status]}</Badge>{app.submission_confirmed && <Badge tone="green">✓ Submission confirmed by you</Badge>}{app.job_id && <Link to={`/jobs/${app.job_id}`} className="text-xs text-brand-600 underline">View job & match</Link>}</div></div>
          </div>
          <div className="flex flex-wrap gap-2">
            {app.apply_url ? <a href={app.apply_url} target="_blank" rel="noreferrer noopener"><Button variant="secondary">Open application page ↗</Button></a> : <Button variant="secondary" disabled>No link added</Button>}
            <Select aria-label="Change status" className="!w-auto" value={app.status} onChange={(e) => { const s = e.target.value as AppStatus; if (s === "applied") setConfirm(true); else call("st", () => api(`/applications/${app.id}/`, { method: "PATCH", body: { status: s } }), "Status updated"); }}>
              {COLUMNS.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</Select>
            <Button variant="ghost" onClick={() => { if (confirm_("Delete this application and its history?")) call("del", async () => { await api(`/applications/${app.id}/`, { method: "DELETE" }); location.href = "/applications"; }); }}>Delete</Button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h2 className="font-semibold">Assisted apply</h2>
            <p className="mb-4 text-sm muted">Prepare your data, review it, let the browser extension fill the form, then check everything and submit on the employer's site yourself. JobPilot never submits for you.</p>
            {closed ? <Notice tone="green">This application is already <strong>{app.status}</strong>.</Notice> : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field label="Resume to use">{(i) => <Select id={i} value={app.resume_id ?? ""} onChange={(e) => call("resume", () => api(`/applications/${app.id}/`, { method: "PATCH", body: { resume_id: e.target.value ? Number(e.target.value) : null } }), "Resume updated — please review again")}>
                    <option value="">None selected</option>{resumes.data?.map((r) => <option key={r.id} value={r.id}>{r.title}{r.is_primary ? " (primary)" : ""}</option>)}</Select>}</Field>
                  <Field label="Application link">{(i) => <Input id={i} type="url" defaultValue={app.apply_url} placeholder="https://…" onBlur={(e) => e.target.value !== app.apply_url && call("url", () => api(`/applications/${app.id}/`, { method: "PATCH", body: { apply_url: e.target.value } }), "Link saved")} />}</Field>
                </div>
                {!prep && !activeAttempt && <Button loading={busy === "prep"} onClick={prepare}>1 · Prepare & check eligibility</Button>}
                {!prep && activeAttempt && <Button loading={busy === "prep"} onClick={prepare}>Resume preparation (attempt {activeAttempt.attempt_no})</Button>}
                {prep && (
                  <div className="space-y-4 fade-up">
                    <div><h3 className="mb-2 text-sm font-medium">Eligibility & checklist</h3>
                      {prep.eligibility.warnings.length ? prep.eligibility.warnings.map((w) => <div key={w} className="mb-2"><Notice>{w}</Notice></div>) : <Notice tone="green">No problems found.</Notice>}
                      {<ul className="mt-2 space-y-1 text-sm">{prep.eligibility.checks.map((c, i) => <li key={i}><span className={c.passed ? "text-emerald-600" : "text-amber-600"}>{c.passed ? "✓" : "!"}</span> {c.label}{c.detail && <span className="text-xs muted"> — {c.detail}</span>}</li>)}</ul>}</div>
                    <div><h3 className="mb-2 text-sm font-medium">Data the extension will type into the form</h3>
                      <dl className="grid gap-x-4 gap-y-1 rounded-xl surface-2 p-3 text-sm sm:grid-cols-2">{Object.entries(prep.form_data).filter(([k]) => k !== "cover_letter").map(([k, v]) => <div key={k} className="flex gap-2"><dt className="w-32 shrink-0 muted">{k.replace(/_/g, " ")}</dt><dd className="min-w-0 truncate">{v}</dd></div>)}</dl>
                      {!prep.form_data.cover_letter && <p className="mt-1 text-xs muted">No cover letter written yet — generate one below if the form asks for it.</p>}</div>
                    <ol className="list-decimal space-y-1 pl-5 text-sm muted">{prep.steps.map((s) => <li key={s}>{s}</li>)}</ol>
                    {!app.review_confirmed_at ? (
                      <div className="space-y-3">
                        {prep.eligibility.warnings.length > 0 && <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I understand these warnings and still want to apply.</label>}
                        <Button loading={busy === "review"} disabled={prep.eligibility.warnings.length > 0 && !ack} onClick={() => call("review", () => api(`/applications/${app.id}/review/`, { method: "POST", body: { acknowledge_warnings: ack } }), "Reviewed — the extension can now fill the form")}>2 · I reviewed this</Button>
                      </div>
                    ) : <Notice tone="green">Reviewed {fmtDateTime(app.review_confirmed_at)}. Open the employer's page and click <strong>Fill</strong> in the JobPilot extension.</Notice>}
                  </div>
                )}
                {app.review_confirmed_at && !prep && <Notice tone="green">Reviewed {fmtDateTime(app.review_confirmed_at)}. Use the extension on the employer's page, then come back here.</Notice>}
                {activeAttempt && (
                  <div className="flex flex-wrap gap-2 border-t border-c pt-4">
                    <Button loading={busy === "submitted"} onClick={() => setConfirm(true)}>3 · I submitted it</Button>
                    <Button variant="secondary" loading={busy === "cancel"} onClick={() => call("cancel", () => api(`/applications/${app.id}/attempts/${activeAttempt.id}/cancel/`, { method: "POST" }), "Attempt cancelled")}>Cancel attempt</Button>
                  </div>
                )}
              </div>
            )}
            {!!app.attempts?.length && (
              <div className="mt-5 border-t border-c pt-4"><h3 className="mb-2 text-sm font-medium">Attempts</h3>
                <ul className="space-y-2">{app.attempts.map((t) => (
                  <li key={t.id} className="rounded-xl surface-2 p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span>Attempt {t.attempt_no} · <Badge tone={t.state === "failed" ? "red" : t.state === "completed" ? "green" : t.state === "cancelled" ? "gray" : "amber"}>{t.state}</Badge>{t.host && <span className="ml-2 text-xs muted">{t.host}</span>}</span>
                    {["cancelled", "failed"].includes(t.state) && t.id === app.attempts![0].id && !closed && <Button size="sm" variant="secondary" loading={busy === "retry"} onClick={() => call("retry", () => api(`/applications/${app.id}/attempts/${t.id}/retry/`, { method: "POST" }), "New attempt started — review again")}>Retry</Button>}</div>
                    {t.error && <p className="mt-1 text-xs text-red-600">{t.error}</p>}
                    {!!t.fields_filled.length && <p className="mt-1 text-xs muted">Filled: {t.fields_filled.join(", ")}</p>}
                    {!!t.fields_skipped.length && <p className="text-xs muted">Skipped (no matching field): {t.fields_skipped.join(", ")}</p>}</li>))}</ul></div>
            )}
          </Card>

          <Card>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Cover letter</h2><div className="flex items-center gap-2">{letterMeta && <EngineBadge engine={letterMeta.engine} model={letterMeta.model} />}<Button size="sm" variant="secondary" loading={busy === "gen"} onClick={generate}>{app.has_cover_letter ? "Regenerate" : "Generate draft"}</Button></div></div>
            <Textarea aria-label="Cover letter" rows={10} placeholder="Generate a draft from your resume and this job, or write your own." value={letterText} onChange={(e) => setLetter(e.target.value)} />
            <div className="mt-2 flex gap-2"><Button size="sm" loading={busy === "saveL"} disabled={letter === null} onClick={() => call("saveL", async () => { await api(`/applications/${app.id}/`, { method: "PATCH", body: { cover_letter: letterText } }); setLetter(null); }, "Cover letter saved")}>Save</Button>
              <Button size="sm" variant="secondary" disabled={!letterText} onClick={async () => { await navigator.clipboard.writeText(letterText); toast("Copied"); }}>Copy</Button></div>
            <p className="mt-2 text-xs muted">Editing the letter after review clears your review, so you re-check what gets filled in.</p>
          </Card>

          <Card>
            <h2 className="mb-2 font-semibold">Notes</h2>
            <Textarea aria-label="Notes" rows={4} placeholder="Recruiter name, salary discussed, questions to ask…" value={notesText} onChange={(e) => setNotes(e.target.value)} />
            <Button className="mt-2" size="sm" disabled={notes === null} loading={busy === "notes"} onClick={() => call("notes", async () => { await api(`/applications/${app.id}/`, { method: "PATCH", body: { notes: notesText } }); setNotes(null); }, "Notes saved")}>Save notes</Button>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h2 className="mb-3 font-semibold">Reminders</h2>
            <ul className="mb-3 space-y-2">{app.reminders?.map((r) => (
              <li key={r.id} className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label={`Mark "${r.title}" done`} checked={r.done} onChange={(e) => call("r" + r.id, () => api(`/reminders/${r.id}/`, { method: "PATCH", body: { done: e.target.checked } }))} />
                <span className={cx("flex-1", r.done && "line-through muted")}>{r.title}<span className="block text-xs muted">{fmtDateTime(r.due_at)}</span></span></li>))}
              {!app.reminders?.length && <li className="text-sm muted">No reminders. A follow-up is scheduled automatically when you mark this as applied.</li>}</ul>
            <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); call("addrem", async () => { await api("/reminders/", { method: "POST", body: { title: rem.title, due_at: new Date(rem.due_at).toISOString(), application_id: app.id } }); setRem({ title: "", due_at: localInput(48) }); }, "Reminder added"); }}>
              <Input aria-label="Reminder title" required placeholder="e.g. Follow up with recruiter" value={rem.title} onChange={(e) => setRem({ ...rem, title: e.target.value })} />
              <Input aria-label="Due date and time" type="datetime-local" required value={rem.due_at} onChange={(e) => setRem({ ...rem, due_at: e.target.value })} />
              <Button type="submit" size="sm" variant="secondary" loading={busy === "addrem"}>Add reminder</Button></form>
          </Card>
          <Card>
            <h2 className="mb-3 font-semibold">History & error log</h2>
            <ol className="space-y-3">{app.activities?.map((a) => (
              <li key={a.id} className="text-sm"><span className={a.kind === "error" ? "text-red-600" : ""}>{a.message}</span><div className="text-xs muted">{fmtDateTime(a.created_at)}</div></li>))}</ol>
          </Card>
        </div>
      </div>
      {confirm && <ConfirmSubmitted app={app} onClose={() => setConfirm(false)} onConfirm={(via) => { setConfirm(false); call("submitted", () => api(`/applications/${app.id}/confirm-submitted/`, { method: "POST", body: { confirm_submitted: true, applied_via: via } }), "Marked as applied — follow-up reminder scheduled"); }} />}
    </div>
  );
}
const confirm_ = (m: string) => window.confirm(m);
