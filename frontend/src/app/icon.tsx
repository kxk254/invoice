import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "#333363",
          borderRadius: 7,
          overflow: "hidden",
        }}
      >
        <svg width="32" height="32" viewBox="0 0 32 32">
          {/* 請求書 (receipt/invoice paper) */}
          <rect x={7} y={4} width={18} height={24} rx={2} fill="#ffffff" />
          <path d="M20 4 L25 4 L25 9 Z" fill="#b9c0d4" />
          {/* Yen mark */}
          <path
            d="M11 8 L16 15 M21 8 L16 15 M16 15 L16 24 M11.5 18 L20.5 18 M11.5 21 L20.5 21"
            fill="none"
            stroke="#333363"
            strokeWidth={2.3}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Hanko seal stamp accent */}
          <circle cx={26} cy={26} r={5} fill="#d1382c" stroke="#333363" strokeWidth={1.6} />
        </svg>
      </div>
    ),
    { ...size }
  );
}
