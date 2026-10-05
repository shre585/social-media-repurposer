import { useState } from "react";
import { fmtTime, mediaUrl } from "../services/api.js";
import ResultCard from "./ResultCard.jsx";

function Carousel({ slides }) {
  return (
    <div className="carousel" aria-label="Carousel preview">
      {slides.map((s, i) => (
        <div className="slide" key={i}>
          <span className="slide-n">{i + 1}/{slides.length}</span>
          <strong>{s.title}</strong>
          <p>{s.body}</p>
        </div>
      ))}
    </div>
  );
}

export default function ClipCard({ jobId, clip, index, kind, onSaved }) {
  const pids = Object.keys(clip.platforms);
  const [tab, setTab] = useState(pids[0]);
  const active = clip.platforms[tab];
  const isMedia = kind === "video" || kind === "audio";
  const media = active?.media;
  const pct = Math.round(clip.importance * 100);

  return (
    <article className="card clip">
      <header className="clip-head">
        <span className="clip-n">{index + 1}</span>
        <div>
          <h3>{clip.title}</h3>
          <p className="muted">
            {isMedia ? `${fmtTime(clip.start)} → ${fmtTime(clip.end)} · ${clip.duration}s` : `Concept: ${clip.topic}`}
          </p>
        </div>
        <div className="score" title="How strong a moment this is (AI importance + speaking energy + scene changes)">
          <span>{pct}</span><small>score</small>
        </div>
      </header>

      <div className="chips">{clip.keywords.slice(0, 5).map((k) => <span key={k} className="tag soft">{k}</span>)}</div>

      <div className="tabs" role="tablist">
        {pids.map((p) => (
          <button key={p} role="tab" aria-selected={tab === p} className={tab === p ? "on" : ""} onClick={() => setTab(p)}>
            {clip.platforms[p].emoji} {clip.platforms[p].label}
          </button>
        ))}
        <button role="tab" aria-selected={tab === "_carousel"} className={tab === "_carousel" ? "on" : ""} onClick={() => setTab("_carousel")}>
          🎠 Carousel
        </button>
      </div>

      {tab === "_carousel" ? (
        <Carousel slides={clip.carousel} />
      ) : (
        <div className="clip-body">
          {isMedia && (
            <div className={`player ar-${active.aspect.replace(":", "x")}`}>
              {media ? (
                <video key={media.url} src={mediaUrl(media.url)} poster={mediaUrl(clip.thumbnail)} controls preload="none" playsInline />
              ) : (
                <div className="player-empty">No video for this platform</div>
              )}
            </div>
          )}
          <ResultCard jobId={jobId} clipId={clip.id} platformId={tab} platform={active} srt={clip.srt} onSaved={onSaved} />
        </div>
      )}
    </article>
  );
}
