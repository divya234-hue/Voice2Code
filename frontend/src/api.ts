const API = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type Patch = {
  patch_id: string;
  summary: string;
  explanation: string;
  status: string;
  diff: string;
  files: string[];
};

export type TestRun = {
  run_id: string;
  exit_code: number | null;
  output: string;
  timed_out: boolean;
};

export type AgentStatus = {
  available: boolean;
  detail?: string;
};

export type PatchActionResult = Patch | { patch: Patch; tests: TestRun };
type ApiError = { error?: { message?: string }; detail?: string };

async function errorMessage(response: Response): Promise<string> {
  const body = (await response.json().catch(() => ({}))) as ApiError;
  return body.error?.message ?? body.detail ?? `Request failed (${response.status})`;
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as T;
}

export function getAgentStatus(): Promise<AgentStatus> {
  return jsonRequest(`${API}/api/v1/coding/status`);
}

export async function transcribeAudio(
  file: File | Blob,
  filename: string,
): Promise<{ transcript: string }> {
  const form = new FormData();
  form.append("audio_file", file, filename);
  form.append("language_code", "indic-auto");
  return jsonRequest(`${API}/api/v1/voice/transcribe`, {
    method: "POST",
    body: form,
  });
}

export function requestProposal(instruction: string): Promise<Patch> {
  return jsonRequest(`${API}/api/v1/coding/proposals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });
}

export function updatePatch(
  patchId: string,
  action: "approve" | "reject" | "rollback",
): Promise<PatchActionResult> {
  return jsonRequest(
    `${API}/api/v1/coding/patches/${patchId}/${action}`,
    { method: "POST" },
  );
}

export async function synthesizeExplanation(text: string): Promise<Blob> {
  const response = await fetch(`${API}/api/v1/voice/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      model: "timbre-v2.5",
      voice: "Nalini",
      language: "hi-IN",
    }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.blob();
}
