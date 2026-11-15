import { useCallback, useRef, useState } from "react";

export const inr = (paise: number): string => `₹${Math.round(paise / 100).toLocaleString("en-IN")}`;

export const CHART = ["#00BAF2", "#002E6E", "#7C5CFC", "#10B981", "#F59E0B", "#F43F5E", "#14B8A6", "#64748B"];

export const compactInr = (rupees: number): string =>
  rupees >= 10_000_000 ? `₹${(rupees / 10_000_000).toFixed(1)}Cr` : rupees >= 100_000 ? `₹${(rupees / 100_000).toFixed(1)}L` : rupees >= 1000 ? `₹${(rupees / 1000).toFixed(rupees >= 10_000 ? 0 : 1)}k` : `₹${Math.round(rupees)}`;

export const LANGS: { code: "hi" | "mr" | "ta" | "en"; label: string }[] = [
  { code: "hi", label: "हिन्दी" },
  { code: "mr", label: "मराठी" },
  { code: "ta", label: "தமிழ்" },
  { code: "en", label: "English" },
];

export const AGENT_LABEL: Record<string, string> = {
  supervisor: "Supervisor", insights: "Insights Agent", khata: "Khata Agent", inventory: "Inventory Agent",
  growth: "Growth Agent", finance: "Finance Agent", trust: "Trust Agent", approval: "Approval Gate", general: "Munim",
};

/** Microphone recorder using MediaRecorder; resolves with the recorded Blob on stop. */
export function useRecorder(): { recording: boolean; start: () => Promise<void>; stop: () => Promise<Blob | null> } {
  const [recording, setRecording] = useState(false);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream);
    chunks.current = [];
    mr.ondataavailable = (e) => chunks.current.push(e.data);
    mr.start();
    rec.current = mr;
    setRecording(true);
  }, []);

  const stop = useCallback(
    () =>
      new Promise<Blob | null>((resolve) => {
        const mr = rec.current;
        if (!mr) return resolve(null);
        mr.onstop = () => {
          mr.stream.getTracks().forEach((t) => t.stop());
          setRecording(false);
          resolve(new Blob(chunks.current, { type: mr.mimeType || "audio/webm" }));
        };
        mr.stop();
      }),
    [],
  );
  return { recording, start, stop };
}
