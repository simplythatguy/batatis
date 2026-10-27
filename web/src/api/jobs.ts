import type { Job } from "./types.gen";

export type CaseJob = Job & { kind: "intake" | "identify" };
export const isApplicantJob = (job: Job): job is CaseJob => job.kind === "intake" || job.kind === "identify";

export const activeJob = (job: CaseJob) => job.state === "queued" || job.state === "running";
export const latestJob = (jobs: Job[], kind: CaseJob["kind"]) => jobs.filter(isApplicantJob).filter(job => job.kind === kind).sort((a, b) => b.created_at.localeCompare(a.created_at))[0];

export function jobLabel(job: CaseJob): string {
  switch (job.state) {
    case "queued": return "Queued";
    case "running": return ({ reading: "Reading", preparing: "Preparing", applying: "Applying results", screen: "Screening articles", rerank: "Ranking articles", verify: "Checking references", questions: "Preparing questions" })[job.stage] ?? "Working";
    case "succeeded": return "Completed";
    case "failed": return "Failed";
    case "cancelled": return "Cancelled";
    case "superseded": return "Out of date";
  }
}

/** No overall clock: keep observing the persisted job until it finishes or this view leaves. */
export function observeJob(options: {
  job: CaseJob;
  signal: AbortSignal;
  read: (id: string, signal: AbortSignal) => Promise<Job>;
  change: (job: CaseJob) => void;
  failure: (error: unknown) => void;
  finished: (job: CaseJob) => Promise<void>;
  interval?: number;
}) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;
  const stop = () => { stopped = true; clearTimeout(timer); options.signal.removeEventListener("abort", stop); };
  options.signal.addEventListener("abort", stop, { once: true });
  async function accept(job: Job) {
    if (stopped || options.signal.aborted) return;
    if (!isApplicantJob(job) || job.id !== options.job.id || job.case_id !== options.job.case_id || job.kind !== options.job.kind) {
      options.failure(new Error("The progress response belongs to another application."));
      stop(); return;
    }
    options.change(job);
    if (!activeJob(job)) {
      stop();
      try { await options.finished(job); }
      catch (error) { if (!options.signal.aborted) options.failure(error); }
      return;
    }
    timer = setTimeout(poll, options.interval ?? 1500);
  }
  async function poll() {
    if (stopped || options.signal.aborted) return;
    try { await accept(await options.read(options.job.id, options.signal)); }
    catch (error) {
      if (stopped || options.signal.aborted) return;
      options.failure(error);
      if (!stopped && !options.signal.aborted) timer = setTimeout(poll, options.interval ?? 2500);
    }
  }
  void accept(options.job).catch(options.failure);
  return stop;
}
