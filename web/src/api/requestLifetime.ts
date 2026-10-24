/** Authenticated responses renew cookies, even when callers ignore their data. */
let accountLifetime = new AbortController();

/** Transports retain their own caller cancellation, deadlines and credentials policy. */
export function accountRequestSignal(parent?: AbortSignal): AbortSignal {
  return parent ? AbortSignal.any([accountLifetime.signal, parent]) : accountLifetime.signal;
}

/** Called synchronously when the account session changes, before subscribers start new work. */
export function replaceAccountRequests() {
  const previous = accountLifetime;
  accountLifetime = new AbortController();
  previous.abort();
}
