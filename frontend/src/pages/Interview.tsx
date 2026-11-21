import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { fmtDate, useLoad, useToast } from "../lib/app";
import type { Interview as IV, Job } from "../lib/types";
import { Badge, Bar, Button, Card, Empty, EngineBadge, ErrorState, Field, Input, Loading, Notice, PageHeader, ScoreRing, Select, Textarea } from "../components/ui";

export default function Interview() {
  const [sp] = useSearchParams();
  const toast = useToast();
  const list = useLoad(() => api<IV[]>("/interviews/"), []);
  const jobs = useLoad(() => api<{ results: Job[] }>("/jobs/", { query: { sort: "recent" } }), []);
  const [session, setSession] = useState<IV | null>(null);
  const [setup, setSetup] = useState({ role: "", job_id: sp.get("job") || "", kind: "mixed", count: "5" });
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setBusy(true);
    try { setSession(await api<IV>("/interviews/", { method: "POST", body: { ...setup, job_id: setup.job_id ? Number(setup.job_id) : undefined, count: Number(setup.count) } })); list.reload(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const open = async (id: number) => { try { setSession(await api<IV>(`/interviews/${id}/`)); } catch (e: any) { toast(e.message, "err"); } };
  const remove = async (id: number) => { if (!confirm("Delete this practice session?")) return; try { await api(`/interviews/${id}/`, { method: "DELETE" }); list.reload(); } catch (e: any) { toast(e.message, "err"); } };

  if (session) return <Practice session={session} onUpdate={setSession} onExit={() => { setSession(null); list.reload(); }} />;

  return (
    <div>
      <PageHeader title="Interview practice" subtitle="Answer questions generated for a role or job. You get instant, specific feedback on structure, evidence and clarity — written by your local model when available, otherwise by transparent rules." />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <h2 className="mb-4 font-semibold">New session</h2>
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); start(); }}>
            <Field label="Practice for a job">{(id) => <Select id={id} value={setup.job_id} onChange={(e) => setSetup({ ...setup, job_id: e.target.value })}><option value="">— or type a role below —</option>{jobs.data?.results.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}</Select>}</Field>
            {!setup.job_id && <Field label="Role">{(id) => <Input id={id} placeholder="Backend Developer" value={setup.role} onChange={(e) => setSetup({ ...setup, role: e.target.value })} />}</Field>}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Type">{(id) => <Select id={id} value={setup.kind} onChange={(e) => setSetup({ ...setup, kind: e.target.value })}><option value="mixed">Mixed</option><option value="behavioral">Behavioural</option><option value="technical">Technical</option></Select>}</Field>
              <Field label="Questions">{(id) => <Select id={id} value={setup.count} onChange={(e) => setSetup({ ...setup, count: e.target.value })}>{[3, 5, 7, 10].map((n) => <option key={n}>{n}</option>)}</Select>}</Field>
            </div>
            <Button type="submit" className="w-full" loading={busy}>Start practice</Button>
          </form>
        </Card>
        <div className="lg:col-span-2">
          <h2 className="mb-3 font-semibold">Past sessions</h2>
          {list.loading && !list.data ? <Loading /> : list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data?.length ? <Empty icon="🎤" title="No sessions yet" text="Start your first mock interview. Nothing is recorded — answers are text only and stay on your machine." /> : (
            <div className="space-y-3">{list.data.map((s) => (
              <Card key={s.id} className="flex flex-wrap items-center justify-between gap-3">
                <div><div className="font-medium">{s.role_title}</div><div className="text-xs muted">{s.kind} · {s.answered}/{s.total} answered · {fmtDate((s as any).started_at)}</div>
                  <div className="mt-1 flex gap-1.5"><Badge tone={s.status === "completed" ? "green" : "amber"}>{s.status === "completed" ? "Completed" : "In progress"}</Badge>{s.summary?.average != null && <Badge tone="brand">Avg {s.summary.average}</Badge>}</div></div>
                <div className="flex gap-2"><Button size="sm" variant="secondary" onClick={() => open(s.id)}>{s.status === "completed" ? "Review" : "Continue"}</Button><Button size="sm" variant="ghost" onClick={() => remove(s.id)}>Delete</Button></div>
              </Card>))}</div>
          )}
        </div>
      </div>
    </div>
  );
}

function Practice({ session, onUpdate, onExit }: { session: IV; onUpdate: (s: IV) => void; onExit: () => void }) {
  const toast = useToast();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [listening, setListening] = useState(false);
  const recRef = useRef<any>(null);
  const questions = session.questions || [];
  const answered = new Map((session.answers || []).map((a) => [a.question_index, a]));
  const [idx, setIdx] = useState<number>(session.next_index ?? 0);
  const q = questions.find((x) => x.id === idx);
  const current = answered.get(idx);
  const done = session.status === "completed";
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

  useEffect(() => { setSeconds(0); setAnswer(""); const t = setInterval(() => setSeconds((s) => s + 1), 1000); return () => clearInterval(t); }, [idx]);
  useEffect(() => () => recRef.current?.stop(), []);

  const dictate = () => {
    if (listening) { recRef.current?.stop(); return; }
    const r = new SR(); r.continuous = true; r.interimResults = false; r.lang = "en-IN";
    r.onresult = (e: any) => { const t = Array.from(e.results).slice(e.resultIndex).map((x: any) => x[0].transcript).join(" "); setAnswer((a) => (a ? a + " " : "") + t.trim()); };
    r.onend = () => setListening(false); r.onerror = () => { setListening(false); toast("Voice input isn't available here. Type your answer instead.", "err"); };
    recRef.current = r; r.start(); setListening(true);
  };
  const submit = async () => {
    setBusy(true);
    try {
      const r = await api<{ completed: boolean }>(`/interviews/${session.id}/answer/`, { method: "POST", body: { question_index: idx, answer } });
      const fresh = await api<IV>(`/interviews/${session.id}/`); onUpdate(fresh);
      if (r.completed) toast("Session complete — see your summary below."); setAnswer("");
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const finish = async () => { try { onUpdate(await api<IV>(`/interviews/${session.id}/finish/`, { method: "POST" })); } catch (e: any) { toast(e.message, "err"); } };
  const mm = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  const fb = current?.feedback;

  return (
    <div className="space-y-6">
      <PageHeader title={`Mock interview: ${session.role_title}`} subtitle={<span className="flex items-center gap-2">{session.kind} · {answered.size}/{questions.length} answered <EngineBadge engine={session.engine} /></span>}
        actions={<><Button variant="secondary" onClick={onExit}>← All sessions</Button>{!done && answered.size > 0 && <Button variant="secondary" onClick={finish}>Finish & summarise</Button>}</>} />

      {done && session.summary && (
        <Card className="fade-up"><div className="flex flex-wrap items-center gap-5"><ScoreRing score={session.summary.average} size={80} label="Average score" /><div className="min-w-0 flex-1">
          <h2 className="font-semibold">Session summary</h2><p className="text-sm muted">{session.summary.answered} of {session.summary.total ?? questions.length} questions answered.</p>
          {!!session.summary.top_improvements?.length && <ul className="mt-2 list-disc pl-5 text-sm">{session.summary.top_improvements.map((t: string) => <li key={t}>{t}</li>)}</ul>}</div></div>
          {session.summary.verdict && <p className="mt-3"><Badge tone={session.summary.average >= 75 ? "green" : session.summary.average >= 55 ? "amber" : "red"}>{session.summary.verdict}</Badge></p>}</Card>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[14rem_1fr]">
        <nav aria-label="Questions" className="flex gap-2 overflow-x-auto lg:flex-col">
          {questions.map((x, i) => { const a = answered.get(x.id); return (
            <button key={x.id} onClick={() => setIdx(x.id)} className={`flex shrink-0 items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm cursor-pointer ${idx === x.id ? "border-brand-500 bg-brand-50 dark:bg-brand-600/10" : "border-c"}`}>
              <span>Q{i + 1}</span>{a ? <Badge tone={a.score >= 70 ? "green" : a.score >= 45 ? "amber" : "red"}>{a.score}</Badge> : <span className="text-xs muted">todo</span>}</button>); })}
        </nav>
        {q && (
          <div className="space-y-4">
            <Card>
              <div className="mb-2 flex items-center justify-between"><Badge tone={q.type === "technical" ? "blue" : "brand"}>{q.type}{q.skill ? ` · ${q.skill}` : ""}</Badge><span className="text-xs muted" aria-label="Elapsed time">⏱ {mm}</span></div>
              <h2 className="text-lg font-medium leading-snug">{q.text}</h2>
              <p className="mt-2 text-xs muted">Tip: for behavioural questions use Situation → Task → Action → Result, and include a number.</p>
            </Card>
            {current ? (
              <Card className="fade-up"><div className="flex items-center gap-4"><ScoreRing score={current.score} size={64} label="Answer score" /><div><h3 className="font-semibold">Feedback</h3><p className="text-sm">{typeof fb === "string" ? fb : fb?.feedback}</p></div></div>
                <p className="mt-4 rounded-xl surface-2 p-3 text-sm prose-pre"><span className="font-medium">Your answer: </span>{current.answer}</p>
                {!!fb?.strengths?.length && <div className="mt-3"><div className="text-sm font-medium text-emerald-700 dark:text-emerald-300">What worked</div><ul className="list-disc pl-5 text-sm">{fb.strengths.map((s: string) => <li key={s}>{s}</li>)}</ul></div>}
                {!!fb?.improvements?.length && <div className="mt-3"><div className="text-sm font-medium text-amber-700 dark:text-amber-300">To improve</div><ul className="list-disc pl-5 text-sm">{fb.improvements.map((s: string) => <li key={s}>{s}</li>)}</ul></div>}
                {fb?.stronger_answer && <div className="mt-3"><div className="text-sm font-medium">A stronger version</div><p className="rounded-xl surface-2 p-3 text-sm prose-pre">{fb.stronger_answer}</p></div>}
                {fb?.engine && <div className="mt-3"><EngineBadge engine={fb.engine} /></div>}
                {(() => { const nxt = questions.find((x) => !answered.has(x.id)); return nxt && !done ? <Button className="mt-4" onClick={() => setIdx(nxt.id)}>Next question →</Button> : null; })()}
              </Card>
            ) : done ? <Notice>This question was skipped.</Notice> : (
              <Card>
                <Textarea aria-label="Your answer" rows={8} placeholder="Type your answer as you would say it aloud…" maxLength={5000} value={answer} onChange={(e) => setAnswer(e.target.value)} />
                <div className="mt-1 flex items-center justify-between text-xs muted"><span>{answer.trim().split(/\s+/).filter(Boolean).length} words · aim for 80–200</span><Bar value={Math.min(answer.length, 800)} max={800} /></div>
                <div className="mt-3 flex flex-wrap gap-2"><Button loading={busy} disabled={answer.trim().length < 3} onClick={submit}>Get feedback</Button>
                  {SR && <Button variant="secondary" onClick={dictate} aria-pressed={listening}>{listening ? "⏹ Stop dictation" : "🎙 Dictate"}</Button>}</div>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
