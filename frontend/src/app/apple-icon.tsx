import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "#0f172a",
          overflow: "hidden",
        }}
      >
        <svg width="180" height="180" viewBox="0 0 32 32">
          <rect x={4} y={3} width={16} height={24} rx={2.5} fill="#ffffff" />
          <path d="M15 3 L20 3 L20 8 Z" fill="#94a3b8" />
          <rect x={7.5} y={12} width={10} height={2.6} rx={1.3} fill="#334155" />
          <rect x={7.5} y={18} width={7} height={2.6} rx={1.3} fill="#334155" />
          <circle cx={25} cy={26} r={9} fill="#10b981" stroke="#0f172a" strokeWidth={2.5} />
          <path
            d="M20.7 26.3 L23.7 29.3 L29.6 22.4"
            fill="none"
            stroke="#ffffff"
            strokeWidth={3.4}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    { ...size }
  );
}
