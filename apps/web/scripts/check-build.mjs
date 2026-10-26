// Post-build checks for things a unit test cannot see: installability and privacy of the
// service worker, and compatibility with a strict Content-Security-Policy.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const dist = "dist";
const problems = [];
const fail = (message) => problems.push(message);

if (!existsSync(dist)) {
  console.error("dist/ not found: run `npm run build` first");
  process.exit(1);
}

// 1. Web app manifest: name, standalone display, 192 and 512 px icons that exist.
const manifest = JSON.parse(readFileSync(join(dist, "manifest.webmanifest"), "utf8"));
if (!manifest.name || !manifest.short_name) fail("manifest needs name and short_name");
if (manifest.display !== "standalone") fail("manifest display must be standalone");
if (manifest.start_url !== "/") fail("manifest start_url must be /");
for (const size of ["192x192", "512x512"]) {
  const icon = manifest.icons?.find((i) => i.sizes === size && i.type === "image/png");
  if (!icon) fail(`manifest is missing a ${size} PNG icon`);
  else if (!existsSync(join(dist, icon.src.replace(/^\//, "")))) fail(`icon file missing: ${icon.src}`);
}

// 2. Service worker: shell only. API responses (personal data) must never be cached.
const worker = readFileSync(join(dist, "sw.js"), "utf8");
if (/\/api\/v1/.test(worker.replace(/navigateFallbackDenylist[^\]]*\]/, ""))) {
  fail("service worker mentions /api/v1 outside the navigation deny-list");
}
if (!/\/\^\\\/api\\\//.test(worker) && !worker.includes("api")) {
  fail("service worker must deny navigation fallback for /api/");
}
if (/runtimeCaching|StaleWhileRevalidate|CacheFirst|NetworkFirst/.test(worker)) {
  fail("service worker must not define runtime caching");
}

// 3. HTML: nothing inline, so a strict CSP (script-src 'self'; style-src 'self') works.
const html = readFileSync(join(dist, "index.html"), "utf8");
if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(html)) fail("index.html contains an inline <script>");
if (/<style[\s>]/i.test(html)) fail("index.html contains an inline <style>");
if (/\sstyle=/i.test(html)) fail("index.html contains an inline style attribute");
if (/\son[a-z]+=/i.test(html)) fail("index.html contains an inline event handler");

// 4. Bundles must not carry anything that looks like a server credential.
const assets = readdirSync(join(dist, "assets")).filter((f) => f.endsWith(".js"));
for (const file of assets) {
  const code = readFileSync(join(dist, "assets", file), "utf8");
  if (/sk-[A-Za-z0-9]{20,}|BEGIN (RSA |EC )?PRIVATE KEY|AKIA[0-9A-Z]{16}/.test(code)) {
    fail(`${file} contains something that looks like a credential`);
  }
}

if (problems.length > 0) {
  console.error("Build check failed:\n- " + problems.join("\n- "));
  process.exit(1);
}
console.log("Build check passed.");
