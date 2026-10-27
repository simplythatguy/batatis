// Stands in for the OpenCode executable: `node fake-opencode.cjs <control.json> run ...` prints the
// events the control file asks for after recording how it was started.
const { appendFileSync, readFileSync } = require("node:fs");
const control = JSON.parse(readFileSync(process.argv[2], "utf8"));
appendFileSync(control.capture, `${JSON.stringify({ pid: process.pid, cwd: process.cwd(), args: process.argv.slice(3), config: process.env.OPENCODE_CONFIG_CONTENT, env: process.env })}\n`);
const mode = control.completion ?? {};
if (mode.kind === "hang") setInterval(() => {}, 1000);
else {
  for (const event of mode.events ?? []) process.stdout.write(`${JSON.stringify(event)}\n`);
  process.exit(mode.exitCode ?? 0);
}
