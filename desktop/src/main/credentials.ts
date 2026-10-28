/**
 * Provider API keys, encrypted with the OS (Keychain on macOS, DPAPI on Windows) through safeStorage.
 * Fail closed: with no OS encryption nothing is written, and there is no plaintext fallback.
 * Nothing here reads a key back out for a renderer; status is all a window ever learns.
 */
import { randomBytes } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { KeyProviderId } from "./providers";

export interface SecretBox {
  available(): Promise<boolean>;
  encrypt(plain: string): Promise<Buffer>;
  decrypt?(sealed: Buffer): Promise<string>;
}

export type KeyStatus = "missing" | "saved" | "secure-storage-unavailable";
export type SaveOutcome = "saved" | "secure-storage-unavailable" | "invalid";

/** API keys are printable ASCII without spaces; anything else is a paste mistake, not a key. */
export function isPlausibleKey(value: string): boolean {
  return /^[\x21-\x7e]{8,512}$/.test(value);
}

export class KeyVault {
  #dir: string;
  #box: SecretBox;
  #unavailable = false;

  constructor(dir: string, box: SecretBox) {
    this.#dir = dir;
    this.#box = box;
  }

  #file(id: KeyProviderId): string {
    return join(this.#dir, `${id}.key`);
  }

  async status(id: KeyProviderId): Promise<KeyStatus> {
    if (this.#unavailable) return "secure-storage-unavailable";
    try {
      return (await stat(this.#file(id))).isFile() ? "saved" : "missing";
    } catch {
      return "missing";
    }
  }

  async save(id: KeyProviderId, key: string): Promise<SaveOutcome> {
    const value = key.trim();
    if (!isPlausibleKey(value)) return "invalid";
    const partial = `${this.#file(id)}.partial`;
    try {
      if (!(await this.#box.available())) {
        this.#unavailable = true;
        return "secure-storage-unavailable";
      }
      const sealed = await this.#box.encrypt(value);
      await mkdir(this.#dir, { recursive: true, mode: 0o700 });
      await writeFile(partial, sealed, { mode: 0o600 });
      await rename(partial, this.#file(id));
      this.#unavailable = false;
      return "saved";
    } catch {
      this.#unavailable = true;
      await rm(partial, { force: true }).catch(() => {});
      return "secure-storage-unavailable";
    }
  }

  async remove(id: KeyProviderId): Promise<void> {
    await rm(this.#file(id), { force: true });
  }

  /**
   * A random id for this install, made once. It is not a secret: the Batatis website counts the installs that
   * use one access code with it, so a code's seat limit covers desktop installs too.
   */
  async installId(): Promise<string> {
    const file = join(this.#dir, "install.id");
    try {
      const saved = (await readFile(file, "utf8")).trim();
      if (/^[A-Za-z0-9_-]{16,80}$/.test(saved)) return saved;
    } catch { /* made below */ }
    const made = randomBytes(24).toString("base64url");
    await mkdir(this.#dir, { recursive: true, mode: 0o700 });
    await writeFile(file, made, { mode: 0o600 });
    return made;
  }

  /** Main-only use. A missing file returns before touching the OS keyring. */
  async use<T>(id: KeyProviderId, work: (key: string) => Promise<T>): Promise<T | null> {
    let sealed: Buffer;
    try {
      sealed = await readFile(this.#file(id));
    } catch {
      return null;
    }
    let key: string;
    try {
      if (!this.#box.decrypt || !(await this.#box.available())) { this.#unavailable = true; return null; }
      key = await this.#box.decrypt(sealed);
      if (!isPlausibleKey(key)) return null;
      this.#unavailable = false;
    } catch {
      this.#unavailable = true;
      return null;
    } finally {
      sealed.fill(0);
    }
    return work(key);
  }
}
