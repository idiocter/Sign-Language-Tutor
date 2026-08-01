// Browser Web Speech API wrappers (Phase 4). ASR (speech-in) and TTS (speech-out) run
// entirely in the browser. Nepali voice/recognition support is spotty — every caller must
// keep text input/output working as the fallback (the plan requires it).

const LANG_TAG: Record<string, string> = { en: "en-US", ne: "ne-NP" };

export function speechSupported(): boolean {
  if (typeof window === "undefined") return false;
  return "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
}

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** Speak text. Returns false if no voice could be used (caller shows text instead). */
export function speak(text: string, language: string): boolean {
  if (!ttsSupported() || !text) return false;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = LANG_TAG[language] ?? "en-US";
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find((v) => v.lang?.startsWith(language === "ne" ? "ne" : "en"));
  if (match) u.voice = match;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
  // If asking for Nepali but no ne voice exists, it may fall back silently — report that.
  return language !== "ne" || !!match;
}

/** One-shot speech recognition. Resolves with the transcript, or rejects if unsupported. */
export function listenOnce(language: string): Promise<string> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined") return reject(new Error("no window"));
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Ctor) return reject(new Error("speech recognition unsupported"));
    const rec = new Ctor();
    rec.lang = LANG_TAG[language] ?? "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onresult = (e: any) => resolve(e.results[0][0].transcript as string);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onerror = (e: any) => reject(new Error(e.error || "recognition error"));
    rec.onend = () => {
      /* resolved via onresult, or rejected via onerror */
    };
    rec.start();
  });
}
