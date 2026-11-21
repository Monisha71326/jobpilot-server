const $ = (id) => document.getElementById(id);
let cache = null; // {fields, attempt}

function show(msg, kind) { const s = $("status"); s.textContent = msg; s.className = kind || ""; s.style.display = "block"; }
function norm(u) { return u.trim().replace(/\/+$/, ""); }

async function ensureHostPermission(base) {
  const origin = new URL(base).origin + "/*";
  if (await chrome.permissions.contains({ origins: [origin] })) return true;
  return chrome.permissions.request({ origins: [origin] }); // asks the person, only for their own JobPilot address
}
async function call(path, opts = {}) {
  const { url, key } = await chrome.storage.local.get(["url", "key"]);
  const res = await fetch(norm(url) + "/api" + path, { ...opts, headers: { "X-Autofill-Key": key, "Content-Type": "application/json" } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}
async function load() {
  cache = await call("/autofill/profile/");
  const a = cache.attempt;
  $("app").textContent = a ? `Ready: ${a.job_title} at ${a.company}` : "No reviewed application is waiting. In JobPilot open an application → Prepare → “I reviewed this”. You can still fill your basic details.";
  $("fill").disabled = false;
}

$("save").onclick = async () => {
  try {
    const url = norm($("url").value);
    if (!/^https?:\/\//.test(url)) throw new Error("Address must start with http:// or https://");
    if (!(await ensureHostPermission(url))) throw new Error("Permission to reach JobPilot was declined.");
    await chrome.storage.local.set({ url, key: $("key").value.trim() });
    await load();
    show("Connected. Open the employer's application page, then press Fill.", "ok");
  } catch (e) { show(e.message, "err"); }
};

$("fill").onclick = async () => {
  try {
    if (!cache) await load();
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !/^https?:/.test(tab.url || "")) throw new Error("Open the employer's application page first.");
    await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, files: ["filler.js"] });
    const results = await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, func: (f) => window.__jobpilotFill(f), args: [cache.fields] });
    const filled = [...new Set(results.flatMap((r) => (r.result ? r.result.filled : [])))];
    const host = new URL(tab.url).hostname;
    const skipped = Object.keys(cache.fields).filter((k) => !filled.includes(k) && k !== "cover_letter");
    if (cache.attempt) {
      await call("/autofill/report/", { method: "POST", body: JSON.stringify({ attempt_id: cache.attempt.id, filled, skipped, host, error: filled.length ? "" : "No matching form fields were found on this page." }) });
    }
    show(filled.length
      ? `Filled ${filled.length} field(s): ${filled.join(", ")}.\n\nNow review EVERY field, attach your resume, and submit on the site yourself.`
      : "No matching fields found on this page (the form may be on another page, or use unusual labels). Nothing was changed.", filled.length ? "ok" : "err");
  } catch (e) { show(e.message, "err"); }
};

(async () => {
  const s = await chrome.storage.local.get(["url", "key"]);
  if (s.url) $("url").value = s.url;
  if (s.key) { $("key").value = s.key; try { await load(); } catch (e) { show(e.message, "err"); } }
})();
