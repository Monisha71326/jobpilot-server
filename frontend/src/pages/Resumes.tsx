import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, download } from "../lib/api";
import { fmtDate, fmtDateTime, useLoad, useToast } from "../lib/app";
import type { AIResult, Analysis, Job, ResumeContent, ResumeDetail, ResumeSummary, ResumeVersion } from "../lib/types";
import { Badge, Button, Card, Empty, EngineBadge, ErrorState, Field, Input, Loading, Modal, Notice, PageHeader, ScoreRing, Select, Skill, TagInput, Textarea } from "../components/ui";

export default function Resumes() {
  const toast = useToast();
  const nav = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const { data, error, loading, reload } = useLoad(() => api<ResumeSummary[]>("/resumes/"), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<{ resume: ResumeSummary } | null>(null);
  const [drag, setDrag] = useState(false);

  const upload = async (file?: File | null) => {
    if (!file) return;
    if (!/\.(pdf|docx)$/i.test(file.name)) { toast("Please choose a PDF or DOCX file.", "err"); return; }
    setBusy("upload");
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await api<ResumeDetail>("/resumes/", { method: "POST", body: fd });
      toast(`Parsed "${r.title}": ${r.skills.length} skills found.`); reload();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(null); if (fileRef.current) fileRef.current.value = ""; }
  };
  const create = async () => {
    setBusy("create");
    try { const r = await api<ResumeDetail>("/resumes/builder/", { method: "POST", body: { title: "My resume" } }); nav(`/resumes/${r.id}`); }
    catch (e: any) { toast(e.message, "err"); setBusy(null); }
  };
  const act = async (key: string, fn: () => Promise<any>, ok: string) => { setBusy(key); try { await fn(); toast(ok); reload(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(null); } };

  return (
    <div>
      <PageHeader title="Resumes" subtitle="Upload a PDF or DOCX to parse and analyse it, or build one here. Your files stay on this computer."
        actions={<><Button variant="secondary" loading={busy === "create"} onClick={create}>Build a resume</Button><Button loading={busy === "upload"} onClick={() => fileRef.current?.click()}>Upload resume</Button></>} />
      <input ref={fileRef} type="file" accept=".pdf,.docx" className="sr-only" aria-label="Upload resume file" onChange={(e) => upload(e.target.files?.[0])} />

      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files?.[0]); }}
        className={`mb-6 rounded-2xl border-2 border-dashed p-6 text-center text-sm transition ${drag ? "border-brand-500 bg-brand-50 dark:bg-brand-600/10" : "border-c muted"}`}>
        Drag a <strong>PDF or DOCX</strong> here (max 5 MB, text-based). Scanned images aren't supported.
      </div>

      {loading && !data ? <Loading /> : error ? <ErrorState message={error} onRetry={reload} /> : !data?.length ? (
        <Empty icon="📄" title="No resumes yet" text="Upload an existing resume or build a new one from your profile." />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.map((r) => (
            <Card key={r.id} className="fade-up">
              <div className="flex gap-4">
                <ScoreRing score={r.analysis_score} label="ATS score" size={60} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><h2 className="truncate font-semibold">{r.title}</h2>{r.is_primary && <Badge tone="green">Primary</Badge>}<Badge>{r.source === "builder" ? "Built here" : r.file_type.toUpperCase()}</Badge></div>
                  <p className="text-xs muted">Updated {fmtDate(r.updated_at)}{r.page_count ? ` · ${r.page_count} page(s)` : ""}{r.latest_version ? ` · v${r.latest_version}` : ""}</p>
                  <div className="mt-2 flex flex-wrap gap-1">{r.skills.slice(0, 6).map((s) => <Skill key={s}>{s}</Skill>)}{r.skills.length > 6 && <Badge>+{r.skills.length - 6}</Badge>}</div>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => setAnalysis({ resume: r })}>Analyse</Button>
                {r.source === "builder" || r.latest_version ? <Link to={`/resumes/${r.id}`}><Button size="sm" variant="secondary">Edit</Button></Link>
                  : <Button size="sm" variant="secondary" loading={busy === `b${r.id}`} onClick={() => act(`b${r.id}`, async () => { await api(`/resumes/${r.id}/to-builder/`, { method: "POST" }); nav(`/resumes/${r.id}`); }, "Converted to an editable version — please review it.")}>Make editable</Button>}
                {r.has_file && <Button size="sm" variant="ghost" onClick={() => download(`/resumes/${r.id}/file/`, r.original_filename).catch((e) => toast(e.message, "err"))}>Download original</Button>}
                {!r.is_primary && <Button size="sm" variant="ghost" loading={busy === `p${r.id}`} onClick={() => act(`p${r.id}`, () => api(`/resumes/${r.id}/set-primary/`, { method: "POST" }), "Primary resume updated")}>Make primary</Button>}
                <Button size="sm" variant="ghost" onClick={() => { const t = prompt("Rename resume", r.title); if (t?.trim()) act(`r${r.id}`, () => api(`/resumes/${r.id}/`, { method: "PATCH", body: { title: t } }), "Renamed"); }}>Rename</Button>
                <Button size="sm" variant="ghost" onClick={() => { if (confirm(`Delete "${r.title}"? Applications keep their history.`)) act(`d${r.id}`, () => api(`/resumes/${r.id}/`, { method: "DELETE" }), "Resume deleted"); }}>Delete</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {analysis && <AnalysisModal resume={analysis.resume} onClose={() => { setAnalysis(null); reload(); }} />}
    </div>
  );
}

// ------------------------------------------------------------------ analysis
function AnalysisModal({ resume, onClose }: { resume: ResumeSummary; onClose: () => void }) {
  const toast = useToast();
  const [res, setRes] = useState<{ analysis: Analysis; ai: AIResult } | null>(null);
  const [jobId, setJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const jobs = useLoad(() => api<{ results: Job[] }>("/jobs/", { query: { sort: "recent" } }), []);
  const run = async () => {
    setBusy(true);
    try { setRes(await api("/resumes/" + resume.id + "/analyze/", { method: "POST", body: jobId ? { job_id: Number(jobId) } : {} })); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const a = res?.analysis;
  return (
    <Modal open onClose={onClose} title={`Analyse: ${resume.title}`} wide>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1"><Field label="Optional: tailor to a job" hint="Shows which job keywords your resume is missing.">{(id) => (
          <Select id={id} value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">General analysis</option>{jobs.data?.results.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}</Select>)}</Field></div>
        <Button onClick={run} loading={busy}>{res ? "Re-run" : "Run analysis"}</Button>
      </div>
      {busy && <Loading text="Analysing… local AI can take up to a minute." />}
      {!res && !busy && <p className="text-sm muted">Checks run instantly on your machine. If Ollama is running, you also get AI-written suggestions.</p>}
      {a && !busy && (
        <div className="space-y-5 fade-up">
          <div className="flex items-center gap-4"><ScoreRing score={a.score} size={76} label="ATS score" /><div><div className="text-lg font-semibold">{a.grade}</div><div className="text-sm muted">{a.stats.words} words · {a.stats.bullets} bullets · {a.stats.skills} skills detected</div></div></div>
          {a.job_fit && (
            <Card className="surface-2 !border-0"><h3 className="font-medium mb-2">Fit for the selected job{a.job_fit.skill_coverage_pct != null && ` — ${a.job_fit.skill_coverage_pct}% skill coverage`}</h3>
              <div className="flex flex-wrap gap-1">{a.job_fit.matched_skills.map((s) => <Skill key={s} state="have">{s}</Skill>)}{a.job_fit.missing_skills.map((s) => <Skill key={s} state="missing">{s}</Skill>)}</div>
              {!!a.job_fit.missing_keywords.length && <p className="mt-2 text-xs muted">Keywords from the posting not on your resume: {a.job_fit.missing_keywords.join(", ")}</p>}</Card>
          )}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div><h3 className="mb-2 font-medium">Checks</h3><ul className="space-y-2">{a.checks.map((c) => (
              <li key={c.id} className="flex gap-2 text-sm"><span className={c.passed ? "text-emerald-600" : "text-red-500"} aria-label={c.passed ? "passed" : "failed"}>{c.passed ? "✓" : "✗"}</span><div><div>{c.label} <span className="text-xs muted">· {c.detail}</span></div>{c.fix && <div className="text-xs text-amber-700 dark:text-amber-300">→ {c.fix}</div>}</div></li>))}</ul></div>
            <div><h3 className="mb-2 font-medium flex items-center gap-2">AI suggestions <EngineBadge engine={res!.ai.engine} model={res!.ai.model} /></h3>
              <div className="rounded-xl surface-2 p-3 text-sm prose-pre">{res!.ai.text}</div>{res!.ai.note && <p className="mt-2 text-xs muted">{res!.ai.note}</p>}</div>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ builder / editor
const blankExp = { company: "", title: "", location: "", start: "", end: "", bullets: [""] };
const blankEdu = { school: "", degree: "", start: "", end: "", details: "" };
const blankProj = { name: "", description: "", bullets: [] as string[] };

export function ResumeEditor() {
  const { id } = useParams();
  const toast = useToast();
  const { data: resume, error, loading, reload } = useLoad(() => api<ResumeDetail>(`/resumes/${id}/`), [id]);
  const versions = useLoad(() => api<ResumeVersion[]>(`/resumes/${id}/versions/`), [id]);
  const templates = useLoad(() => api<{ id: string; label: string; description: string }[]>("/resume-templates/"), []);
  const [content, setContent] = useState<ResumeContent | null>(null);
  const [template, setTemplate] = useState("classic");
  const [note, setNote] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState<string | null>(null);

  // initialise editor from the newest version once
  if (versions.data && versions.data.length && loaded !== id) {
    setContent(versions.data[0].content); setTemplate(versions.data[0].template); setLoaded(id!);
  }

  if ((loading && !resume) || versions.loading && !content) return <Loading />;
  if (error || !resume) return <ErrorState message={error || "Resume not found."} onRetry={reload} />;
  if (!content) return <ErrorState message="This resume has no editable version yet." onRetry={() => { versions.reload(); }} />;

  const upd = (fn: (c: ResumeContent) => void) => { const c: ResumeContent = structuredClone(content); fn(c); setContent(c); setDirty(true); };
  const save = async () => {
    setBusy(true);
    try { await api(`/resumes/${id}/versions/`, { method: "POST", body: { content, template, note } }); toast("Saved as a new version"); setDirty(false); setNote(""); versions.reload(); reload(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const exportDocx = () => download(`/resumes/${id}/export/?template=${template}`, "resume.docx").catch((e) => toast(e.message, "err"));
  const restore = (v: ResumeVersion) => { setContent(v.content); setTemplate(v.template); setDirty(true); toast(`Loaded v${v.version_no} — save to keep it as a new version.`); };
  const b = content.basics;

  return (
    <div className="space-y-6">
      <Link to="/resumes" className="text-sm muted hover:underline">← Back to resumes</Link>
      <PageHeader title={resume.title} subtitle={dirty ? "You have unsaved changes." : "All changes saved."}
        actions={<><Button variant="secondary" onClick={exportDocx}>Download DOCX</Button><Button onClick={save} loading={busy} disabled={!dirty}>Save version</Button></>} />
      {resume.source === "upload" && <Notice tone="amber">This was imported from an uploaded file. Parsing is best-effort — check every section against your original.</Notice>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h2 className="mb-3 font-semibold">Contact</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Full name">{(i) => <Input id={i} value={b.name} onChange={(e) => upd((c) => { c.basics.name = e.target.value; })} />}</Field>
              <Field label="Headline">{(i) => <Input id={i} value={b.headline} onChange={(e) => upd((c) => { c.basics.headline = e.target.value; })} />}</Field>
              <Field label="Email">{(i) => <Input id={i} type="email" value={b.email} onChange={(e) => upd((c) => { c.basics.email = e.target.value; })} />}</Field>
              <Field label="Phone">{(i) => <Input id={i} value={b.phone} onChange={(e) => upd((c) => { c.basics.phone = e.target.value; })} />}</Field>
              <Field label="Location">{(i) => <Input id={i} value={b.location} onChange={(e) => upd((c) => { c.basics.location = e.target.value; })} />}</Field>
              <Field label="LinkedIn">{(i) => <Input id={i} type="url" value={b.links.linkedin || ""} onChange={(e) => upd((c) => { c.basics.links.linkedin = e.target.value; })} />}</Field>
              <Field label="GitHub">{(i) => <Input id={i} type="url" value={b.links.github || ""} onChange={(e) => upd((c) => { c.basics.links.github = e.target.value; })} />}</Field>
              <Field label="Portfolio">{(i) => <Input id={i} type="url" value={b.links.portfolio || ""} onChange={(e) => upd((c) => { c.basics.links.portfolio = e.target.value; })} />}</Field>
            </div>
            <div className="mt-3"><Field label="Summary" hint="2–3 lines: who you are, your target role, your strongest skills.">{(i) => <Textarea id={i} rows={3} value={content.summary} onChange={(e) => upd((c) => { c.summary = e.target.value; })} />}</Field></div>
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Experience</h2><Button size="sm" variant="secondary" onClick={() => upd((c) => { c.experience.push(structuredClone(blankExp)); })}>+ Add role</Button></div>
            {!content.experience.length && <p className="text-sm muted">No roles yet. Freshers: add internships or projects instead.</p>}
            <div className="space-y-5">{content.experience.map((e, i) => (
              <div key={i} className="rounded-xl border border-c p-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Field label="Job title">{(k) => <Input id={k} value={e.title} onChange={(ev) => upd((c) => { c.experience[i].title = ev.target.value; })} />}</Field>
                  <Field label="Company">{(k) => <Input id={k} value={e.company} onChange={(ev) => upd((c) => { c.experience[i].company = ev.target.value; })} />}</Field>
                  <Field label="Start">{(k) => <Input id={k} placeholder="Jan 2023" value={e.start} onChange={(ev) => upd((c) => { c.experience[i].start = ev.target.value; })} />}</Field>
                  <Field label="End">{(k) => <Input id={k} placeholder="Present" value={e.end} onChange={(ev) => upd((c) => { c.experience[i].end = ev.target.value; })} />}</Field>
                </div>
                <div className="mt-3"><Field label="Achievements (one per line)" hint="Start with a verb and include a number: 'Reduced page load time by 40%'.">{(k) => <Textarea id={k} rows={4} value={e.bullets.join("\n")} onChange={(ev) => upd((c) => { c.experience[i].bullets = ev.target.value.split("\n"); })} />}</Field></div>
                <div className="mt-2 flex gap-2">
                  <Button size="sm" variant="ghost" disabled={i === 0} onClick={() => upd((c) => { [c.experience[i - 1], c.experience[i]] = [c.experience[i], c.experience[i - 1]]; })}>↑ Move up</Button>
                  <Button size="sm" variant="ghost" onClick={() => upd((c) => { c.experience.splice(i, 1); })}>Remove</Button>
                </div>
              </div>))}</div>
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Education</h2><Button size="sm" variant="secondary" onClick={() => upd((c) => { c.education.push({ ...blankEdu }); })}>+ Add education</Button></div>
            <div className="space-y-4">{content.education.map((e, i) => (
              <div key={i} className="grid gap-3 rounded-xl border border-c p-4 sm:grid-cols-2">
                <Field label="Degree">{(k) => <Input id={k} value={e.degree} onChange={(ev) => upd((c) => { c.education[i].degree = ev.target.value; })} />}</Field>
                <Field label="School">{(k) => <Input id={k} value={e.school} onChange={(ev) => upd((c) => { c.education[i].school = ev.target.value; })} />}</Field>
                <Field label="Start">{(k) => <Input id={k} value={e.start} onChange={(ev) => upd((c) => { c.education[i].start = ev.target.value; })} />}</Field>
                <Field label="End">{(k) => <Input id={k} value={e.end} onChange={(ev) => upd((c) => { c.education[i].end = ev.target.value; })} />}</Field>
                <div className="sm:col-span-2"><Field label="Details">{(k) => <Input id={k} value={e.details} onChange={(ev) => upd((c) => { c.education[i].details = ev.target.value; })} />}</Field></div>
                <div><Button size="sm" variant="ghost" onClick={() => upd((c) => { c.education.splice(i, 1); })}>Remove</Button></div>
              </div>))}</div>
          </Card>

          <Card>
            <h2 className="mb-3 font-semibold">Skills & certifications</h2>
            <Field label="Skills" hint="Press Enter or comma after each skill.">{(i) => <TagInput id={i} value={content.skills} onChange={(v) => upd((c) => { c.skills = v; })} placeholder="Python, React, SQL…" />}</Field>
            <div className="mt-3"><Field label="Certifications">{(i) => <TagInput id={i} value={content.certifications} onChange={(v) => upd((c) => { c.certifications = v; })} placeholder="AWS Cloud Practitioner…" />}</Field></div>
          </Card>

          <Card>
            <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Projects</h2><Button size="sm" variant="secondary" onClick={() => upd((c) => { c.projects.push(structuredClone(blankProj)); })}>+ Add project</Button></div>
            <div className="space-y-4">{content.projects.map((p, i) => (
              <div key={i} className="space-y-3 rounded-xl border border-c p-4">
                <Field label="Project name">{(k) => <Input id={k} value={p.name} onChange={(ev) => upd((c) => { c.projects[i].name = ev.target.value; })} />}</Field>
                <Field label="Description">{(k) => <Textarea id={k} rows={2} value={p.description} onChange={(ev) => upd((c) => { c.projects[i].description = ev.target.value; })} />}</Field>
                <Button size="sm" variant="ghost" onClick={() => upd((c) => { c.projects.splice(i, 1); })}>Remove</Button>
              </div>))}</div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h2 className="mb-3 font-semibold">Template</h2>
            <div className="space-y-2">{templates.data?.map((t) => (
              <label key={t.id} className={`block cursor-pointer rounded-xl border p-3 text-sm ${template === t.id ? "border-brand-500 bg-brand-50 dark:bg-brand-600/10" : "border-c"}`}>
                <input type="radio" name="tpl" className="mr-2" checked={template === t.id} onChange={() => { setTemplate(t.id); setDirty(true); }} /><strong>{t.label}</strong><div className="ml-6 text-xs muted">{t.description}</div></label>))}</div>
            <p className="mt-3 text-xs muted">The template applies to the DOCX download.</p>
          </Card>
          <Card>
            <h2 className="mb-3 font-semibold">Save note</h2>
            <Input aria-label="Version note" placeholder="e.g. Tailored for backend roles" maxLength={160} value={note} onChange={(e) => setNote(e.target.value)} />
          </Card>
          <Card>
            <h2 className="mb-3 font-semibold">Version history</h2>
            {!versions.data?.length ? <p className="text-sm muted">No versions yet.</p> : <ul className="space-y-2">{versions.data.map((v) => (
              <li key={v.version_no} className="flex items-center justify-between gap-2 text-sm"><div><div className="font-medium">v{v.version_no} <span className="text-xs muted">· {v.template}</span></div><div className="text-xs muted">{fmtDateTime(v.created_at)}{v.note && ` · ${v.note}`}</div></div>
                <div className="flex"><Button size="sm" variant="ghost" onClick={() => restore(v)}>Load</Button><Button size="sm" variant="ghost" onClick={() => download(`/resumes/${id}/export/?version=${v.version_no}`, "resume.docx").catch((e) => toast(e.message, "err"))}>DOCX</Button></div></li>))}</ul>}
          </Card>
          <Card>
            <h2 className="mb-2 font-semibold">Use in my profile</h2>
            <p className="mb-3 text-xs muted">Copy detected skills and years of experience into your profile (you can edit them there).</p>
            <Button size="sm" variant="secondary" onClick={async () => { try { await api(`/resumes/${id}/apply-to-profile/`, { method: "POST" }); toast("Profile updated from this resume"); } catch (e: any) { toast(e.message, "err"); } }}>Apply to profile</Button>
          </Card>
        </div>
      </div>
    </div>
  );
}
