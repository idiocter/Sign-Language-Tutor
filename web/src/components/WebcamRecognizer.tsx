"use client";

// On-device landmark detection with MediaPipe Tasks (Layer 1). Video never leaves the
// browser — we only ever read hand/face landmarks from the frame.
//
// Recognition (landmarks -> sign) needs a trained model that does not exist yet, so this
// draws detected hand landmarks and reports "not ready". Once an ONNX model is trained,
// buffer normalized frames (see lib/landmarks.ts) and run onnxruntime-web here.

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

const HAND_MODEL = "/models/mediapipe/hand_landmarker.task";
// MediaPipe's wasm runtime. Copy the package's wasm dir into public/mediapipe/wasm for
// offline use, or leave the CDN default for development.
const WASM_BASE =
  process.env.NEXT_PUBLIC_MP_WASM ??
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.20/wasm";

export default function WebcamRecognizer() {
  const t = useTranslations("practice");
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rafRef = useRef<number | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const landmarkerRef = useRef<any>(null);

  async function start() {
    setError(null);
    try {
      const { HandLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const vision = await FilesetResolver.forVisionTasks(WASM_BASE);
      landmarkerRef.current = await HandLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: HAND_MODEL, delegate: "GPU" },
        numHands: 2,
        runningMode: "VIDEO",
      });

      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      const video = videoRef.current!;
      video.srcObject = stream;
      await video.play();
      setRunning(true);
      loop();
    } catch (e) {
      setError(t("modelMissing"));
      // eslint-disable-next-line no-console
      console.error(e);
    }
  }

  function stop() {
    setRunning(false);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    const video = videoRef.current;
    const stream = video?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((tr) => tr.stop());
    if (video) video.srcObject = null;
  }

  function loop() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const lm = landmarkerRef.current;
    if (!video || !canvas || !lm) return;

    const ctx = canvas.getContext("2d")!;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const result = lm.detectForVideo(video, performance.now());
    ctx.fillStyle = "#5b8cff";
    for (const hand of result.landmarks ?? []) {
      for (const pt of hand) {
        ctx.beginPath();
        ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    rafRef.current = requestAnimationFrame(loop);
  }

  useEffect(() => () => stop(), []);

  return (
    <div className="flex flex-col gap-3">
      <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black/40">
        <video ref={videoRef} className="h-full w-full object-cover" playsInline muted />
        <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
        {!running && (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-white/70">
            {t("cameraHint")}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={running ? stop : start}
          className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          {running ? t("stopCamera") : t("startCamera")}
        </button>
        <span className="text-xs text-white/60">{t("notReady")}</span>
      </div>
      {error && <p className="text-sm text-amber-400">{error}</p>}
    </div>
  );
}
