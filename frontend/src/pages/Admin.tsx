import { Navigate } from "react-router-dom";
import { api } from "../lib/api";
import { fmtDateTime, useAuth, useLoad } from "../lib/app";
import { Badge, Button, Card, ErrorState, Loading, PageHeader } from "../components/ui";

interface Stats {
  users: { total: number; new_7d: number }; resumes: number; jobs: { total: number; active: number; by_source: { source__name: string; n: number }[] };
  sources: { slug: string; name: string; last_fetched_at: string | null; is_active: boolean }[];
  applications: { total: number; by_status: { status: string; n: number }[] }; conversations: number; interviews: number;
  usage_today: { feature: string; total: number }[]; admin_url: string;
}

export default function Admin() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useLoad(() => api<Stats>("/admin-stats/"), []);
  if (!user?.is_staff) return <Navigate to="/" replace />;
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorState message={error || "Could not load stats."} onRetry={reload} />;
  const tile = (label: string, v: number | string, hint?: string) => <Card key={label}><div className="text-sm muted">{label}</div><div className="mt-1 text-3xl font-semibold">{v}</div>{hint && <div className="text-xs muted">{hint}</div>}</Card>;
  return (
    <div className="space-y-6">
      <PageHeader title="Admin dashboard" subtitle="Platform-wide counts only. Private content like resumes, letters and chats is never shown here."
        actions={<><Button variant="secondary" onClick={reload}>Refresh</Button><a href={`${location.protocol}//${location.hostname}:8000${data.admin_url}`} target="_blank" rel="noreferrer"><Button>Open Django admin ↗</Button></a></>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {tile("Users", data.users.total, `${data.users.new_7d} new this week`)}{tile("Resumes", data.resumes)}
        {tile("Jobs", data.jobs.total, `${data.jobs.active} active`)}{tile("Applications", data.applications.total)}
        {tile("AI chats", data.conversations)}{tile("Mock interviews", data.interviews)}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card><h2 className="mb-3 font-semibold">Jobs by source</h2><ul className="space-y-2 text-sm">{data.jobs.by_source.map((s) => <li key={s.source__name} className="flex justify-between"><span>{s.source__name}</span><Badge>{s.n}</Badge></li>)}{!data.jobs.by_source.length && <li className="muted">No jobs yet.</li>}</ul></Card>
        <Card><h2 className="mb-3 font-semibold">Applications by status</h2><ul className="space-y-2 text-sm">{data.applications.by_status.map((s) => <li key={s.status} className="flex justify-between"><span className="capitalize">{s.status}</span><Badge>{s.n}</Badge></li>)}{!data.applications.by_status.length && <li className="muted">None yet.</li>}</ul></Card>
        <Card><h2 className="mb-3 font-semibold">Job sources</h2><ul className="space-y-2 text-sm">{data.sources.map((s) => <li key={s.slug} className="flex justify-between gap-3"><span>{s.name}</span><span className="text-xs muted">{s.last_fetched_at ? fmtDateTime(s.last_fetched_at) : "never fetched"}</span></li>)}</ul></Card>
        <Card><h2 className="mb-3 font-semibold">AI & feature usage today</h2><ul className="space-y-2 text-sm">{data.usage_today.map((u) => <li key={u.feature} className="flex justify-between"><span>{u.feature.replace(/_/g, " ")}</span><Badge tone="brand">{u.total}</Badge></li>)}{!data.usage_today.length && <li className="muted">No usage today.</li>}</ul></Card>
      </div>
    </div>
  );
}
