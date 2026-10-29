// Drives the stage harness. Server: `npx vite --port 5182 --strictPort` from web/.
//   node drive.mjs stills      every slide of the real deck, plus intro and outro, one PNG each (manual clock)
//   node drive.mjs transition  frames across one slide dissolve and one group dissolve, and the intro reveal
//   node drive.mjs export      export the first two groups of the test deck with fake takes
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
const require = createRequire("/Users/aamia/.t3/worktrees/batatis/demo-video-tools/package.json");
const { chromium } = require("playwright-core");
const OUT = process.env.OUT ?? "/tmp/stagework/out";
const PORT = process.env.PORT ?? "5182";
const mode = process.argv[2] ?? "stills";
mkdirSync(`${OUT}/${mode}`, { recursive: true });
const exe = `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`;
const browser = await chromium.launch({
  executablePath: exe,
  args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
});
const page = await browser.newPage({ viewport: { width: 1100, height: 700 } });
page.on("console", (m) => console.log("[page]", m.text()));
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
const query = mode === "export" ? "" : "?deck=real&clock=manual";
await page.goto(`http://127.0.0.1:${PORT}/src/studio/stage/harness/index.html${query}`);
await page.waitForFunction(() => window.H);
await page.evaluate(() => window.H.ready);
const save = async (name) => {
  const url = await page.evaluate(() => window.H.frame());
  writeFileSync(`${OUT}/${mode}/${name}.png`, Buffer.from(url.split(",")[1], "base64"));
};
const step = (ms) => page.evaluate((ms) => window.H.step(ms), ms);
const wait = (ms) => page.waitForTimeout(ms);

if (mode === "stills") {
  console.log("stand-ins:", JSON.stringify(await page.evaluate(() => window.H.standIns)));
  await page.evaluate(() => window.H.camera(true));
  await page.evaluate(() => window.H.card("intro"));
  await step(5000); await save("00-intro");
  const slides = await page.evaluate(() => window.H.slides);
  let n = 1;
  for (const [g, ids] of slides.entries())
    for (const [s, id] of ids.entries()) {
      await page.evaluate(([g, s]) => window.H.show(g, s, true), [g, s]);
      // Let a clip decode and play a moment so the still shows a real frame.
      await wait(id.startsWith("apply") || id.startsWith("officer") ? 1500 : 150);
      await step(16);
      await save(`${String(n++).padStart(2, "0")}-${id}`);
    }
  await page.evaluate(() => window.H.camera(false));
  await page.evaluate(() => window.H.card("outro"));
  await step(5000); await save(`${String(n).padStart(2, "0")}-outro`);
}

if (mode === "transition") {
  // Intro reveal, from a blank stage as in the export.
  await page.evaluate(() => window.H.card("intro"));
  for (const [i, ms] of [0, 300, 300, 300, 400, 500, 600].entries()) { await step(ms); await save(`intro-${i}`); }
  await page.evaluate(() => window.H.camera(true));
  // In-group: "Spot the difference" (compare) to "More information required." (statement); 450 ms.
  await page.evaluate(() => window.H.show(1, 0, true));
  await step(100);
  await page.evaluate(() => window.H.show(1, 1));
  for (const [i, ms] of [0, 112, 113, 113, 112].entries()) { await step(ms); await save(`slide-${i}-${[0, 112, 225, 338, 450][i]}ms`); }
  // Clip to clip with a changed title (frame holds, title rises); 450 ms.
  await page.evaluate(() => window.H.show(2, 0, true));
  await wait(1200); await step(16);
  await page.evaluate(() => window.H.show(2, 1));
  for (const [i, ms] of [0, 112, 113, 113, 112].entries()) { await step(ms); await save(`clip-${i}-${[0, 112, 225, 338, 450][i]}ms`); }
  // Group: last open slide (count) into the villain compare; 700 ms.
  await page.evaluate(() => window.H.show(0, 2, true));
  await step(16);
  await page.evaluate(() => window.H.show(1, 0));
  for (const [i, ms] of [0, 175, 175, 175, 175].entries()) { await step(ms); await save(`group-${i}-${[0, 175, 350, 525, 700][i]}ms`); }
}

if (mode === "export") {
  const res = await page.evaluate(() => window.H.export());
  const progress = await page.evaluate(() => window.H.progress);
  console.log("progress samples", progress.length, "last", JSON.stringify(progress.at(-1)));
  if (res.b64) {
    const ext = res.mime.includes("mp4") ? "mp4" : "webm";
    writeFileSync(`${OUT}/export/export.${ext}`, Buffer.from(res.b64, "base64"));
    console.log("export", { mime: res.mime, size: res.size, wallMs: Math.round(res.wallMs) }, `${OUT}/export/export.${ext}`);
  } else console.log("export result", res);
}
await browser.close();
