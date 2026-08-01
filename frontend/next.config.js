/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // All pages are "use client" with no server-side data fetching, so a full
  // static export works here and is what the S3 + CloudFront infra (frontend.tf)
  // actually expects. ("standalone" produces a Node server bundle, not static
  // HTML — that was a real mismatch: CI was syncing .next/static + public to S3,
  // which never contained the actual page HTML.)
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true }, // next/image requires a server; not available in static export
};

module.exports = nextConfig;
