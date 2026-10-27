const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export const ACCEPT = ".mp4,.mov,.mkv,.webm,.pdf,.docx,.txt,.md";
const KINDS = {
  mp4: "video", mov: "video", mkv: "video", webm: "video",
  pdf: "document", docx: "document", txt: "text", md: "text",
};
export const KIND_META = {
  video: { icon: "🎬", label: "Video" },
  document: { icon: "📄", label: "Document" },
  text: { icon: "📝", label: "Text" },
};

export const detectKind = (name = "") => KINDS[name.split(".").pop().toLowerCase()] || null;
export const mediaUrl = (p) => (p ? (p.startsWith("http") ? p : BASE + p) : null);
export const isMedia = (kind) => kind === "video";

export function fmtTime(sec) {
  if (sec == null) return "";
  const s = Math.max(0, Math.round(sec));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = String(m).padStart(2, "0"), rr = String(r).padStart(2, "0");
  return h ? `${h}:${mm}:${rr}` : `${mm}:${rr}`;
}
export function fmtSize(bytes) {
  if (bytes > 1e9) return (bytes / 1e9).toFixed(1) + " GB";
  if (bytes > 1e6) return (bytes / 1e6).toFixed(1) + " MB";
  return Math.max(1, Math.round(bytes / 1e3)) + " KB";
}

function errMsg(data, fallback) {
  const d = data?.detail;
  if (!d) return fallback;
  if (typeof d === "string") return d;
  return d.map?.((x) => x.msg).join(", ") || fallback;
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      ...options,
    });
  } catch {
    throw new Error("Can't reach the server. Is the backend running?");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errMsg(data, `Request failed (${res.status})`));
  return data;
}

export const getPlatforms = () => request("/api/platforms");
export const uploadUrl = (url) => request("/api/upload-url", { method: "POST", body: JSON.stringify({ url }) });
export const startProcess = (payload) => request("/api/process", { method: "POST", body: JSON.stringify(payload) });
export const getStatus = (id) => request(`/api/status/${id}`);
export const getResult = (id) => request(`/api/results/${id}`);
export const getJobs = () => request("/api/jobs");
export const deleteJob = (id) => request(`/api/results/${id}`, { method: "DELETE" });
export const saveContent = (id, clipId, platform, body) =>
  request(`/api/results/${id}/clips/${clipId}/${platform}`, { method: "PUT", body: JSON.stringify(body) });
export const downloadUrl = (path) => (path ? BASE + path : null);
export const zipUrl = (id) => `${BASE}/api/download-all/${id}`;

export function uploadFile(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    fd.append("file", file);
    xhr.open("POST", `${BASE}/api/upload`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      xhr.status < 300 ? resolve(data) : reject(new Error(errMsg(data, "Upload failed")));
    };
    xhr.onerror = () => reject(new Error("Can't reach the server. Is the backend running?"));
    xhr.send(fd);
  });
}
