import { useRef, useState } from "react";
import { ACCEPT } from "../services/api.js";

export default function UploadBox({ mode, setMode, onFile, url, setUrl }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);

  function onDrop(e) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  }

  return (
    <section className="card upload" aria-label="Add your content">
      <div className="seg" role="tablist">
        <button type="button" role="tab" aria-selected={mode === "file"} className={mode === "file" ? "on" : ""} onClick={() => setMode("file")}>
          📁 Upload a file
        </button>
        <button type="button" role="tab" aria-selected={mode === "url"} className={mode === "url" ? "on" : ""} onClick={() => setMode("url")}>
          🔗 Paste a YouTube link
        </button>
      </div>

      {mode === "file" ? (
        <div
          className={`dropzone ${drag ? "drag" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <input ref={inputRef} type="file" accept={ACCEPT} hidden onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
          <div className="dz-emoji" aria-hidden="true">☁️</div>
          <h3>Drop your content here</h3>
          <p>or <u>browse your files</u></p>
          <div className="kinds">
            <span>🎬 MP4 · MOV · MKV</span><span>📄 PDF · DOCX</span><span>📝 TXT · MD</span>
          </div>
        </div>
      ) : (
        <div className="urlbox">
          <label htmlFor="yt-url">Video link</label>
          <input id="yt-url" type="url" placeholder="https://www.youtube.com/watch?v=…" value={url} onChange={(e) => setUrl(e.target.value)} />
          <p className="muted">Public videos only. We download it at up to 720p, then work on it like an upload.</p>
        </div>
      )}
    </section>
  );
}
