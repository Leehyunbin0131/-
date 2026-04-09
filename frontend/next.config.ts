import type { NextConfig } from "next";

/** Server-side only: where Next proxies /api/v1/*. Browser calls same-origin /api/v1/... so guest cookies work with localhost:3000. */
const backendInternal =
  (process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );

const nextConfig: NextConfig = {
  reactStrictMode: true,
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
