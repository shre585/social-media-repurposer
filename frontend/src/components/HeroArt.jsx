export default function HeroArt() {
  return (
    <div className="hero-art" aria-hidden="true">
      <div className="phone">
        <div className="phone-notch" />
        <div className="phone-screen">
          <span className="play">▶</span>
          <div className="wave">{Array.from({ length: 14 }).map((_, i) => <i key={i} style={{ animationDelay: `${i * 0.09}s` }} />)}</div>
          <div className="scrub"><b /></div>
        </div>
      </div>
      <div className="float f1"><span>🎬</span><div><b>Reel</b><small>9:16 · 30s</small></div></div>
      <div className="float f2"><span>▶️</span><div><b>Short</b><small>auto-captions</small></div></div>
      <div className="float f3"><span>#️⃣</span><div><b>Hashtags</b><small>12 picked</small></div></div>
      <div className="float f4"><span>🧵</span><div><b>Thread</b><small>8 posts</small></div></div>
    </div>
  );
}
