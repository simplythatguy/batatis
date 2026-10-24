import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

function tests(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? tests(path) : entry.name.endsWith('.test.ts') ? [path] : [];
  });
}

const result = spawnSync(process.execPath, [
  '--experimental-strip-types', '--import', './scripts/register-ts.mjs', '--test', ...tests('src').sort(),
], { stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
