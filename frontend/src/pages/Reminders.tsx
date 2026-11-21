import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { fmtDateTime, localInput, useLoad, useToast } from "../lib/app";
import type { Reminder } from "../lib/types";
import { Badge, Button, Card, Empty, ErrorState, Field, Input, Loading, PageHeader, Tabs, cx } from "../components/ui";

export default function Reminders() {
  const toast = useToast();
  const [scope, setScope] = useState<"open" | "all">("open");
  const { data, error, loading, reload } = useLoad(() => api<Reminder[]>("/reminders/", { query: { scope: scope === "open" ? "open" : "" } }), [scope]);
  const [f, setF] = useState({ title: "", due_at: localInput(24) });
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<any>, ok?: string) => { try { await fn(); if (ok) toast(ok); reload(); } catch (e: any) { toast(e.message, "err"); } };
  const add = async () => {
    setBusy(true);
    await act(async () => { await api("/reminders/", { method: "POST", body: { title: f.title, due_at: new Date(f.due_at).toISOString() } }); setF({ title: "", due_at: localInput(24) }); }, "Reminder added");
    setBusy(false);
  };
  return (
    <div>
      <PageHeader title="Reminders" subtitle="Follow-ups and deadlines. When a reminder comes due, you get a notification in the bell menu — no email service needed." />
      <Card className="mb-6">
        <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={(e) => { e.preventDefault(); add(); }}>
          <div className="flex-1"><Field label="Remind me to…">{(id) => <Input id={id} required maxLength={160} placeholder="Follow up with the Acme recruiter" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />}</Field></div>
          <Field label="When">{(id) => <Input id={id} type="datetime-local" required value={f.due_at} onChange={(e) => setF({ ...f, due_at: e.target.value })} />}</Field>
          <Button type="submit" loading={busy}>Add reminder</Button>
        </form>
      </Card>
      <div className="mb-4"><Tabs tabs={[{ id: "open", label: "Open" }, { id: "all", label: "All" }]} value={scope} onChange={setScope} /></div>
      {loading && !data ? <Loading /> : error ? <ErrorState message={error} onRetry={reload} /> : !data?.length ? <Empty icon="⏰" title={scope === "open" ? "Nothing due" : "No reminders yet"} text="Reminders you add — and follow-ups created when you mark an application as applied — appear here." /> : (
        <div className="space-y-2">{data.map((r) => (
          <Card key={r.id} className="flex items-center gap-3 !py-3">
            <input type="checkbox" className="h-4 w-4" aria-label={`Mark "${r.title}" ${r.done ? "not done" : "done"}`} checked={r.done} onChange={(e) => act(() => api(`/reminders/${r.id}/`, { method: "PATCH", body: { done: e.target.checked } }))} />
            <div className="min-w-0 flex-1"><div className={cx("text-sm font-medium", r.done && "line-through muted")}>{r.title}</div>
              <div className="text-xs muted">{fmtDateTime(r.due_at)} {r.overdue && <Badge tone="red">Overdue</Badge>} {r.application_id && <Link className="ml-1 text-brand-600 underline" to={`/applications/${r.application_id}`}>Open application</Link>}</div></div>
            <Button size="sm" variant="ghost" onClick={() => act(() => api(`/reminders/${r.id}/`, { method: "PATCH", body: { due_at: new Date(Date.now() + 86400_000).toISOString() } }), "Snoozed until tomorrow")}>Snooze 1 day</Button>
            <Button size="sm" variant="ghost" aria-label={`Delete ${r.title}`} onClick={() => act(() => api(`/reminders/${r.id}/`, { method: "DELETE" }), "Reminder deleted")}>Delete</Button>
          </Card>))}</div>
      )}
    </div>
  );
}
