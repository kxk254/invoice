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
          position: "relative",
          background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "radial-gradient(circle at 28% 22%, rgba(255,255,255,0.35), rgba(255,255,255,0) 55%)",
          }}
        />
        <svg width="180" height="180" viewBox="0 0 32 32" style={{ position: "absolute" }}>
          <path
            d="M10.5 7.5 L16 15 M21.5 7.5 L16 15 M16 15 L16 25 M11 18.5 L21 18.5 M11 21.5 L21 21.5"
            fill="none"
            stroke="#ffffff"
            strokeWidth={2.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    { ...size }
  );
}
