import "./HouseIllustration.css";

export default function HouseIllustration() {
  return (
    <div className="house-illustration">
      <svg width="300" height="320" viewBox="0 0 300 320" aria-hidden="true">
        {/* ground shadow */}
        <ellipse cx="150" cy="298" rx="78" ry="12" fill="rgba(43,36,32,0.10)" />

        {/* pointer lines */}
        <line className="pointer-line line-1" x1="212" y1="210" x2="255" y2="150" />
        <line className="pointer-line line-2" x1="97" y1="219" x2="55" y2="185" />
        <line className="pointer-line line-3" x1="185" y1="248" x2="222" y2="255" />

        {/* roof */}
        <polygon
          points="81,186 150,226 185,166 115,126"
          fill="#C1502E"
          stroke="#8F3A20"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <polygon
          points="219,186 150,226 185,166"
          fill="#D9714A"
          stroke="#8F3A20"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* walls */}
        <polygon
          points="81,250 150,290 150,226 81,186"
          fill="#E2D9C8"
          stroke="#B9AC94"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <polygon
          points="219,250 150,290 150,226 219,186"
          fill="#EDE6DA"
          stroke="#B9AC94"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* windows */}
        <polygon
          points="94.6,222 111.9,232 111.9,216 94.6,206"
          fill="#CFE0E6"
          stroke="#5B6B70"
          strokeWidth="1.2"
        />
        <polygon
          points="212.4,218 195,228 195,212 212.4,202"
          fill="#CFE0E6"
          stroke="#5B6B70"
          strokeWidth="1.2"
        />

        {/* door */}
        <polygon
          points="191.6,266 177.7,274 177.7,238 191.6,230"
          fill="#7A4A34"
          stroke="#5A3324"
          strokeWidth="1.2"
        />
      </svg>

      <div className="badge badge-1">Image reused elsewhere</div>
      <div className="badge badge-2">38% below market</div>
      <div className="badge badge-3">Address check</div>
      <div className="badge result badge-result">62 / 100 — High risk</div>
    </div>
  );
}
