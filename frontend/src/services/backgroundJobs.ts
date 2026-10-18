import { ApiError, request } from "./apiClient";

export type BackgroundJobStatus =
  | "queued"
  | "processing"
  | "succeeded"
  | "failed";

export interface EnqueuedJob {
  job_id: number;
  status: BackgroundJobStatus;
  status_url: string;
}

export interface BackgroundJob<T = unknown> {
  id: number;
  business_id: number;
  job_type: string;
  status: BackgroundJobStatus;
  progress: { step?: string; message?: string } | null;
  progress_version: number;
  result: T | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface PollJobOptions {
  intervalMs?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
  onProgress?: (job: BackgroundJob) => void;
}


export async function getBusinessJob<T = unknown>(
  businessId: number,
  jobId: number,
): Promise<BackgroundJob<T>> {
  const data = await request<{ job: BackgroundJob<T> }>(
    `/businesses/${businessId}/jobs/${jobId}`,
  );
  return data.job;
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("The operation was aborted", "AbortError"));
      return;
    }

    const timeout = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timeout);
      reject(new DOMException("The operation was aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function waitForBusinessJob<T>(
  businessId: number,
  jobId: number,
  options: PollJobOptions = {},
): Promise<T> {
  const intervalMs = options.intervalMs ?? 1000;
  const timeoutMs = options.timeoutMs ?? 120000;
  const startedAt = Date.now();

  for (;;) {
    if (options.signal?.aborted) {
      throw new DOMException("The operation was aborted", "AbortError");
    }
    if (Date.now() - startedAt >= timeoutMs) {
      throw new ApiError(408, "Background job timed out. Check status and try again.");
    }

    const job = await getBusinessJob<T>(businessId, jobId);
    options.onProgress?.(job);

    if (job.status === "succeeded") {
      if (job.result == null) {
        throw new ApiError(500, "Background job completed without a result");
      }
      return job.result;
    }
    if (job.status === "failed") {
      throw new ApiError(500, job.error || "Background job failed");
    }
    if (job.status !== "queued" && job.status !== "processing") {
      throw new ApiError(500, `Unexpected background job status: ${job.status}`);
    }

    await wait(Math.min(intervalMs, Math.max(0, timeoutMs - (Date.now() - startedAt))), options.signal);
  }
}

export async function waitForEnqueuedJob<T>(
  businessId: number,
  accepted: EnqueuedJob,
  options: PollJobOptions = {},
): Promise<T> {
  if (!Number.isInteger(accepted.job_id) || accepted.job_id < 1) {
    throw new ApiError(500, "Server returned an invalid background job ID");
  }
  return waitForBusinessJob<T>(businessId, accepted.job_id, options);
}
