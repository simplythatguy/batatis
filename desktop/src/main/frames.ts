/** batatis.bridge.v1 frames (engine/desktop/bridge.py): u32 BE header length, u32 BE body length, JSON, bytes. */

export const MAX_HEADER = 64 * 1024;
export const MAX_BODY = 256 * 1024;
const PREFIX = 8;
const EMPTY = new Uint8Array(0);

export type FrameHeader = { readonly t: string } & Record<string, unknown>;
export interface Frame {
  header: FrameHeader;
  body: Uint8Array;
}

export class FrameError extends Error {}

export function encodeFrame(header: { t: string } & Record<string, unknown>, body: Uint8Array = EMPTY): Buffer {
  const raw = Buffer.from(JSON.stringify(header), "utf8");
  if (raw.length > MAX_HEADER || body.length > MAX_BODY) throw new FrameError("frame too large");
  const prefix = Buffer.alloc(PREFIX);
  prefix.writeUInt32BE(raw.length, 0);
  prefix.writeUInt32BE(body.length, 4);
  return Buffer.concat([prefix, raw, body]);
}

/** Splits a body into frame-sized chunks; an empty body is one empty chunk. */
export function chunks(body: Uint8Array): Uint8Array[] {
  if (body.length === 0) return [EMPTY];
  const out: Uint8Array[] = [];
  for (let offset = 0; offset < body.length; offset += MAX_BODY) out.push(body.subarray(offset, offset + MAX_BODY));
  return out;
}

/** Incremental decoder for a pipe: feed arbitrary chunks, get whole frames. Throws FrameError on a bad frame. */
export class FrameDecoder {
  #buffer: Buffer = Buffer.alloc(0);

  push(chunk: Uint8Array): Frame[] {
    this.#buffer = this.#buffer.length ? Buffer.concat([this.#buffer, chunk]) : Buffer.from(chunk);
    const frames: Frame[] = [];
    while (this.#buffer.length >= PREFIX) {
      const headerLength = this.#buffer.readUInt32BE(0);
      const bodyLength = this.#buffer.readUInt32BE(4);
      if (headerLength === 0 || headerLength > MAX_HEADER || bodyLength > MAX_BODY) throw new FrameError("frame too large");
      const total = PREFIX + headerLength + bodyLength;
      if (this.#buffer.length < total) break;
      const header = parseHeader(this.#buffer.subarray(PREFIX, PREFIX + headerLength));
      const body = Uint8Array.prototype.slice.call(this.#buffer, PREFIX + headerLength, total);
      frames.push({ header, body });
      this.#buffer = this.#buffer.subarray(total);
    }
    return frames;
  }

  get buffered(): number {
    return this.#buffer.length;
  }
}

function parseHeader(raw: Uint8Array): FrameHeader {
  let value: unknown;
  try {
    value = JSON.parse(Buffer.from(raw).toString("utf8"));
  } catch {
    throw new FrameError("header is not JSON");
  }
  if (!isHeader(value)) throw new FrameError("header has no type");
  return value;
}

function isHeader(value: unknown): value is FrameHeader {
  return typeof value === "object" && value !== null && !Array.isArray(value) && "t" in value && typeof value.t === "string";
}
