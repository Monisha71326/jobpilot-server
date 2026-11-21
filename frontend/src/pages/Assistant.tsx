import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { timeAgo, useLoad, useToast } from "../lib/app";
import type { ChatMessage, Conversation, Job } from "../lib/types";
import { Badge, Button, Card, EngineBadge, ErrorState, Loading, PageHeader, Select, Spinner, Textarea, cx } from "../components/ui";

const STARTERS = [
  "How can I improve my resume for backend roles?",
  "Help me prepare a 60-second 'tell me about yourself'.",
  "What should I learn next to get hired faster?",
  "How do I negotiate salary for my first offer?",
];

export default function Assistant() {
  const toast = useToast();
  const convs = useLoad(() => api<Conversation[]>("/assistant/conversations/"), []);
  const jobs = useLoad(() => api<{ results: Job[] }>("/jobs/", { query: { sort: "recent" } }), []);
  const [active, setActive] = useState<Conversation | null>(null);
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [jobId, setJobId] = useState("");
  const [listOpen, setListOpen] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, sending]);

  const open = async (id: number) => {
    try { const c = await api<Conversation>(`/assistant/conversations/${id}/`); setActive(c); setMsgs(c.messages || []); setListOpen(false); } catch (e: any) { toast(e.message, "err"); }
  };
  const create = async (): Promise<Conversation | null> => {
    try { const c = await api<Conversation>("/assistant/conversations/", { method: "POST", body: jobId ? { job_id: Number(jobId) } : {} }); setActive(c); setMsgs([]); convs.reload(); return c; }
    catch (e: any) { toast(e.message, "err"); return null; }
  };
  const send = async (content: string) => {
    content = content.trim();
    if (!content || sending) return;
    const c = active ?? (await create());
    if (!c) return;
    setSending(true); setText("");
    setMsgs((m) => [...m, { id: -Date.now(), role: "user", content }]);
    try {
      const r = await api<{ assistant_message: ChatMessage }>(`/assistant/conversations/${c.id}/messages/`, { method: "POST", body: { content } });
      setMsgs((m) => [...m, r.assistant_message]); convs.reload();
    } catch (e: any) { toast(e.message, "err"); setMsgs((m) => m.slice(0, -1)); setText(content); } finally { setSending(false); }
  };
  const del = async (id: number) => {
    if (!confirm("Delete this conversation?")) return;
    try { await api(`/assistant/conversations/${id}/`, { method: "DELETE" }); if (active?.id === id) { setActive(null); setMsgs([]); } convs.reload(); } catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <div>
      <PageHeader title="AI career assistant" subtitle="Chat with a model running on your own computer. It knows your resume and profile, never sends them anywhere, and says so when it falls back to simple rules." />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[18rem_1fr]">
        <Card pad={false} className={cx("overflow-hidden", !listOpen && "hidden lg:block")}>
          <div className="space-y-2 border-b border-c p-3">
            <Select aria-label="Discuss a specific job" value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">General chat</option>{jobs.data?.results.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}</Select>
            <Button className="w-full" size="sm" onClick={() => create()}>+ New chat</Button>
          </div>
          <div className="max-h-[60vh] overflow-y-auto p-2">
            {convs.loading && !convs.data ? <Loading /> : convs.error ? <ErrorState message={convs.error} onRetry={convs.reload} /> : !convs.data?.length ? <p className="p-4 text-sm muted">No chats yet.</p> : convs.data.map((c) => (
              <div key={c.id} className={cx("group flex items-center gap-1 rounded-lg", active?.id === c.id && "bg-brand-50 dark:bg-brand-600/20")}>
                <button className="min-w-0 flex-1 px-3 py-2 text-left cursor-pointer" onClick={() => open(c.id)}><div className="truncate text-sm font-medium">{c.title}</div><div className="text-xs muted">{timeAgo(c.updated_at)}</div></button>
                <button className="px-2 text-xs opacity-60 hover:opacity-100 cursor-pointer" aria-label={`Delete ${c.title}`} onClick={() => del(c.id)}>🗑</button>
              </div>
            ))}
          </div>
        </Card>

        <Card pad={false} className="flex h-[70vh] min-h-[28rem] flex-col">
          <div className="flex items-center justify-between border-b border-c px-4 py-2.5"><span className="truncate text-sm font-medium">{active?.title || "New conversation"}</span>
            <Button className="lg:hidden" size="sm" variant="secondary" onClick={() => setListOpen(!listOpen)}>{listOpen ? "Hide chats" : "Chats"}</Button></div>
          <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
            {!msgs.length && (
              <div className="mx-auto max-w-md pt-6 text-center"><div className="mb-2 text-4xl" aria-hidden>✦</div><h2 className="font-semibold">Ask me anything about your job search</h2>
                <div className="mt-4 grid gap-2">{STARTERS.map((s) => <button key={s} onClick={() => send(s)} className="rounded-xl border border-c px-4 py-2.5 text-left text-sm hover:surface-2 cursor-pointer">{s}</button>)}</div></div>
            )}
            {msgs.map((m) => (
              <div key={m.id} className={cx("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cx("max-w-[85%] rounded-2xl px-4 py-2.5 text-sm", m.role === "user" ? "bg-brand-600 text-white" : "surface-2")}>
                  <div className="prose-pre">{m.content}</div>
                  {m.role === "assistant" && <div className="mt-2 flex items-center gap-2"><EngineBadge engine={m.engine} />{m.note && <span className="text-[11px] muted">{m.note}</span>}</div>}
                </div>
              </div>
            ))}
            {sending && <div className="flex items-center gap-2 text-sm muted"><Spinner className="h-4 w-4" /> Thinking… a local model can take a moment.</div>}
            <div ref={end} />
          </div>
          <form className="flex gap-2 border-t border-c p-3" onSubmit={(e) => { e.preventDefault(); send(text); }}>
            <Textarea aria-label="Message" rows={1} className="resize-none" placeholder="Type your question…" maxLength={4000} value={text} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }} />
            <Button type="submit" loading={sending} disabled={!text.trim()}>Send</Button>
          </form>
        </Card>
      </div>
      <p className="mt-3 text-xs muted"><Badge tone="amber">Heads-up</Badge> AI can be wrong. Check facts, and never paste passwords or ID numbers into the chat.</p>
    </div>
  );
}
