import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { STATUS_LABEL, fmtDateTime, timeAgo, useAuth, useLoad, useToast } from "../lib/app";
import type { AppStatus, Dashboard as D, Job } from "../lib/types";
import { Badge, Bar, Button, Card, Empty, ErrorState, Loading, Notice, PageHeader, ScoreRing, scoreTone } from "../components/ui";

const ORDER: AppStatus[] = ["wishlist", "preparing", "applied", "interviewing", "offer", "rejected"];
const COLORS: Record<string, string> = { wishlist: "bg-slate-400", preparing: "bg-amber-500", applied: "bg-sky-500", interviewing: "bg-brand-500", offer: "bg-emerald-500", rejected: "bg-red-400" };

export default function Dashboard() {
  const { user } = useAuth();
  const toast = useToast();
  const { data, error, loading, reload } = useLoad(() => api<D>("/dashboard/"), []);
  const rec = useLoad(() => api<{ has_resume: boolean; results: Job[] }>("/jobs/recommended/"), []);
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorState message={error || "Could not load dashboard."} onRetry={reload} />;

  const maxWeek = Math.max(1, ...data.weekly.map((w) => w.applied));
  const maxCount = Math.max(1, ...ORDER.map((s) => data.counts[s]));
  const done = async (id: number) => { try { await api(`/reminders/${id}/`, { method: "PATCH", body: { done: true } }); toast("Reminder completed"); reload(); } catch (e: any) { toast(e.message, "err"); } };

  return (
    <div className="space-y-6">
      <PageHeader title={`Hello${user?.first_name ? `, ${user.first_name}` : ""} 👋`} subtitle="Here is where your job search stands today."
        actions={<><Link to="/jobs"><Button>Find jobs</Button></Link><Link to="/applications"><Button variant="secondary">Open tracker</Button></Link></>} />

      {!data.ai.ready && (
        <Notice tone="blue">
          <strong>Local AI is {data.ai.enabled ? "not running" : "turned off"}.</strong> Everything still works using built-in rules (matching, ATS checks, template letters).
          To enable AI-written text for free, install <a className="underline" href="https://ollama.com/download" target="_blank" rel="noreferrer">Ollama</a> and run <code className="rounded bg-black/10 px-1">ollama pull {data.ai.model}</code>. <Link className="underline" to="/settings">Details</Link>
        </Notice>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Applications" value={data.total_applications} hint={`${data.counts.applied + data.counts.interviewing + data.counts.offer} active`} />
        <Stat label="Interviewing" value={data.counts.interviewing} hint={`${data.counts.offer} offer(s)`} />
        <Stat label="Response rate" value={data.response_rate == null ? "—" : `${data.response_rate}%`} hint="of submitted applications" />
        <Stat label="Saved jobs" value={data.saved_jobs} hint={<Link className="text-brand-600 hover:underline" to="/saved">View saved</Link>} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="font-semibold mb-4">Pipeline</h2>
          {data.total_applications === 0 ? <Empty icon="🎯" title="No applications yet" text="Save a job, then add it to your tracker to see your pipeline here." action={<Link to="/jobs"><Button>Browse jobs</Button></Link>} /> : (
            <div className="space-y-3">
              {ORDER.map((s) => (
                <div key={s} className="flex items-center gap-3 text-sm">
                  <span className="w-24 muted">{STATUS_LABEL[s]}</span>
                  <div className="flex-1 h-6 rounded-lg surface-2 overflow-hidden"><div className={`h-full rounded-lg ${COLORS[s]}`} style={{ width: `${(data.counts[s] / maxCount) * 100}%`, minWidth: data.counts[s] ? 8 : 0 }} /></div>
                  <span className="w-6 text-right font-medium">{data.counts[s]}</span>
                </div>
              ))}
            </div>
          )}
          <h3 className="font-semibold mt-8 mb-3 text-sm">Applications submitted per week (last 8 weeks)</h3>
          <div className="flex h-28 items-end gap-2" role="img" aria-label="Weekly applications bar chart">
            {data.weekly.map((w, i) => (
              <div key={i} className="flex flex-1 flex-col items-center gap-1">
                <span className="text-[11px] muted">{w.applied || ""}</span>
                <div className="w-full rounded-t-md bg-brand-500/80" style={{ height: `${(w.applied / maxWeek) * 80}%`, minHeight: w.applied ? 4 : 2, opacity: w.applied ? 1 : 0.25 }} />
                <span className="text-[10px] muted">{w.label}</span>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="font-semibold mb-3">Profile strength</h2>
            <div className="flex items-center gap-4">
              <ScoreRing score={data.profile_completeness.percent} size={64} label="Profile completeness" />
              <div className="text-sm">{data.profile_completeness.missing.length ? <>Add: <span className="muted">{data.profile_completeness.missing.slice(0, 3).join(", ")}</span></> : "Profile complete 🎉"}</div>
            </div>
            <Link to="/settings"><Button variant="secondary" size="sm" className="mt-4 w-full">Edit profile</Button></Link>
          </Card>
          <Card>
            <h2 className="font-semibold mb-3">Primary resume</h2>
            {data.resume ? (
              <div className="flex items-center gap-4"><ScoreRing score={data.resume.score} size={64} label="Resume score" /><div className="text-sm"><div className="font-medium">{data.resume.title}</div><Link className="text-brand-600 hover:underline" to={`/resumes`}>{data.resume.score == null ? "Run analysis" : "View analysis"}</Link></div></div>
            ) : <><p className="text-sm muted mb-3">Upload a resume to unlock matching and analysis.</p><Link to="/resumes"><Button size="sm">Add resume</Button></Link></>}
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="font-semibold mb-3">Upcoming reminders</h2>
          {!data.reminders.length ? <p className="text-sm muted">Nothing due. Reminders are created automatically when you mark an application as applied, and you can add your own.</p> : (
            <ul className="divide-y divide-[var(--border)]">
              {data.reminders.map((r) => (
                <li key={r.id} className="flex items-center gap-3 py-2.5 text-sm">
                  <div className="flex-1"><div className="font-medium">{r.title}</div><div className={r.overdue ? "text-red-600 text-xs" : "text-xs muted"}>{r.overdue ? "Overdue · " : ""}{fmtDateTime(r.due_at)}</div></div>
                  <Button variant="secondary" size="sm" onClick={() => done(r.id)}>Done</Button>
                </li>
              ))}
            </ul>
          )}
          <Link to="/reminders" className="mt-3 inline-block text-sm text-brand-600 hover:underline">All reminders →</Link>
        </Card>
        <Card>
          <h2 className="font-semibold mb-3">Recent activity</h2>
          {!data.recent_activity.length ? <p className="text-sm muted">Your application history will appear here.</p> : (
            <ul className="space-y-3">
              {data.recent_activity.map((a) => (
                <li key={a.id} className="text-sm"><Link to={`/applications/${a.application_id}`} className="font-medium hover:underline">{a.label}</Link><div className="muted">{a.message} · {timeAgo(a.created_at)}</div></li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Recommended for you</h2><Link to="/jobs" className="text-sm text-brand-600 hover:underline">See all jobs →</Link></div>
        {rec.loading ? <Loading /> : !rec.data?.has_resume ? <p className="text-sm muted">Add a resume to see jobs ranked by how well they fit you.</p> : !rec.data.results.length ? <p className="text-sm muted">No jobs yet — open <Link className="underline" to="/jobs">Find jobs</Link> to load demo data or fetch from a free job source.</p> : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {rec.data.results.map((j) => (
              <Link key={j.id} to={`/jobs/${j.id}`} className="flex items-center gap-3 rounded-xl border border-c p-3 hover:surface-2">
                <ScoreRing score={j.match_score} size={48} label="Match" />
                <div className="min-w-0"><div className="truncate text-sm font-medium">{j.title}</div><div className="truncate text-xs muted">{j.company}</div><Badge tone={scoreTone(j.match_score)}>{j.match_verdict}</Badge></div>
              </Link>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h2 className="font-semibold mb-3">Today's free usage</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(data.usage).map(([k, v]) => (
            <div key={k} className="text-xs"><div className="mb-1 flex justify-between"><span className="muted">{k.replace(/_/g, " ")}</span><span>{v.used}/{v.limit}</span></div><Bar value={v.used} max={v.limit} tone={v.used / v.limit > 0.85 ? "amber" : "brand"} /></div>
          ))}
        </div>
        <p className="mt-3 text-xs muted">Limits protect your machine and reset at midnight. Billing is disabled — there is nothing to pay for.</p>
      </Card>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return <Card><div className="text-sm muted">{label}</div><div className="mt-1 text-3xl font-semibold tracking-tight">{value}</div><div className="mt-1 text-xs muted">{hint}</div></Card>;
}
