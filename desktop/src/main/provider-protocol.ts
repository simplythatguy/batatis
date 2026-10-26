/** The main protocol owns request cancellation; provider signals never depend on Python thread locals. */
export function withProviderCancellation(forward: (request: Request) => Promise<Response>, cancel: (kind: "identity" | "request") => void) {
  return async (request: Request): Promise<Response> => {
    const path = new URL(request.url).pathname;
    if (/^\/api\/auth\/(?:logout|login|signup|oauth)/.test(path)) cancel("identity");
    const ownsAI = /^\/api\/(?:assist|cases\/[^/]+\/(?:intake|identify|relevance))$/.test(path);
    if (!ownsAI) return forward(request);
    const abort = () => cancel("request");
    if (request.signal.aborted) cancel("request");
    request.signal.addEventListener("abort", abort, { once: true });
    const detach = () => request.signal.removeEventListener("abort", abort);
    try {
      const response = await forward(request);
      if (!response.body) { detach(); return response; }
      const reader = response.body.getReader();
      const body = new ReadableStream<Uint8Array>({
        async pull(controller) {
          try {
            const next = await reader.read();
            if (next.done) { detach(); controller.close(); }
            else controller.enqueue(next.value);
          } catch (error) { detach(); controller.error(error); }
        },
        async cancel() { detach(); cancel("request"); await reader.cancel(); },
      });
      return new Response(body, { status: response.status, headers: response.headers });
    } catch (error) { detach(); throw error; }
  };
}
