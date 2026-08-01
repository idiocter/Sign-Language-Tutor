// Client-side session state (Zustand). Mastery + the currently practiced sign live here;
// durable state (FSRS schedule, attempts) is owned by the backend.

import { create } from "zustand";

interface SessionState {
  targetSignId: string;
  mastery: Record<string, number>; // sign_id -> 0..1
  setTargetSign: (signId: string) => void;
  recordMastery: (signId: string, value: number) => void;
}

export const useSession = create<SessionState>((set) => ({
  targetSignId: "NSL_0001",
  mastery: {},
  setTargetSign: (signId) => set({ targetSignId: signId }),
  recordMastery: (signId, value) =>
    set((s) => ({ mastery: { ...s.mastery, [signId]: value } })),
}));
