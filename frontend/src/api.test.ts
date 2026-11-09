import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getAgentStatus,
  requestProposal,
  synthesizeExplanation,
  transcribeAudio,
  updatePatch,
} from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Voice2Code API integration", () => {
  it("reports local Gemma runtime status from the coding API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ available: false, detail: "Install Gemma 4 first" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAgentStatus()).resolves.toEqual({
      available: false,
      detail: "Install Gemma 4 first",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/coding/status",
      undefined,
    );
  });

  it("sends an audio upload and language selection to Prisma", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ transcript: "Add a test" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const audio = new Blob(["wav-data"], { type: "audio/wav" });

    await expect(transcribeAudio(audio, "recording.wav")).resolves.toEqual({
      transcript: "Add a test",
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/voice/transcribe");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("language_code")).toBe("indic-auto");
    expect((init.body as FormData).get("audio_file")).toBeInstanceOf(File);
  });

  it("submits a coding instruction and returns the proposed patch", async () => {
    const patch = {
      patch_id: "patch-1",
      summary: "Add a test",
      explanation: "The test covers the requested behavior.",
      status: "proposed",
      diff: "+def test_example(): pass",
      files: ["test_example.py"],
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(patch));
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestProposal("Add a test")).resolves.toEqual(patch);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/coding/proposals",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ instruction: "Add a test" }),
      }),
    );
  });

  it("sends an explicit approval and returns its test result", async () => {
    const result = {
      patch: {
        patch_id: "patch-1",
        summary: "Add a test",
        explanation: "Added a test.",
        status: "applied",
        diff: "",
        files: ["test_example.py"],
      },
      tests: { run_id: "run-1", exit_code: 0, output: "1 passed", timed_out: false },
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(result));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updatePatch("patch-1", "approve")).resolves.toEqual(result);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/coding/patches/patch-1/approve",
      { method: "POST" },
    );
  });

  it("returns actual WAV bytes from Timbre", async () => {
    const audio = new Blob(["RIFF"], { type: "audio/wav" });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(audio, { status: 200, headers: { "Content-Type": "audio/wav" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(synthesizeExplanation("Done")).resolves.toBeInstanceOf(Blob);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/v1/voice/synthesize");
    expect(JSON.parse(init.body as string)).toEqual({
      text: "Done",
      model: "timbre-v2.5",
      voice: "Nalini",
      language: "hi-IN",
    });
  });

  it("surfaces API errors without replacing them with a success response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { message: "Gnani API credentials are not configured" } }, 503),
      ),
    );

    await expect(transcribeAudio(new Blob(["audio"]), "sample.wav")).rejects.toThrow(
      "Gnani API credentials are not configured",
    );
  });
});
