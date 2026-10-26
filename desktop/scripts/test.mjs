import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";

const files = readdirSync("tests").filter((name) => name.endsWith(".test.ts")).sort().map((name) => `tests/${name}`);
const result = spawnSync(process.execPath, ["--experimental-strip-types", "--disable-warning=MODULE_TYPELESS_PACKAGE_JSON", "--import", "./scripts/register-ts.mjs", "--test", ...files], { stdio: "inherit" });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
