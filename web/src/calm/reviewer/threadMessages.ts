/** Messages are immutable and append-only; an older read cannot revoke a send or read receipt. */
import type { Message } from "../../api/accounts";

export function mergeThreadMessages(previous: Message[] | null, incoming: Message[] | null): Message[] | null {
  if (incoming === null) return previous;
  // The server's append order breaks timestamp ties. Locally acknowledged messages absent from
  // that snapshot follow it, and sort into their proper chronological position below.
  const messages = new Map(incoming.map(message => [message.id, message]));
  for (const acknowledged of previous ?? []) {
    const saved = messages.get(acknowledged.id);
    messages.set(acknowledged.id, saved
      ? { ...saved, read_by_me: saved.read_by_me || acknowledged.read_by_me }
      : acknowledged);
  }
  return [...messages.values()].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
}
