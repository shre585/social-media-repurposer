import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import HeroArt from "../components/HeroArt.jsx";
import FilePreview from "../components/FilePreview.jsx";
import PlatformSelector from "../components/PlatformSelector.jsx";
import UploadBox from "../components/UploadBox.jsx";
import { detectKind, getPlatforms, isMedia, startProcess, uploadFile, uploadUrl } from "../services/api.js";

const TONES = [
  { id: "educational", label: "📚 Educational" },
  { id: "genz", label: "✨ Gen-Z" },
  { id: "professional", label: "💼 Professional" },
  { id: "funny", label: "😂 Funny" },
];
const LANGS = [
  { id: "english", label: "English" },
  { id: "hinglish", label: "Hinglish" },
  { id: "hindi", label: "हिन्दी" },
];

export default function Home() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("file");
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState("");
  const [platforms, setPlatforms] = useState([]);
  const [selected, setSelected] = useState(["instagram", "youtube"]);
  const [aiInfo, setAiInfo] = useState(null);
  const [tone, setTone] = useState("educational");
  const [language, setLanguage] = useState("english");
  const [maxClips, setMaxClips] = useState(6);
  const [clipLen, setClipLen] = useState([20, 60]);
  const [reframe, setReframe] = useState("blur");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getPlatforms()
      .then((d) => { setPlatforms(d.platforms); setAiInfo(d); })
      .catch((e) => setError(e.message));
  }, []);

  const kind = mode === "url" ? "video" : file ? detectKind(file.name) : null;
  const media = kind ? isMedia(kind) : true;
  const ready = (mode === "file" ? !!file : url.trim().length > 8) && selected.length > 0 && !busy;

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  function pickFile(f) {
    setError("");
    if (!detectKind(f.name)) {
      setError("That file type isn't supported yet. Try a video (MP4, MOV, MKV, WEBM) or a document (PDF, DOCX, TXT, MD).");
      return;
    }
    setFile(f);
  }

  async function submit() {
    setError("");
    try {
      setBusy("Uploading…");
      const up = mode === "file" ? await uploadFile(file, (p) => setBusy(`Uploading… ${p}%`)) : await uploadUrl(url.trim());
      setBusy("Getting things ready…");
      await startProcess({
        job_id: up.job_id, platforms: selected, tone, language,
        max_clips: maxClips, min_clip_seconds: clipLen[0], max_clip_seconds: clipLen[1], reframe,
      });
      navigate(`/results/${up.job_id}`);
    } catch (e) {
      setError(e.message);
      setBusy("");
    }
  }

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow"><i>NEW</i> built for busy creators</span>
          <h1>One upload.<br /><span className="grad">Every platform.</span></h1>
          <p className="lead">
            Drop in a lecture video, PDF, Word doc or blog text. We find the best moments, cut them to size, and write the
            captions, hashtags and threads for each app.
          </p>
          <p className="hand">1 hour of video → a week of posts ↴</p>
        </div>
        <HeroArt />
      </section>

      <div className="marquee" aria-hidden="true">
        <div>
          {Array.from({ length: 2 }).map((_, i) => (
            <span key={i}>REELS ✦ SHORTS ✦ CAPTIONS ✦ HASHTAGS ✦ THREADS ✦ CAROUSELS ✦ SRT ✦ SEO ✦ </span>
          ))}
        </div>
      </div>

      <div className="stack">
        <UploadBox mode={mode} setMode={setMode} onFile={pickFile} url={url} setUrl={setUrl} />
        {mode === "file" && file && <FilePreview file={file} onRemove={() => setFile(null)} />}

        <PlatformSelector platforms={platforms} selected={selected} onToggle={toggle} />

        <section className="card options" aria-label="Customize">
          <h2 className="section-title">Make it yours</h2>
          <div className="opt-grid">
            <fieldset>
              <legend>Tone of voice</legend>
              <div className="pills">
                {TONES.map((t) => (
                  <button type="button" key={t.id} className={tone === t.id ? "on" : ""} onClick={() => setTone(t.id)}>{t.label}</button>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend>Caption language</legend>
              <div className="pills">
                {LANGS.map((l) => (
                  <button type="button" key={l.id} className={language === l.id ? "on" : ""} onClick={() => setLanguage(l.id)}>{l.label}</button>
                ))}
              </div>
            </fieldset>
            <label className="range">
              <span>Max {media ? "clips" : "posts"}: <b>{maxClips}</b></span>
              <input type="range" min="1" max="12" value={maxClips} onChange={(e) => setMaxClips(+e.target.value)} />
            </label>
            {media && (
              <>
                <label className="range">
                  <span>Clip length: <b>{clipLen[0]}s – {clipLen[1]}s</b></span>
                  <input type="range" min="10" max="90" step="5" value={clipLen[1]}
                    onChange={(e) => setClipLen([Math.min(clipLen[0], +e.target.value - 5), +e.target.value])} />
                </label>
                <fieldset>
                  <legend>When the shape doesn't match</legend>
                  <div className="pills">
                    <button type="button" className={reframe === "blur" ? "on" : ""} onClick={() => setReframe("blur")}>🌫️ Blurred background</button>
                    <button type="button" className={reframe === "crop" ? "on" : ""} onClick={() => setReframe("crop")}>🔲 Crop to fill</button>
                  </div>
                </fieldset>
              </>
            )}
          </div>
          {aiInfo && !aiInfo.ai_enabled && (
            <p className="notice">
              No AI key found, so we'll use the built-in keyword analyser. It works, but add an API key in <code>.env</code> for much smarter clips and captions.
            </p>
          )}
        </section>

        {error && <p className="error banner" role="alert">{error}</p>}

        <div className="cta-row">
          <button type="button" className="btn primary big" disabled={!ready} onClick={submit}>
            {busy || "✨ Repurpose it"}
          </button>
          {!ready && !busy && <span className="muted">Add a file or link and pick at least one platform.</span>}
        </div>
      </div>
    </>
  );
}
