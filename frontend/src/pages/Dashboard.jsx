import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { KIND_META, deleteJob, fmtTime, getJobs } from "../services/api.js";

const STATUS = { completed: "Ready", processing: "Working", queued: "In line", failed: "Failed", uploaded: "Not started" };

export default function Dashboard() {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState("");

  const load = () => getJobs().then((d) => setJobs(d.jobs)).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function remove(id) {
    if (!window.confirm("Delete this batch and all of its clips?")) return;
    await deleteJob(id).catch((e) => setError(e.message));
    load();
  }

  const done = (jobs || []).filter((j) => j.status === "completed");
  const totalClips = done.reduce((n, j) => n + (j.stats?.clips || 0), 0);

  return (
    <>
      <h1 className="page-title">My projects</h1>
      {error && <p className="error banner">{error}</p>}

      {jobs && jobs.length > 0 && (
        <div className="stats">
          <div className="stat"><b>{jobs.length}</b><span>projects</span></div>
          <div className="stat"><b>{totalClips}</b><span>clips & posts made</span></div>
          <div className="stat"><b>{done.length}</b><span>ready to post</span></div>
        </div>
      )}

      {jobs === null && !error && <p className="muted">Loading…</p>}
      {jobs?.length === 0 && (
        <div className="card empty">
          <div className="dz-emoji">📭</div>
          <h3>Nothing here yet</h3>
          <p className="muted">Upload your first video, podcast or PDF to get started.</p>
          <Link className="btn primary" to="/">Start a project</Link>
        </div>
      )}

      <div className="grid">
        {(jobs || []).map((j) => (
          <article key={j.id} className="card job">
            <div className="job-top">
              <span className="fp-icon">{KIND_META[j.kind]?.icon || "📦"}</span>
              <span className={`status ${j.status}`}>{STATUS[j.status] || j.status}</span>
            </div>
            <h3 title={j.filename}>{j.title || j.filename}</h3>
            <p className="muted">
              {j.stats ? `${j.stats.clips} clips · ${j.stats.platforms} platforms${j.stats.duration ? ` · ${fmtTime(j.stats.duration)}` : ""}` : j.status === "processing" ? `${j.progress}% done` : "—"}
            </p>
            <div className="row">
              <Link className="btn small primary" to={`/results/${j.id}`}>Open</Link>
              <button className="btn small ghost" onClick={() => remove(j.id)}>Delete</button>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
