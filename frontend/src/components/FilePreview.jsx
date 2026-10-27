import { useEffect, useMemo } from "react";
import { KIND_META, detectKind, fmtSize } from "../services/api.js";

export default function FilePreview({ file, onRemove }) {
  const kind = detectKind(file.name);
  const objectUrl = useMemo(() => (kind === "video" ? URL.createObjectURL(file) : null), [file, kind]);
  useEffect(() => () => objectUrl && URL.revokeObjectURL(objectUrl), [objectUrl]);
  const meta = KIND_META[kind] || { icon: "📦", label: "File" };

  return (
    <div className="card file-preview">
      <div className="fp-head">
        <span className="fp-icon" aria-hidden="true">{meta.icon}</span>
        <div className="fp-meta">
          <strong title={file.name}>{file.name}</strong>
          <span className="muted">{meta.label} · {fmtSize(file.size)}</span>
        </div>
        <button type="button" className="btn small ghost" onClick={onRemove}>✕ Remove</button>
      </div>
      {kind === "video" && <video src={objectUrl} controls preload="metadata" className="fp-media" />}
    </div>
  );
}
