import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root to this folder so Next.js doesn't pick up a stray
  // package-lock.json higher in the directory tree.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
