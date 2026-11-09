import { useEffect, useRef, useState } from "react";
import {
  getAgentStatus,
  requestProposal,
  synthesizeExplanation,
  transcribeAudio,
  updatePatch,
  type Patch,
  type PatchActionResult,
  type TestRun,
} from "./api";

const audioTypes = ["audio/wav", "audio/mpeg", "audio/ogg", "audio/flac", "audio/aac", "audio/mp4"];

async function makeWav(blob: Blob): Promise<Blob> {
  const context = new AudioContext();
  try {
    const buffer = await context.decodeAudioData(await blob.arrayBuffer());
    const sampleRate = 44100;
    const channels = 1;
    const frames = Math.ceil(buffer.length * sampleRate / buffer.sampleRate);
    const pcm = new ArrayBuffer(44 + frames * channels * 2);
    const view = new DataView(pcm);
    const write = (offset: number, value: string) => {
      for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
    };
    write(0, "RIFF");
    view.setUint32(4, pcm.byteLength - 8, true);
    write(8, "WAVE");
    write(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * channels * 2, true);
    view.setUint16(32, channels * 2, true);
    view.setUint16(34, 16, true);
    write(36, "data");
    view.setUint32(40, frames * channels * 2, true);
    const source = Array.from({ length: buffer.numberOfChannels }, (_, i) => buffer.getChannelData(i));
    let offset = 44;
    for (let frame = 0; frame < frames; frame++) {
      const sourceFrame = frame * buffer.sampleRate / sampleRate;
      const lower = Math.floor(sourceFrame);
      const upper = Math.min(lower + 1, buffer.length - 1);
      const fraction = sourceFrame - lower;
      const mixed = source.reduce((sum, channel) => {
        const sample = channel[lower] * (1 - fraction) + channel[upper] * fraction;
        return sum + sample / source.length;
      }, 0);
      const value = Math.max(-1, Math.min(1, mixed));
      view.setInt16(offset, value < 0 ? value * 0x8000 : value * 0x7fff, true);
      offset += 2;
    }
    return new Blob([pcm], { type: "audio/wav" });
  } finally {
    await context.close();
  }
}

export default function App() {
  const [instruction, setInstruction] = useState("");
  const [transcript, setTranscript] = useState("");
  const [patch, setPatch] = useState<Patch | null>(null);
  const [tests, setTests] = useState<TestRun | null>(null);
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [agentStatus, setAgentStatus] = useState<"checking" | "available" | "unavailable" | "offline">("checking");
  const [agentDetail, setAgentDetail] = useState("");
  const [audioSource, setAudioSource] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const audioUrl = useRef<string | null>(null);
  const recordingTimeout = useRef<number | null>(null);

  useEffect(() => {
    void getAgentStatus()
      .then((data) => {
        setAgentStatus(data.available ? "available" : "unavailable");
        setAgentDetail(data.detail ?? "");
      })
      .catch(() => {
        setAgentStatus("offline");
        setAgentDetail("Could not check the local Gemma runtime.");
      });
    return () => {
      if (recordingTimeout.current !== null) window.clearTimeout(recordingTimeout.current);
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    };
  }, []);

  async function transcribe(file: File | Blob, filename: string) {
    setWorking("Transcribing with Prisma…");
    setError("");
    try {
      const data = await transcribeAudio(file, filename);
      setTranscript(data.transcript);
      setInstruction(data.transcript);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Transcription failed");
    } finally {
      setWorking("");
    }
  }

  async function toggleRecording() {
    setError("");
    if (recording) {
      if (recordingTimeout.current !== null) window.clearTimeout(recordingTimeout.current);
      recorder.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      recorder.current = mediaRecorder;
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        void makeWav(new Blob(chunks.current, { type: mediaRecorder.mimeType }))
          .then((wav) => transcribe(wav, "recording.wav"))
          .catch(() => setError("This browser could not decode the recording; upload a WAV, MP3, OGG, FLAC, AAC, or M4A file."));
      };
      mediaRecorder.start();
      setRecording(true);
      recordingTimeout.current = window.setTimeout(() => {
        if (mediaRecorder.state === "recording") {
          mediaRecorder.stop();
          setRecording(false);
        }
      }, 30_000);
    } catch {
      setError("Microphone access is unavailable. Use the audio upload option instead.");
    }
  }

  async function propose() {
    setWorking("Asking Gemma 4 for a proposal…");
    setError("");
    setPatch(null);
    setTests(null);
    try {
      setPatch(await requestProposal(instruction));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Proposal failed");
    } finally {
      setWorking("");
    }
  }

  async function patchAction(action: "approve" | "reject" | "rollback") {
    if (!patch) return;
    setWorking(action === "approve" ? "Applying approved patch and running tests…" : `${action}ing patch…`);
    setError("");
    try {
      const data: PatchActionResult = await updatePatch(patch.patch_id, action);
      if ("patch" in data) {
        setPatch(data.patch);
        setTests(data.tests);
      } else {
        setPatch(data);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Patch action failed");
    } finally {
      setWorking("");
    }
  }

  async function speakExplanation() {
    if (!patch) return;
    setWorking("Generating speech with Timbre…");
    setError("");
    try {
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      audioUrl.current = URL.createObjectURL(
        await synthesizeExplanation(patch.explanation || patch.summary),
      );
      setAudioSource(audioUrl.current);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Speech synthesis failed");
    } finally {
      setWorking("");
    }
  }

  const audioElement = audioSource ? <audio controls src={audioSource} /> : null;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">GEMMA 4 · GNANI AI</div>
          <h1>Voice2Code</h1>
          <p>Speak an instruction. Review every change before it touches your files.</p>
        </div>
        <div className="runtime-status">
          <span className={`status ${agentStatus === "available" ? "ready" : "pending"}`}>
            {agentStatus === "checking" ? "Checking Gemma…" : agentStatus === "available" ? "Gemma 4 installed" : agentStatus === "offline" ? "Backend unavailable" : "Gemma 4 unavailable"}
          </span>
          {agentDetail && <p className="runtime-detail">{agentDetail}</p>}
        </div>
      </header>

      <section className="panel">
        <div className="section-title"><span className="step">01</span><div><h2>Give an instruction</h2><p>Hindi, Hinglish, or English · Prisma supports clips up to 30 seconds</p></div></div>
        <div className="controls">
          <button className={recording ? "button danger" : "button"} disabled={Boolean(working) && !recording} onClick={() => void toggleRecording()}>{recording ? "Stop recording" : "Record voice"}</button>
          <label className="button secondary upload">Upload audio<input type="file" disabled={Boolean(working)} accept={audioTypes.join(",")} onChange={(event) => { const file = event.target.files?.[0]; if (file) void transcribe(file, file.name); }} /></label>
        </div>
        {transcript && <div className="transcript"><span>Prisma transcript</span><p>{transcript}</p></div>}
        <label className="field-label" htmlFor="instruction">Instruction</label>
        <textarea id="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="उदाहरण: इस फ़ंक्शन के लिए एक unit test जोड़ें…" rows={4} maxLength={10000} />
        <div className="actions"><button className="button primary" disabled={!instruction.trim() || Boolean(working)} onClick={() => void propose()}>Generate proposal</button></div>
      </section>

      {patch && <section className="panel">
        <div className="section-title"><span className="step">02</span><div><h2>Proposed patch</h2><p>{patch.summary} · {patch.status}</p></div></div>
        <p className="explanation">{patch.explanation}</p>
        <pre className="diff"><code>{patch.diff}</code></pre>
        <div className="actions">
          {patch.status === "proposed" && <>
            <button className="button primary" disabled={Boolean(working)} onClick={() => void patchAction("approve")}>Approve and apply</button>
            <button className="button secondary" disabled={Boolean(working)} onClick={() => void patchAction("reject")}>Reject</button>
          </>}
          {patch.status === "applied" && <button className="button secondary" disabled={Boolean(working)} onClick={() => void patchAction("rollback")}>Roll back</button>}
          <button className="button secondary" disabled={Boolean(working)} onClick={() => void speakExplanation()}>Speak explanation</button>
          {audioElement}
        </div>
      </section>}

      {tests && <section className="panel">
        <div className="section-title"><span className="step">03</span><div><h2>Test run</h2><p>{tests.timed_out ? "Timed out" : tests.exit_code === 0 ? "Passed" : `Failed (exit ${tests.exit_code ?? "unknown"})`}</p></div></div>
        <pre className="output"><code>{tests.output || "No output"}</code></pre>
      </section>}

      {working && <p className="working" role="status">{working}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {agentStatus === "unavailable" && <p className="notice">The local competition-harness adapter is unavailable. Prisma transcription and Timbre synthesis need a configured Gnani API key; proposal generation additionally needs a callable Gemma runtime.</p>}
      {agentStatus === "offline" && <p className="notice">The backend is not reachable. Start FastAPI and verify its CORS configuration.</p>}
      <footer>Local development interface · Patch approval is required before file writes</footer>
    </main>
  );
}
