// Thin fetch wrapper: token auth, JSON, and uniform error objects.
const TOKEN_KEY = "jp_token";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
}

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, message: string, data: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
  get code(): string | undefined { return this.data?.code; }
}

/** Turn DRF error payloads ({detail} or {field: [msgs]}) into one readable sentence. */
function messageFrom(status: number, data: any): string {
  if (data && typeof data === "object") {
    if (typeof data.detail === "string") return data.detail;
    const parts = Object.entries(data)
      .filter(([k]) => !["code", "needs_paste", "can_force", "existing_id", "warnings"].includes(k))
      .map(([k, v]) => `${k === "non_field_errors" ? "" : k.replace(/_/g, " ") + ": "}${Array.isArray(v) ? v.join(" ") : String(v)}`);
    if (parts.length) return parts.join(" ");
  }
  if (status === 0) return "Cannot reach the server. Is the backend running on port 8000?";
  if (status === 429) return "You have hit the free daily limit for this feature. It resets at midnight.";
  if (status >= 500) return "The server hit an unexpected error. Please try again.";
  return `Request failed (${status}).`;
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

export async function api<T = any>(path: string, opts: { method?: string; body?: any; query?: Record<string, any>; raw?: boolean } = {}): Promise<T> {
  const { method = "GET", body, query, raw } = opts;
  let url = `/api${path}`;
  if (query) {
    const qs = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") qs.set(k, String(v)); });
    const s = qs.toString();
    if (s) url += (url.includes("?") ? "&" : "?") + s;
  }
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Token ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, messageFrom(0, null), null);
  }
  if (raw) {
    if (!res.ok) throw new ApiError(res.status, messageFrom(res.status, null), null);
    return res as unknown as T;
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try { data = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    if (res.status === 401 && token && onUnauthorized) onUnauthorized();
    throw new ApiError(res.status, messageFrom(res.status, data), data);
  }
  return data as T;
}

/** Download an authenticated file (resume original / DOCX export) via blob. */
export async function download(path: string, fallbackName: string) {
  const res = await api<Response>(path, { raw: true });
  const cd = res.headers.get("Content-Disposition") || "";
  const m = /filename="?([^";]+)"?/.exec(cd);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = m?.[1] || fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
