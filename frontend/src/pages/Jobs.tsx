import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { fmtDate, fmtDateTime, timeAgo, useLoad, useToast } from "../lib/app";
import type { AIResult, Job, JobList, Match } from "../lib/types";
import { Badge, Bar, Button, Card, Empty, EngineBadge, ErrorState, Field, Input, Loading, Modal, Notice, PageHeader, Pager, ScoreRing, Select, Skill, Textarea, scoreTone } from "../components/ui";

interface SourceInfo { slug: string; name: string; kind: string; attribution: string; terms_url: string; refreshable: boolean; needs_board_token: boolean; last_fetched_at: string | null; next_allowed_at: string | null; job_count: number; enabled: boolean }
interface SourcesResp { sources: SourceInfo[]; boards: { id: number; source: string; token: string; last_fetched_at: string | null; last_error: string }[] }

// ------------------------------------------------------------------ job card
export function JobCard({ job, onToggleSave, onTrack }: { job: Job; onToggleSave: (j: Job) => void; onTrack?: (j: Job) => void }) {
  return (
    <Card className="fade-up transition hover:shadow-md">
      <div className="flex gap-4">
        <ScoreRing score={job.match_score} label="Match score" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <Link to={`/jobs/${job.id}`} className="block truncate text-base font-semibold hover:text-brand-600">{job.title}</Link>
              <div className="text-sm muted">{job.company} · {job.location || "Location not listed"}{job.is_remote && " · Remote"}</div>
            </div>
            <div className="flex gap-1.5">
              <Button variant="ghost" size="sm" onClick={() => onToggleSave(job)} aria-pressed={job.is_saved} aria-label={job.is_saved ? "Remove from saved" : "Save job"}>{job.is_saved ? "★ Saved" : "☆ Save"}</Button>
              {onTrack && !job.application_status && <Button variant="secondary" size="sm" onClick={() => onTrack(job)}>Track</Button>}
            </div>
          </div>
          <p className="mt-2 line-clamp-2 text-sm muted">{job.snippet}</p>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {job.match_verdict && <Badge tone={scoreTone(job.match_score)}>{job.match_verdict}</Badge>}
            {job.application_status && <Badge tone="brand">In tracker: {job.application_status}</Badge>}
            {job.imported_by_me && <Badge tone="blue">Imported by you</Badge>}
            {job.source.kind === "demo" && <Badge tone="amber" title="Fictional listing for trying the app">Demo data</Badge>}
            {job.skills.slice(0, 5).map((s) => <Skill key={s}>{s}</Skill>)}
          </div>
          <div className="mt-2 text-xs muted">Source: {job.source.name} · checked {timeAgo(job.last_checked_at)}{job.posted_at ? ` · posted ${fmtDate(job.posted_at)}` : ""}</div>
        </div>
      </div>
    </Card>
  );
}

function useJobActions(reload: () => void) {
  const toast = useToast();
  const nav = useNavigate();
  const toggleSave = async (j: Job) => {
    try {
      if (j.is_saved) { await api(`/saved-jobs/${j.id}/`, { method: "DELETE" }); toast("Removed from saved jobs"); }
      else { await api("/saved-jobs/", { method: "POST", body: { job_id: j.id } }); toast("Job saved"); }
      reload();
    } catch (e: any) { toast(e.message, "err"); }
  };
  const track = async (j: Job) => {
    try { const a = await api<{ id: number }>("/applications/", { method: "POST", body: { job_id: j.id } }); toast("Added to your tracker"); nav(`/applications/${a.id}`); }
    catch (e: any) { if (e.status === 409 && e.data?.existing_id) { toast(e.message, "err"); nav(`/applications/${e.data.existing_id}`); } else toast(e.message, "err"); }
  };
  return { toggleSave, track };
}

// ------------------------------------------------------------------ search page
export default function Jobs() {
  const [sp, setSp] = useSearchParams();
  const toast = useToast();
  const [form, setForm] = useState({ q: sp.get("q") || "", skills: sp.get("skills") || "", location: sp.get("location") || "", experience: sp.get("experience") || "", remote: sp.get("remote") || "", sort: sp.get("sort") || "match" });
  const [showFilters, setShowFilters] = useState(false);
  const [modal, setModal] = useState<"import" | "sources" | null>(null);
  const page = Number(sp.get("page") || 1);
  const query = Object.fromEntries(sp.entries());
  const { data, error, loading, reload } = useLoad(() => api<JobList>("/jobs/", { query: { sort: "match", ...query } }), [sp.toString()]);
  const { toggleSave, track } = useJobActions(reload);

  const apply = (e?: React.FormEvent) => {
    e?.preventDefault();
    const next: Record<string, string> = {};
    Object.entries(form).forEach(([k, v]) => v && (next[k] = v));
    setSp(next);
  };
  const clear = () => { setForm({ q: "", skills: "", location: "", experience: "", remote: "", sort: "match" }); setSp({}); };
  const goPage = (p: number) => { const n = new URLSearchParams(sp); n.set("page", String(p)); setSp(n); window.scrollTo({ top: 0 }); };
  const hasFilters = ["q", "skills", "location", "experience", "remote"].some((k) => sp.get(k));

  return (
    <div>
      <PageHeader title="Find jobs" subtitle="Listings come from free public job feeds, jobs you import yourself, and clearly labelled demo data. Every card shows its source and when it was last checked."
        actions={<><Button variant="secondary" onClick={() => setModal("sources")}>Job sources</Button><Button onClick={() => setModal("import")}>+ Import a job</Button></>} />

      <Card className="mb-5">
        <form onSubmit={apply} className="space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input aria-label="Search by role, company or keyword" placeholder="Role, company or keyword — e.g. Django developer" value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} />
            <Button type="submit">Search</Button>
            <Button type="button" variant="secondary" onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}>Filters{hasFilters ? " •" : ""}</Button>
          </div>
          {showFilters && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 fade-up">
              <Field label="Skills" hint="Comma separated">{(id) => <Input id={id} placeholder="python, react" value={form.skills} onChange={(e) => setForm({ ...form, skills: e.target.value })} />}</Field>
              <Field label="Location">{(id) => <Input id={id} placeholder="Bengaluru" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />}</Field>
              <Field label="My experience (years)">{(id) => <Input id={id} type="number" min={0} max={40} value={form.experience} onChange={(e) => setForm({ ...form, experience: e.target.value })} />}</Field>
              <Field label="Work mode">{(id) => <Select id={id} value={form.remote} onChange={(e) => setForm({ ...form, remote: e.target.value })}><option value="">Any</option><option value="true">Remote only</option><option value="false">Not remote</option></Select>}</Field>
              <Field label="Sort by">{(id) => <Select id={id} value={form.sort} onChange={(e) => setForm({ ...form, sort: e.target.value })}><option value="match">Best match</option><option value="recent">Most recent</option></Select>}</Field>
              <div className="sm:col-span-2 lg:col-span-5 flex gap-2"><Button type="submit" size="sm">Apply filters</Button><Button type="button" variant="ghost" size="sm" onClick={clear}>Clear all</Button></div>
            </div>
          )}
        </form>
      </Card>

      {data && !data.has_resume && <div className="mb-4"><Notice tone="blue">Match scores need a resume. <Link className="underline font-medium" to="/resumes">Upload or build one</Link> to see how well you fit each job.</Notice></div>}
      {loading && !data ? <Loading text="Searching jobs…" /> : error ? <ErrorState message={error} onRetry={reload} /> : !data?.results.length ? (
        <Empty icon="🔎" title={hasFilters ? "No jobs match these filters" : "No jobs loaded yet"}
          text={hasFilters ? "Try fewer filters or a broader keyword." : "Load demo listings to explore the app, fetch jobs from a free public source, or import a job you found yourself."}
          action={<div className="flex flex-wrap gap-2 justify-center">{hasFilters && <Button variant="secondary" onClick={clear}>Clear filters</Button>}<Button onClick={() => setModal("sources")}>Open job sources</Button><Button variant="secondary" onClick={() => setModal("import")}>Import a job</Button></div>} />
      ) : (
        <>
          <p className="mb-3 text-sm muted" aria-live="polite">{data.count} job{data.count === 1 ? "" : "s"} found</p>
          <div className="space-y-3">{data.results.map((j) => <JobCard key={j.id} job={j} onToggleSave={toggleSave} onTrack={track} />)}</div>
          <Pager page={data.page || page} pages={data.pages} onPage={goPage} />
        </>
      )}
      <ImportModal open={modal === "import"} onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); toast("Job imported"); }} />
      <SourcesModal open={modal === "sources"} onClose={() => setModal(null)} onChanged={reload} />
    </div>
  );
}

// ------------------------------------------------------------------ import modal
function ImportModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ url: "", text: "", title: "", company: "", location: "" });
  const [err, setErr] = useState(""); const [needsPaste, setNeedsPaste] = useState(false); const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await api("/jobs/import/", { method: "POST", body: f }); setF({ url: "", text: "", title: "", company: "", location: "" }); setNeedsPaste(false); onDone(); }
    catch (e: any) { setErr(e.message); if (e.data?.needs_paste) setNeedsPaste(true); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Import a job" wide>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm muted">Paste a link to a public job page, or paste the description text. Pages that block automated access (most big job boards) can't be read — paste the text instead. JobPilot never bypasses logins, CAPTCHAs or site protections.</p>
        {err && <Notice tone="red"><span role="alert">{err}</span></Notice>}
        <Field label="Job link (optional)">{(id) => <Input id={id} type="url" placeholder="https://company.com/careers/backend-engineer" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} />}</Field>
        <Field label="Job description text" hint={needsPaste ? "Paste the description here and fill in the title and company." : "Used when no link is given, or when the link can't be read."}>{(id) => <Textarea id={id} rows={7} value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} />}</Field>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Title">{(id) => <Input id={id} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />}</Field>
          <Field label="Company">{(id) => <Input id={id} value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} />}</Field>
          <Field label="Location">{(id) => <Input id={id} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} />}</Field>
        </div>
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" loading={busy}>Import job</Button></div>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ sources modal
function SourcesModal({ open, onClose, onChanged }: { open: boolean; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const { data, error, loading, reload } = useLoad(() => (open ? api<SourcesResp>("/jobs/sources/") : Promise.resolve(null as unknown as SourcesResp)), [open]);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState<Record<string, string>>({});
  const [token, setToken] = useState<Record<string, string>>({});
  const refresh = async (s: SourceInfo, tok?: string) => {
    setBusy(s.slug + (tok || ""));
    try {
      const r = await api<any>(`/jobs/sources/${s.slug}/refresh/`, { method: "POST", body: { query: query[s.slug] || "", token: tok ?? token[s.slug] ?? "" } });
      toast(r.skipped ? r.message : `Fetched ${r.fetched} jobs (${r.created} new, ${r.updated} updated).`, r.skipped ? "ok" : "ok");
      reload(); onChanged();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(null); }
  };
  const loadDemo = async () => {
    setBusy("demo");
    try { const r = await api<{ created: number; updated: number }>("/jobs/demo/", { method: "POST" }); toast(`Demo jobs ready (${r.created} added, ${r.updated} refreshed). They are fictional.`); reload(); onChanged(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(null); }
  };
  const removeBoard = async (id: number) => { try { await api(`/jobs/boards/${id}/`, { method: "DELETE" }); reload(); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <Modal open={open} onClose={onClose} title="Job sources" wide>
      <p className="mb-4 text-sm muted">Only official public APIs and feeds are used, each limited to polite refresh intervals. Respect each provider's terms. Nothing is fetched until you press Refresh.</p>
      {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={reload} /> : (
        <div className="space-y-3">
          {data?.sources.map((s) => (
            <div key={s.slug} className="rounded-xl border border-c p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div><div className="font-medium">{s.name} <Badge tone={s.kind === "demo" ? "amber" : "gray"}>{s.kind}</Badge></div>
                  <div className="text-xs muted">{s.job_count} jobs · {s.last_fetched_at ? `last fetched ${fmtDateTime(s.last_fetched_at)}` : "never fetched"}{s.next_allowed_at ? ` · next refresh after ${fmtDateTime(s.next_allowed_at)}` : ""}</div></div>
                {s.terms_url && <a className="text-xs text-brand-600 underline" href={s.terms_url} target="_blank" rel="noreferrer">Terms</a>}
              </div>
              {s.attribution && <p className="mt-1 text-xs muted">{s.attribution}</p>}
              {s.refreshable && !s.needs_board_token && (
                <div className="mt-3 flex flex-col gap-2 sm:flex-row"><Input aria-label={`Keyword for ${s.name}`} placeholder="Optional keyword (e.g. python)" value={query[s.slug] || ""} onChange={(e) => setQuery({ ...query, [s.slug]: e.target.value })} />
                  <Button variant="secondary" loading={busy === s.slug} disabled={!s.enabled} onClick={() => refresh(s)}>Refresh</Button></div>
              )}
              {s.needs_board_token && (
                <div className="mt-3 space-y-2">
                  <div className="flex flex-col gap-2 sm:flex-row"><Input aria-label={`Company board name for ${s.name}`} placeholder="Company board name, e.g. stripe" value={token[s.slug] || ""} onChange={(e) => setToken({ ...token, [s.slug]: e.target.value })} />
                    <Button variant="secondary" loading={busy === s.slug} disabled={!s.enabled} onClick={() => refresh(s)}>Fetch board</Button></div>
                  {data.boards.filter((b) => b.source === s.slug).map((b) => (
                    <div key={b.id} className="flex items-center justify-between rounded-lg surface-2 px-3 py-2 text-sm"><span>{b.token}{b.last_error && <span className="ml-2 text-xs text-red-600">{b.last_error}</span>}</span>
                      <span className="flex gap-1"><Button size="sm" variant="ghost" loading={busy === s.slug + b.token} onClick={() => refresh(s, b.token)}>Refresh</Button><Button size="sm" variant="ghost" onClick={() => removeBoard(b.id)}>Remove</Button></span></div>
                  ))}
                </div>
              )}
              {s.kind === "demo" && <Button className="mt-3" size="sm" variant="secondary" loading={busy === "demo"} onClick={loadDemo}>Load fictional demo jobs</Button>}
              {!s.enabled && s.refreshable && <p className="mt-2 text-xs text-amber-600">External fetching is disabled in server settings (JOB_SOURCES_ENABLED=false).</p>}
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ detail page
export function JobDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { data: job, error, loading, reload } = useLoad(() => api<Job>(`/jobs/${id}/`), [id]);
  const { toggleSave, track } = useJobActions(reload);
  const [gen, setGen] = useState<{ kind: string; res?: AIResult; busy?: boolean } | null>(null);
  const [tone, setTone] = useState("professional");

  if (loading && !job) return <Loading />;
  if (error || !job) return <ErrorState message={error || "Job not found."} onRetry={reload} />;
  const m: Match | null | undefined = job.match;

  const generate = async (kind: string) => {
    setGen({ kind, busy: true });
    try { const res = await api<AIResult>("/writing/generate/", { method: "POST", body: { job_id: job.id, kind, tone } }); setGen({ kind, res }); }
    catch (e: any) { toast(e.message, "err"); setGen(null); }
  };
  const del = async () => { if (!confirm("Delete this imported job?")) return; try { await api(`/jobs/${job.id}/`, { method: "DELETE" }); nav("/jobs"); } catch (e: any) { toast(e.message, "err"); } };

  return (
    <div className="space-y-6">
      <Link to="/jobs" className="text-sm muted hover:underline">← Back to jobs</Link>
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">{job.title}</h1>
            <p className="muted">{job.company} · {job.location || "Location not listed"}{job.is_remote && " · Remote"}{job.employment_type && ` · ${job.employment_type}`}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {job.salary_text && <Badge tone="green">{job.salary_text}</Badge>}
              {job.min_experience != null && <Badge>{job.min_experience}{job.max_experience ? `–${job.max_experience}` : "+"} yrs</Badge>}
              {job.source.kind === "demo" && <Badge tone="amber">Demo data — not a real vacancy</Badge>}
            </div>
            <p className="mt-3 text-xs muted">Source: {job.source.name}{job.source.attribution ? ` — ${job.source.attribution}` : ""} · last checked {fmtDateTime(job.last_checked_at)}{!job.is_active && " · no longer listed at the source"}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => toggleSave(job)}>{job.is_saved ? "★ Saved" : "☆ Save"}</Button>
            {job.application_status ? <Link to="/applications"><Button variant="secondary">In tracker: {job.application_status}</Button></Link> : <Button onClick={() => track(job)}>Add to tracker</Button>}
            {job.apply_url ? <a href={job.apply_url} target="_blank" rel="noreferrer noopener"><Button variant="secondary">Open original posting ↗</Button></a> : <Button variant="secondary" disabled title="This listing has no application page">No apply link</Button>}
          </div>
        </div>
        {job.possible_duplicate_application && <div className="mt-4"><Notice tone="amber">You already applied to a similar role: <strong>{job.possible_duplicate_application.job__title}</strong> at {job.possible_duplicate_application.job__company} ({job.possible_duplicate_application.status}). Check you are not duplicating an application.</Notice></div>}
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h2 className="font-semibold mb-2">Description</h2>
            <p className="prose-pre text-sm leading-relaxed">{job.description || "No description available."}</p>
          </Card>
          <Card>
            <h2 className="font-semibold mb-1">Writing assistant</h2>
            <p className="mb-3 text-sm muted">Drafts are based only on facts in your resume and profile. Always read and edit before sending.</p>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Select aria-label="Tone" className="!w-auto" value={tone} onChange={(e) => setTone(e.target.value)}>{["professional", "friendly", "confident", "concise"].map((t) => <option key={t}>{t}</option>)}</Select>
              <Button variant="secondary" size="sm" loading={gen?.busy && gen.kind === "cover_letter"} onClick={() => generate("cover_letter")}>Cover letter</Button>
              <Button variant="secondary" size="sm" loading={gen?.busy && gen.kind === "recruiter_message"} onClick={() => generate("recruiter_message")}>Recruiter message</Button>
            </div>
            {gen?.res && (
              <div className="fade-up">
                <div className="mb-2 flex items-center gap-2"><EngineBadge engine={gen.res.engine} model={gen.res.model} />{gen.res.note && <span className="text-xs muted">{gen.res.note}</span>}</div>
                <Textarea rows={10} value={gen.res.text} onChange={(e) => setGen({ ...gen, res: { ...gen.res!, text: e.target.value } })} aria-label="Generated text" />
                <div className="mt-2 flex gap-2"><Button size="sm" variant="secondary" onClick={async () => { await navigator.clipboard.writeText(gen.res!.text); toast("Copied to clipboard"); }}>Copy</Button></div>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h2 className="font-semibold mb-3">Why this score?</h2>
            {!m ? <p className="text-sm muted">{job.match_score == null ? <>Add a resume to see an explainable compatibility score. <Link className="underline" to="/resumes">Add resume</Link></> : "No breakdown available."}</p> : (
              <div className="space-y-4">
                <div className="flex items-center gap-3"><ScoreRing score={m.score} size={72} label="Compatibility" /><div><div className="font-semibold">{m.verdict}</div><div className="text-xs muted">Rule-based, fully explainable</div></div></div>
                <div className="space-y-3">
                  {m.factors.map((f) => (
                    <div key={f.factor} className="text-sm"><div className="mb-1 flex justify-between"><span className="font-medium">{f.factor}</span><span className="muted">{f.score}/{f.max}</span></div><Bar value={f.score} max={f.max} /><p className="mt-1 text-xs muted">{f.detail}</p></div>
                  ))}
                </div>
                {!!m.matched_skills.length && <div><div className="mb-1 text-xs font-medium muted">Skills you have</div><div className="flex flex-wrap gap-1">{m.matched_skills.map((s) => <Skill key={s} state="have">{s}</Skill>)}</div></div>}
                {!!m.missing_skills.length && <div><div className="mb-1 text-xs font-medium muted">Skills to add or learn</div><div className="flex flex-wrap gap-1">{m.missing_skills.map((s) => <Skill key={s} state="missing">{s}</Skill>)}</div></div>}
                {m.eligibility.warnings.map((w) => <Notice key={w}>{w}</Notice>)}
                <p className="text-xs muted">💡 {m.tip}</p>
                <div className="flex flex-wrap gap-2"><Link to={`/skills?job=${job.id}`}><Button size="sm" variant="secondary">Skill gap & roadmap</Button></Link><Link to={`/interview?job=${job.id}`}><Button size="sm" variant="secondary">Practice interview</Button></Link></div>
              </div>
            )}
          </Card>
          {job.imported_by_me && <Button variant="ghost" size="sm" onClick={del}>Delete this imported job</Button>}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ saved jobs
export function SavedJobs() {
  const { data, error, loading, reload } = useLoad(() => api<Job[]>("/saved-jobs/"), []);
  const { toggleSave, track } = useJobActions(reload);
  const toast = useToast();
  const [notes, setNotes] = useState<Record<number, string>>({});
  useEffect(() => { if (data) setNotes(Object.fromEntries(data.map((j) => [j.id, j.note || ""]))); }, [data]);
  const saveNote = async (id: number) => { try { await api(`/saved-jobs/${id}/`, { method: "PATCH", body: { note: notes[id] } }); toast("Note saved"); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <div>
      <PageHeader title="Saved jobs" subtitle="Jobs you bookmarked to review later." />
      {loading && !data ? <Loading /> : error ? <ErrorState message={error} onRetry={reload} /> : !data?.length ? (
        <Empty icon="⭐" title="Nothing saved yet" text="Tap the star on any job to keep it here." action={<Link to="/jobs"><Button>Browse jobs</Button></Link>} />
      ) : (
        <div className="space-y-4">{data.map((j) => (
          <div key={j.id}>
            <JobCard job={j} onToggleSave={toggleSave} onTrack={track} />
            <div className="mt-2 flex gap-2"><Input aria-label={`Note for ${j.title}`} placeholder="Private note (e.g. referral from Asha)" maxLength={300} value={notes[j.id] ?? ""} onChange={(e) => setNotes({ ...notes, [j.id]: e.target.value })} /><Button variant="secondary" size="sm" onClick={() => saveNote(j.id)}>Save note</Button></div>
          </div>
        ))}</div>
      )}
    </div>
  );
}
