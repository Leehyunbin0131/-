import type { NextConfig } from "next";

/** Server-side only: where Next proxies /api/v1/*. Browser calls same-origin /api/v1/... so guest cookies work with localhost:3000. */
const backendInternal =
  (process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );

/** LAN 등에서 접속 시 dev HMR 차단 경고를 없애려면 콤마로 구분해 호스트만 적습니다. 예: 192.168.45.180 */
const allowedDevOrigins = (process.env.NEXT_ALLOWED_DEV_ORIGINS ?? "")
  .split(",")
  .map((host) => host.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(allowedDevOrigins.length > 0 ? { allowedDevOrigins } : {}),
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendInternal}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
