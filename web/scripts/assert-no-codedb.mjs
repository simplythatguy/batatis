/**
 * After `vite build`, the sqlite must not be a file in dist/, and the three
 * public paths must 404. vercel.json routes are applied, not only read:
 * a planted copy of the database still has to 404.
 */
import { createServer } from "node:http";
import { readFileSync, existsSync, readdirSync, statSync, mkdirSync, cpSync, writeFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const dist = join(root, "web", "dist");
const paths = ["/codedb.sqlite", "/codedb/build/codedb.sqlite", "/api/codedb/build/codedb.sqlite"];
const marker = "SQLite format 3";

if (!existsSync(join(dist, "index.html"))) {
  console.error("web/dist/index.html is missing; run the web build first");
  process.exit(1);
}

function walk(dir, found) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (name === "codedb.sqlite") found.push(path);
    if (statSync(path).isDirectory()) walk(path, found);
  }
  return found;
}

const leaked = walk(dist, []);
if (leaked.length) {
  console.error("codedb.sqlite is in the web build:", leaked.join(", "));
  process.exit(1);
}

const config = JSON.parse(readFileSync(join(root, "vercel.json"), "utf8"));
const routes = config.routes || [];

function statusFor(urlPath) {
  for (const route of routes) {
    if (route.src && new RegExp(route.src).test(urlPath)) {
      if (route.continue) continue;
      return route.status ?? 200;
    }
  }
  return null;
}

for (const urlPath of paths) {
  if (statusFor(urlPath) !== 404) {
    console.error(`vercel.json does not 404 ${urlPath}`);
    process.exit(1);
  }
}

const planted = join(root, "web", ".tmp-codedb-check");
rmSync(planted, { recursive: true, force: true });
mkdirSync(planted, { recursive: true });
cpSync(dist, planted, { recursive: true });
for (const urlPath of paths) {
  const file = join(planted, urlPath);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, marker);
}

function bodyFor(urlPath, rootDir) {
  const routed = statusFor(urlPath);
  if (routed === 404) return { status: 404, body: "not found" };
  const file = join(rootDir, urlPath);
  if (existsSync(file) && statSync(file).isFile()) {
    return { status: 200, body: readFileSync(file, "utf8") };
  }
  return { status: 404, body: "missing" };
}

const server = createServer((req, res) => {
  const result = bodyFor(req.url.split("?")[0], planted);
  res.writeHead(result.status, { "content-type": "text/plain" });
  res.end(result.body);
});

await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
const port = server.address().port;
try {
  for (const urlPath of paths) {
    const response = await fetch(`http://127.0.0.1:${port}${urlPath}`);
    const text = await response.text();
    if (response.status !== 404 || text.includes(marker)) {
      console.error(`${urlPath} served the code database`, response.status, text.slice(0, 40));
      process.exit(1);
    }
  }
} finally {
  server.close();
  rmSync(planted, { recursive: true, force: true });
}

function jsFiles(dir, found = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) jsFiles(path, found);
    else if (name.endsWith(".js")) found.push(path);
  }
  return found;
}

const chrome = readFileSync(join(dist, "index.html"), "utf8") + jsFiles(dist).map((path) => readFileSync(path, "utf8")).join("\n");
if (!chrome.includes('name="robots"') || !chrome.includes("noindex, nofollow")) {
  console.error("built index.html is missing the robots noindex tag");
  process.exit(1);
}
for (const banned of ["up to 30 days", "DELETE /cases", "cases stay until deleted"]) {
  if (chrome.includes(banned)) {
    console.error("built web output still contains notice copy:", banned);
    process.exit(1);
  }
}

console.log("codedb paths 404; robots noindex is in the build");
