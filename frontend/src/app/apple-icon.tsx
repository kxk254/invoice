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
          background: "linear-gradient(135deg, #0f766e 0%, #14b8a6 100%)",
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
            d="M9.5 6.5 L16 15 M22.5 6.5 L16 15 M16 15 L16 26 M9.5 17 L22.5 17 M9.5 22 L22.5 22"
            fill="none"
            stroke="#ffffff"
            strokeWidth={3.2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    { ...size }
  );
}
