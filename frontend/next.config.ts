import type { NextConfig } from "next";

// Same LAN/Tailscale hosts already trusted by the Django backend
// (DJANGO_ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS in .env). The dev server only
// trusts `localhost` by default for *any* of these three things, so hitting
// it from one of these other addresses would otherwise load every page fine
// (plain GETs aren't checked) while every Server Action - every button that
// actually mutates data, e.g. Import, mark-sent, restore - gets silently
// rejected by Next's own CSRF Origin/Host check before it ever reaches our
// code, with no error surfaced to the page.
const LAN_HOSTS = ["100.94.246.4", "10.66.66.4", "10.66.66.5", "10.66.66.8", "192.168.11.71", "192.168.11.*"];

const nextConfig: NextConfig = {
  allowedDevOrigins: LAN_HOSTS,
  experimental: {
    serverActions: {
      allowedOrigins: LAN_HOSTS.map((host) => `${host}:3000`),
      // Default is 1MB, too small for a real historical AccountItem export.
      bodySizeLimit: "10mb",
    },
  },
};

export default nextConfig;
