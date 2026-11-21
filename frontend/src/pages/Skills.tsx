import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { fmtDate, useLoad, useToast } from "../lib/app";
import type { Goal, Job, SkillGapResult } from "../lib/types";
import { Badge, Bar, Button, Card, Empty, EngineBadge, ErrorState, Field, Input, Loading, Notice, PageHeader, ScoreRing, Select, Skill, Tabs } from "../components/ui";

type Roadmap = SkillGapResult["roadmap"];

export default function Skills() {
  const [sp] = useSearchParams();
  const [tab, setTab] = useState<"gap" | "goals">("gap");
  return (
    <div>
      <PageHeader title="Skills & learning roadmap" subtitle="Compare your skills with a role or a specific job, then follow a phased plan. Hours are rough estimates for a motivated beginner, not market data." />
      <div className="mb-5"><Tabs tabs={[{ id: "gap", label: "Skill gap" }, { id: "goals", label: "Career goals" }]} value={tab} onChange={setTab} /></div>
      {tab === "gap" ? <Gap initialJob={sp.get("job") || ""} /> : <Goals />}
    </div>
  );
}

function RoadmapView({ roadmap }: { roadmap: Roadmap }) {
  if (!roadmap.phases.length) return <Notice tone="green">Nothing missing — you already cover every required skill. 🎉</Notice>;
  return (
    <div>
      <p className="mb-3 text-sm muted">About <strong>{roadmap.total_weeks} weeks</strong> at {roadmap.hours_per_week} h/week ({roadmap.total_hours} hours total).</p>
      <ol className="space-y-4 border-l-2 border-brand-200 pl-5 dark:border-brand-600/40">
        {roadmap.phases.map((p) => (
          <li key={p.title} className="relative"><span className="absolute -left-[1.85rem] top-1 h-3 w-3 rounded-full bg-brand-500" aria-hidden />
            <div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{p.title}</h3><Badge>{p.weeks}</Badge><Badge tone="gray">~{p.est_hours} h</Badge></div>
            <p className="mt-1 text-sm">🎯 {p.milestone}</p>
            <div className="mt-2 space-y-1 text-sm">{Object.entries(p.resources).map(([skill, res]) => (
              <div key={skill}><span className="font-medium">{skill}:</span> {(Array.isArray(res) ? res : []).map((r: any, i: number) => r?.url ? <span key={i}>{i > 0 && " · "}<a className="text-brand-600 underline" href={r.url} target="_blank" rel="noreferrer noopener">{r.title || r.name || r.url}</a></span> : <span key={i}>{i > 0 && " · "}{String(r?.title ?? r)}</span>)}</div>))}</div>
          </li>))}
      </ol>
    </div>
  );
}

function Gap({ initialJob }: { initialJob: string }) {
  const toast = useToast();
  const roles = useLoad(() => api<{ role: string; skills: string[] }[]>("/skills/roles/"), []);
  const jobs = useLoad(() => api<{ results: Job[] }>("/jobs/", { query: { sort: "recent" } }), []);
  const [f, setF] = useState({ role: "", job_id: initialJob, hours: "8", with_ai: false });
  const [res, setRes] = useState<SkillGapResult | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setRes(await api<SkillGapResult>("/skills/gap/", { method: "POST", body: { role: f.role, job_id: f.job_id ? Number(f.job_id) : undefined, hours_per_week: Number(f.hours), with_ai: f.with_ai } })); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const saveGoal = async () => { try { await api("/goals/", { method: "POST", body: { target_role: res!.target } }); toast("Saved as a career goal"); } catch (e: any) { toast(e.message, "err"); } };
  useEffect(() => { if (initialJob && jobs.data) run(); /* auto-run when arriving from a job page */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!jobs.data]);
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card className="h-fit">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(); }}>
          <Field label="Target job">{(id) => <Select id={id} value={f.job_id} onChange={(e) => setF({ ...f, job_id: e.target.value })}><option value="">— choose a role instead —</option>{jobs.data?.results.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}</Select>}</Field>
          {!f.job_id && <Field label="Target role" hint="Pick a known role for the best results.">{(id) => <><Input id={id} list="role-list" placeholder="Backend Developer" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} /><datalist id="role-list">{roles.data?.map((r) => <option key={r.role} value={r.role} />)}</datalist></>}</Field>}
          <Field label="Hours per week">{(id) => <Input id={id} type="number" min={2} max={40} value={f.hours} onChange={(e) => setF({ ...f, hours: e.target.value })} />}</Field>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={f.with_ai} onChange={(e) => setF({ ...f, with_ai: e.target.checked })} /> Add a short AI-written study plan (uses local model)</label>
          <Button type="submit" className="w-full" loading={busy} disabled={!f.role && !f.job_id}>Analyse gap</Button>
        </form>
      </Card>
      <div className="space-y-6 lg:col-span-2">
        {!res ? <Empty icon="🧭" title="Find out what to learn next" text="Choose a job or role. Your skills come from your profile and all your resumes." /> : (
          <>
            {res.note && <Notice>{res.note}</Notice>}
            <Card className="fade-up">
              <div className="flex flex-wrap items-center gap-4"><ScoreRing score={res.coverage_pct} size={72} label="Skill coverage" /><div className="flex-1"><h2 className="text-lg font-semibold">{res.target}</h2><p className="text-sm muted">You have {res.have.length} of {res.required.length} required skills.</p></div><Button variant="secondary" size="sm" onClick={saveGoal} disabled={!res.known_role}>Save as career goal</Button></div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div><div className="mb-1 text-xs font-medium muted">You have</div><div className="flex flex-wrap gap-1">{res.have.length ? res.have.map((s) => <Skill key={s} state="have">{s}</Skill>) : <span className="text-sm muted">None yet</span>}</div></div>
                <div><div className="mb-1 text-xs font-medium muted">To learn</div><div className="flex flex-wrap gap-1">{res.missing.length ? res.missing.map((s) => <Skill key={s} state="missing">{s}</Skill>) : <span className="text-sm muted">Nothing — you're covered</span>}</div></div>
              </div>
            </Card>
            {res.ai && <Card><div className="mb-2 flex items-center gap-2"><h3 className="font-semibold">Study plan</h3><EngineBadge engine={res.ai.engine} model={res.ai.model} /></div><p className="text-sm prose-pre">{res.ai.text}</p></Card>}
            <Card><h3 className="mb-3 font-semibold">Learning roadmap</h3><RoadmapView roadmap={res.roadmap} /></Card>
          </>
        )}
      </div>
    </div>
  );
}

function Goals() {
  const toast = useToast();
  const { data, error, loading, reload } = useLoad(() => api<Goal[]>("/goals/"), []);
  const roles = useLoad(() => api<{ role: string }[]>("/skills/roles/"), []);
  const [f, setF] = useState({ target_role: "", target_date: "" });
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const add = async () => { setBusy(true); try { await api("/goals/", { method: "POST", body: { ...f, target_date: f.target_date || null } }); setF({ target_role: "", target_date: "" }); toast("Goal created"); reload(); } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  const toggle = async (g: Goal, skill: string) => {
    const done = g.completed_skills.includes(skill) ? g.completed_skills.filter((s) => s !== skill) : [...g.completed_skills, skill];
    try { await api(`/goals/${g.id}/`, { method: "PATCH", body: { completed_skills: done } }); reload(); } catch (e: any) { toast(e.message, "err"); }
  };
  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); toast(ok); reload(); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <div className="space-y-6">
      <Card>
        <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={(e) => { e.preventDefault(); add(); }}>
          <div className="flex-1"><Field label="I want to become a…">{(id) => <><Input id={id} list="goal-roles" required placeholder="Data Analyst" value={f.target_role} onChange={(e) => setF({ ...f, target_role: e.target.value })} /><datalist id="goal-roles">{roles.data?.map((r) => <option key={r.role} value={r.role} />)}</datalist></>}</Field></div>
          <Field label="By (optional)">{(id) => <Input id={id} type="date" value={f.target_date} onChange={(e) => setF({ ...f, target_date: e.target.value })} />}</Field>
          <Button type="submit" loading={busy}>Create goal</Button>
        </form>
      </Card>
      {loading && !data ? <Loading /> : error ? <ErrorState message={error} onRetry={reload} /> : !data?.length ? <Empty icon="🎯" title="No career goals yet" text="Set a target role and tick off skills as you learn them." /> : data.map((g) => (
        <Card key={g.id}>
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">{g.title}</h3><p className="text-xs muted">Target: {g.target_role}{g.target_date && ` · by ${fmtDate(g.target_date)}`}</p></div>
            <div className="flex items-center gap-2"><Badge tone={g.status === "achieved" ? "green" : "brand"}>{g.status}</Badge>
              <Button size="sm" variant="ghost" onClick={() => act(() => api(`/goals/${g.id}/regenerate/`, { method: "POST" }), "Roadmap refreshed from your latest skills")}>Refresh</Button>
              <Button size="sm" variant="ghost" onClick={() => setOpen(open === g.id ? null : g.id)}>{open === g.id ? "Hide roadmap" : "Roadmap"}</Button>
              <Button size="sm" variant="ghost" onClick={() => { if (confirm("Delete this goal?")) act(() => api(`/goals/${g.id}/`, { method: "DELETE" }), "Goal deleted"); }}>Delete</Button></div></div>
          <div className="mt-3 flex items-center gap-3"><Bar value={g.progress} tone="green" /><span className="text-sm font-medium">{g.progress}%</span></div>
          <div className="mt-3 flex flex-wrap gap-2">{g.skills_needed.map((s) => (
            <label key={s} className="flex cursor-pointer items-center gap-1.5 rounded-full border border-c px-3 py-1 text-sm"><input type="checkbox" checked={g.completed_skills.includes(s)} onChange={() => toggle(g, s)} />{s}</label>))}</div>
          {open === g.id && <div className="mt-5 border-t border-c pt-4"><RoadmapView roadmap={g.roadmap} /></div>}
        </Card>
      ))}
    </div>
  );
}
