import { useState } from "react";
import { downloadUrl, saveContent } from "../services/api.js";
import CopyButton from "./CopyButton.jsx";

export default function ResultCard({ jobId, clipId, platformId, platform, srt, onSaved }) {
  const { content, media, media_error: mediaError } = platform;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function startEdit() {
    setDraft({ title: content.title, caption: content.caption, hashtags: content.hashtags.join(" ") });
    setEditing(true);
  }
  async function save() {
    setSaving(true);
    setError("");
    try {
      const updated = await saveContent(jobId, clipId, platformId, {
        title: draft.title,
        caption: draft.caption,
        hashtags: draft.hashtags.split(/[\s,]+/).filter(Boolean),
      });
      onSaved(clipId, platformId, updated);
      setEditing(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const over = content.text.length > content.char_limit && platformId === "x";

  return (
    <div className="result">
      <div className="result-head">
        <span className="badge">{platform.aspect}</span>
        {media && <span className="badge">{media.duration}s{media.trimmed ? " (trimmed)" : ""}</span>}
        <span className="badge soft" title={platform.tip}>🕒 {platform.best_time[0]}</span>
      </div>

      {editing ? (
        <div className="edit">
          <label>Title<input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></label>
          <label>Caption<textarea rows={5} value={draft.caption} onChange={(e) => setDraft({ ...draft, caption: e.target.value })} /></label>
          <label>Hashtags<input value={draft.hashtags} onChange={(e) => setDraft({ ...draft, hashtags: e.target.value })} /></label>
          {error && <p className="error">{error}</p>}
          <div className="row">
            <button type="button" className="btn small primary" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save changes"}</button>
            <button type="button" className="btn small ghost" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <>
          <h4 className="r-title">{content.title}</h4>
          <pre className="post-text">{content.text}</pre>
          <div className="counter" data-over={over}>{content.text.length} / {content.char_limit} characters</div>
          <div className="chips">{content.hashtags.map((h) => <span key={h} className="tag">{h}</span>)}</div>
          <div className="row wrap">
            <CopyButton text={content.text} label="Copy post" className="primary" />
            <button type="button" className="btn small" onClick={startEdit}>✏️ Edit</button>
            {media && <a className="btn small" href={downloadUrl(media.download)}>⬇️ Download video</a>}
            {srt && <a className="btn small" href={downloadUrl(srt.download)}>💬 Captions .srt</a>}
          </div>
          {mediaError && <p className="error">This clip couldn't be rendered: {mediaError}</p>}
        </>
      )}
    </div>
  );
}
