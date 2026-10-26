// Renders the app icons from the Batatis mark's own CSS (web/src/calm/calm.css .cf-mark) on a white tile.
// Run: npx electron scripts/make-icons.cjs  → assets/icon-mac.png, assets/icon-win.png (1024 × 1024).
const { app, BrowserWindow } = require("electron");
const { mkdirSync, mkdtempSync, writeFileSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

app.commandLine.appendSwitch("force-device-scale-factor", "1");
app.disableHardwareAcceleration();
// Each icon renders in its own window; closing the first must not quit before the second.
app.on("window-all-closed", () => {});

const SIZE = 1024;
const MARK = "radial-gradient(circle at 35% 30%, #ffa27a, #f25a2a 55%, #c63f12)";

/** `inset`: space around the white tile; macOS draws icons on Apple's 824-pixel tile inside a 1024 canvas. */
function page({ inset, radius, shadow }) {
  const tile = SIZE - 2 * inset;
  const mark = Math.round(tile * 0.4);
  const corner = (n) => `${((n / 24) * mark).toFixed(1)}px`;
  return `<!doctype html><html><body style="margin:0;width:${SIZE}px;height:${SIZE}px;background:transparent;display:grid;place-items:center">
    <div style="width:${tile}px;height:${tile}px;border-radius:${radius}px;background:#fff;display:grid;place-items:center;
      box-shadow:${shadow ? "0 10px 28px rgba(17,24,39,0.16), 0 0 0 1px rgba(17,24,39,0.06)" : "0 0 0 2px rgba(17,24,39,0.07) inset"}">
      <div style="width:${mark}px;height:${mark}px;border-radius:${corner(8)} ${corner(12)} ${corner(9)} ${corner(13)};background:${MARK}"></div>
    </div></body></html>`;
}

async function render(html, file) {
  const window = new BrowserWindow({ width: SIZE, height: SIZE, show: false, transparent: true, frame: false, useContentSize: true,
    webPreferences: { offscreen: true, javascript: false } });
  const source = join(mkdtempSync(join(tmpdir(), "batatis-icon-")), "icon.html");
  writeFileSync(source, html);
  await window.loadFile(source);
  await new Promise((done) => setTimeout(done, 300));
  const image = await window.webContents.capturePage({ x: 0, y: 0, width: SIZE, height: SIZE });
  writeFileSync(file, image.resize({ width: SIZE, height: SIZE, quality: "best" }).toPNG());
  window.destroy();
}

app.whenReady().then(async () => {
  const out = join(__dirname, "..", "assets");
  mkdirSync(out, { recursive: true });
  await render(page({ inset: 100, radius: 186, shadow: true }), join(out, "icon-mac.png"));
  await render(page({ inset: 40, radius: 200, shadow: false }), join(out, "icon-win.png"));
  app.quit();
});
