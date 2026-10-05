export default function Loader() {
  return <div className="eq" role="img" aria-label="Working">{Array.from({ length: 6 }).map((_, i) => <i key={i} style={{ animationDelay: `${i * 0.12}s` }} />)}</div>;
}
