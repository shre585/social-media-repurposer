import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ClipCard from "../components/ClipCard.jsx";
import ExtrasPanel from "../components/ExtrasPanel.jsx";
import ProcessingStatus from "../components/ProcessingStatus.jsx";
import { fmtTime, getResult, getStatus, isMedia, zipUrl } from "../services/api.js";

export default function Results() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const timer = useRef(null);

  const loadFull = useCallback(() => getResult(jobId).then(setJob).catch((e) => setError(e.message)), [jobId]);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const s = await getStatus(jobId);
        if (stop) return;
        if (s.status === "completed") return loadFull();
        setJob((prev) => ({ ...(prev || {}), ...s }));
        if (s.status === "failed") return;
        timer.current = setTimeout(tick, 1500);
      } catch (e) {
        if (!stop) setError(e.message);
      }
    }
    tick();
    return () => { stop = true; clearTimeout(timer.current); };
  }, [jobId, loadFull]);

  function onSaved(clipId, platformId, content) {
    setJob((j) => ({
      ...j,
      clips: j.clips.map((c) =>
        c.id !== clipId ? c : { ...c, platforms: { ...c.platforms, [platformId]: { ...c.platforms[platformId], content } } }
      ),
    }));
  }

  if (error) return <p className="error banner">{error} <Link to="/">Back home</Link></p>;
  if (!job) return <p className="muted">Loading your project…</p>;
  if (job.status !== "completed") {
    if (job.status === "uploaded") return <p className="notice">This file was uploaded but never started. <Link to="/">Go back and press Repurpose.</Link></p>;
    return (
      <>
        <ProcessingStatus job={job} />
        {job.status === "failed" && <div className="cta-row"><Link className="btn primary" to="/">Try again</Link></div>}
      </>
    );
  }

  const media = isMedia(job.kind);
  return (
    <>
      <div className="results-head">
        <div>
          <h1 className="page-title">{job.title}</h1>
          <p className="muted">{job.summary}</p>
        </div>
        <a className="btn primary" href={zipUrl(job.id)}>📦 Download everything (.zip)</a>
      </div>

      {job.warning && <p className="notice">{job.warning}</p>}

      <div className="stats">
        {media && <div className="stat"><b>{fmtTime(job.stats.duration)}</b><span>original length</span></div>}
        <div className="stat"><b>{job.stats.topics}</b><span>topics found</span></div>
        <div className="stat"><b>{job.stats.clips}</b><span>{media ? "clips cut" : "posts written"}</span></div>
        <div className="stat"><b>{job.stats.platforms}</b><span>platforms</span></div>
      </div>

      {job.keywords?.length > 0 && (
        <div className="chips big-chips">{job.keywords.map((k) => <span className="tag" key={k}>{k}</span>)}</div>
      )}

      <div className="clip-list">
        {job.clips.map((c, i) => (
          <ClipCard key={c.id} jobId={job.id} clip={c} index={i} kind={job.kind} onSaved={onSaved} />
        ))}
      </div>

      {job.extras && <ExtrasPanel extras={job.extras} />}

      {job.transcript?.length > 0 && (
        <details className="card transcript">
          <summary>📜 Full transcript ({job.transcript.length} segments)</summary>
          <div className="t-list">
            {job.transcript.map((s, i) => (
              <p key={i}><code>{fmtTime(s.start)}</code> {s.text}</p>
            ))}
          </div>
        </details>
      )}
    </>
  );
}
