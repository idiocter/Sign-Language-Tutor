"use client";

// On-device sign recognition with MediaPipe Tasks + onnxruntime-web (Layer 1). Video never
// leaves the browser — we read hand/pose/face landmarks, assemble the same feature vector
// the model was trained on (see lib/landmarks.ts, mirrors capture_tool), buffer a window,
// pool it, and run the recognition model locally.
//
// Needs the three .task models in public/models/mediapipe/ (see that folder's README, or
// `make models`). Without them it degrades to a clear message. Because the interim model is
// trained on synthetic data, live predictions are illustrative until real data is collected.

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { assembleFrame, normalizeFrame, poolMeanStd, SEQ_LEN, type LM } from "@/lib/landmarks";
import { recognize } from "@/lib/recognition";
import { listSigns, type Sign } from "@/lib/api";

const MP = "/models/mediapipe";
const WASM_BASE =
  process.env.NEXT_PUBLIC_MP_WASM ??
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.20/wasm";

const MIN_FRAMES = 30;
const PREDICT_EVERY_MS = 700;

export default function WebcamRecognizer() {
  const t = useTranslations("practice");
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<{ sign: string; conf: number } | null>(null);

  const rafRef = useRef<number | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hand = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pose = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const face = useRef<any>(null);
  const buffer = useRef<Float32Array[]>([]);
  const lastPredict = useRef(0);
  const predicting = useRef(false);
  const labels = useRef<Record<string, Sign>>({});

  useEffect(() => {
    listSigns()
      .then((s) => (labels.current = Object.fromEntries(s.map((x) => [x.sign_id, x]))))
      .catch(() => {});
  }, []);

  async function start() {
    setError(null);
    setPrediction(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let mp: any;
    try {
      mp = await import("@mediapipe/tasks-vision");
    } catch {
      setError(t("libFailed"));
      return;
    }
    try {
      const vision = await mp.FilesetResolver.forVisionTasks(WASM_BASE);
      // Each landmarker is optional — recognition still runs (degraded) if one is missing.
      hand.current = await mp.HandLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: `${MP}/hand_landmarker.task`, delegate: "GPU" },
        numHands: 2,
        runningMode: "VIDEO",
      }).catch(() => null);
      pose.current = await mp.PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: `${MP}/pose_landmarker.task`, delegate: "GPU" },
        numPoses: 1,
        runningMode: "VIDEO",
      }).catch(() => null);
      face.current = await mp.FaceLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: `${MP}/face_landmarker.task`, delegate: "GPU" },
        numFaces: 1,
        runningMode: "VIDEO",
      }).catch(() => null);

      if (!hand.current && !pose.current) {
        setError(t("modelMissing"));
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      const video = videoRef.current!;
      video.srcObject = stream;
      await video.play();
      buffer.current = [];
      setRunning(true);
      loop();
    } catch (e) {
      setError(t("modelMissing"));
      // eslint-disable-next-line no-console
      console.warn("[WebcamRecognizer] could not start:", e);
    }
  }

  function stop() {
    setRunning(false);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    const video = videoRef.current;
    (video?.srcObject as MediaStream | null)?.getTracks().forEach((tr) => tr.stop());
    if (video) video.srcObject = null;
  }

  function loop() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    const ts = performance.now();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const handRes: any = hand.current?.detectForVideo(video, ts);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const poseRes: any = pose.current?.detectForVideo(video, ts);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const faceRes: any = face.current?.detectForVideo(video, ts);

    // Split the two hands by handedness (mirror-flipped preview; best-effort mapping).
    let left: LM[] | null = null;
    let right: LM[] | null = null;
    const hands: LM[][] = handRes?.landmarks ?? [];
    (handRes?.handedness ?? []).forEach((h: { categoryName?: string }[], i: number) => {
      const label = h?.[0]?.categoryName;
      if (label === "Left") left = hands[i];
      else right = hands[i];
    });

    const poseLm: LM[] | null = poseRes?.landmarks?.[0] ?? null;
    const faceLm: LM[] | null = faceRes?.faceLandmarks?.[0] ?? null;

    const frame = normalizeFrame(assembleFrame(poseLm, left, right, faceLm));
    const buf = buffer.current;
    buf.push(frame);
    if (buf.length > SEQ_LEN) buf.shift();

    // draw hand landmarks
    const ctx = canvas.getContext("2d")!;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#5b8cff";
    for (const h of hands) {
      for (const p of h) {
        ctx.beginPath();
        ctx.arc(p.x * canvas.width, p.y * canvas.height, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // throttled recognition
    if (buf.length >= MIN_FRAMES && ts - lastPredict.current > PREDICT_EVERY_MS && !predicting.current) {
      lastPredict.current = ts;
      predicting.current = true;
      recognize(poolMeanStd(buf))
        .then((r) => {
          const top = r.predictions[0];
          if (top) setPrediction({ sign: top.sign_id, conf: top.confidence });
        })
        .catch(() => {})
        .finally(() => {
          predicting.current = false;
        });
    }

    rafRef.current = requestAnimationFrame(loop);
  }

  useEffect(() => () => stop(), []);

  const predLabel = prediction && labels.current[prediction.sign];

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
        {running && prediction && (
          <div className="absolute left-3 top-3 rounded-lg bg-black/60 px-3 py-1.5 text-sm">
            <span className="text-white/60">{t("detected")}: </span>
            <span className="font-semibold text-[var(--accent)]">
              {predLabel ? predLabel.en : prediction.sign}
            </span>
            <span className="text-white/40"> {(prediction.conf * 100).toFixed(0)}%</span>
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
        <span className="text-xs text-white/60">{t("onDevice")}</span>
      </div>
      {error && <p className="text-sm text-amber-400">{error}</p>}
    </div>
  );
}
