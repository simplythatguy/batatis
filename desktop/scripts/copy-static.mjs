import { cpSync, rmSync } from "node:fs";

rmSync("dist/static", { recursive: true, force: true });
cpSync("static", "dist/static", { recursive: true });
