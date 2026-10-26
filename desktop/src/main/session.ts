import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

/**
 * The Batatis session cookie, held by the host and never by a renderer. Every forwarded request carries
 * the epoch it was sent in; a Set-Cookie from an older epoch (a late answer after a switch) is ignored.
 */

export const COOKIE = "batatis_session";
const TOKEN = /^[A-Za-z0-9_-]{43}$/;

export interface TokenStore {
  save(token: string | null): Promise<void>;
}

export class SessionJar {
  #token: string | null;
  #epoch = 0;
  #store: TokenStore | null;

  constructor(token: string | null = null, store: TokenStore | null = null) {
    this.#token = token !== null && TOKEN.test(token) ? token : null;
    this.#store = store;
  }

  get epoch(): number {
    return this.#epoch;
  }

  get token(): string | null {
    return this.#token;
  }

  cookieHeader(): string | null {
    return this.#token ? `${COOKIE}=${this.#token}` : null;
  }

  /** Apply the engine's Set-Cookie headers for a request sent in `epoch`; resolves once a change is stored. */
  async apply(setCookies: readonly string[], epoch: number): Promise<void> {
    if (epoch !== this.#epoch) return;
    for (const header of setCookies) {
      const next = sessionFrom(header);
      if (next === undefined || next === this.#token) continue;
      this.#token = next;
      await this.#store?.save(next);
    }
  }

  /** A new person or workspace: later answers to earlier requests can no longer change the session. */
  replace(token: string | null): void {
    this.#epoch += 1;
    this.#token = token !== null && TOKEN.test(token) ? token : null;
  }
}

/** The session value a Set-Cookie header sets: a token, null when it clears it, undefined when unrelated. */
export function sessionFrom(header: string): string | null | undefined {
  const [pair, ...attributes] = header.split(";");
  const at = pair.indexOf("=");
  if (at < 0 || pair.slice(0, at).trim() !== COOKIE) return undefined;
  const value = pair.slice(at + 1).trim().replace(/^"(.*)"$/, "$1");
  const cleared = attributes.some((attribute) => {
    const [name, raw = ""] = attribute.split("=");
    const key = name.trim().toLowerCase();
    return (key === "max-age" && Number(raw.trim()) <= 0) || (key === "expires" && Date.parse(raw.trim()) <= Date.now());
  });
  if (cleared || value === "") return null;
  return TOKEN.test(value) ? value : undefined;
}

export interface SessionBox {
  available(): Promise<boolean>;
  encrypt(plain: string): Promise<Buffer>;
  decrypt(sealed: Buffer): Promise<string>;
}

/** The normal workspace's cookie survives a restart only when the OS can encrypt it; otherwise it is kept in memory. */
export class SealedTokenStore implements TokenStore {
  #file: string;
  #box: SessionBox;

  constructor(file: string, box: SessionBox) {
    this.#file = file;
    this.#box = box;
  }

  async load(): Promise<string | null> {
    try {
      const sealed = await readFile(this.#file);
      if (!(await this.#box.available())) return null;
      const token = await this.#box.decrypt(sealed);
      return TOKEN.test(token) ? token : null;
    } catch {
      return null;
    }
  }

  async save(token: string | null): Promise<void> {
    if (token === null || !(await this.#box.available())) {
      await rm(this.#file, { force: true });
      return;
    }
    await mkdir(dirname(this.#file), { recursive: true, mode: 0o700 });
    await writeFile(`${this.#file}.partial`, await this.#box.encrypt(token), { mode: 0o600 });
    await rename(`${this.#file}.partial`, this.#file);
  }
}
