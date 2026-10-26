// A scripted stand-in for the Claude Code CLI. argv: <control.json> <claude args...>. The control file names
// the capture log, the sign-in state file and how login and completions behave.
const fs = require("node:fs");

const [control, ...args] = process.argv.slice(2);
const mode = JSON.parse(fs.readFileSync(control, "utf8"));
const record = (entry) => fs.appendFileSync(mode.capture, `${JSON.stringify({ pid: process.pid, cwd: process.cwd(), args, ...entry })}\n`);
const state = () => JSON.parse(fs.readFileSync(mode.state, "utf8"));
const save = (next) => fs.writeFileSync(mode.state, JSON.stringify(next));
const hang = () => setInterval(() => {}, 1000);

function readInput(done) {
  let input = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => { input += chunk; });
  process.stdin.on("end", () => done(input));
}

if (args[0] === "auth" && args[1] === "status") {
  record({ env: process.env });
  const { loggedIn, authMethod } = state();
  process.stdout.write(`${JSON.stringify({ loggedIn, authMethod, apiProvider: "firstParty" }, null, 2)}\n`);
  process.exitCode = loggedIn ? 0 : 1;
} else if (args[0] === "auth" && args[1] === "login") {
  record({ env: process.env });
  const login = mode.login ?? {};
  process.stdout.write("Opening browser to sign in…\n");
  if (login.decoy) process.stdout.write(`See ${login.decoy} for help\n`);
  const show = () => process.stderr.write(`If your browser didn't open automatically, copy this URL manually:\n\x1b[2m${login.url}\x1b[0m\n`);
  if (login.url) setTimeout(show, login.urlDelayMs ?? 0);
  process.stdin.on("end", () => process.exit(1));
  process.stdin.resume();
  if (login.outcome === "success") setTimeout(() => { save({ loggedIn: true, authMethod: "claude.ai" }); process.exit(0); }, login.delayMs ?? 0);
  else if (login.outcome === "fail") setTimeout(() => process.exit(1), login.delayMs ?? 0);
  else hang();
} else if (args[0] === "auth" && args[1] === "logout") {
  record({});
  save({ loggedIn: false, authMethod: "none" });
  process.stdout.write("Successfully logged out from your Anthropic account.\n");
} else if (args[0] === "-p") {
  readInput((input) => {
    record({ env: process.env, stdin: input });
    const completion = mode.completion ?? {};
    if (completion.kind === "hang") return hang();
    process.stdout.write(`${JSON.stringify(completion.output)}\n`);
    process.exitCode = completion.exitCode ?? 0;
  });
} else {
  process.stderr.write(`unexpected arguments: ${args.join(" ")}\n`);
  process.exitCode = 2;
}
