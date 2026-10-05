import Loader from "./Loader.jsx";

const QUIPS = [
  "Slicing your transcript into snackable bits…",
  "Teaching the AI to ignore your 'umm's…",
  "Picking the spiciest hashtags…",
  "Asking FFmpeg very nicely…",
];

export default function ProcessingStatus({ job }) {
  const steps = job.steps || [];
  const idx = Math.max(0, steps.findIndex((s) => s.id === job.stage));
  const failed = job.status === "failed";
  const quip = QUIPS[Math.floor((job.progress || 0) / 8) % QUIPS.length];

  return (
    <section className="card processing" aria-live="polite">
      <div className="proc-top">
        <Loader />
        <div>
          <h2>{failed ? "That didn't work out" : "Creating your content…"}</h2>
          <p className="muted">{failed ? job.error : job.message || quip}</p>
        </div>
      </div>

      {!failed && (
        <>
          <div className="bar" role="progressbar" aria-valuenow={job.progress || 0} aria-valuemin={0} aria-valuemax={100}>
            <div className="bar-fill" style={{ width: `${job.progress || 0}%` }} />
            <span>{job.progress || 0}%</span>
          </div>
          <ol className="steps">
            {steps.map((s, i) => (
              <li key={s.id} className={i < idx ? "done" : i === idx ? "active" : ""}>
                <span className="dot">{i < idx ? "✓" : i + 1}</span>
                {s.label}
              </li>
            ))}
          </ol>
          <p className="muted small-note">Long videos can take a few minutes. You can leave this page - your batch will be in "My batches".</p>
        </>
      )}
    </section>
  );
}
