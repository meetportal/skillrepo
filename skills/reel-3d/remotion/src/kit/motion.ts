import { Easing } from "remotion";

export const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

export const deg = (degrees: number) => (degrees * Math.PI) / 180;

export const arrive = Easing.bezier(0.16, 1, 0.3, 1);

export const glide = (u: number) => {
  const x = clamp01(u);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

export const progress = (frame: number, startFrame: number, frames: number) => clamp01((frame - startFrame) / Math.max(1, frames));

export const glideBetween = (frame: number, startFrame: number, frames: number, from: number, to: number) =>
  from + (to - from) * glide(progress(frame, startFrame, frames));

export const arriveBetween = (frame: number, startFrame: number, frames: number, from: number, to: number) =>
  from + (to - from) * arrive(progress(frame, startFrame, frames));

export const creepRate = { min: 0.0015, max: 0.0035, standard: 0.0025 };

export const creep = (frame: number, startFrame: number, ratePerFrame = creepRate.standard) =>
  Math.max(0, frame - startFrame) * Math.min(creepRate.max, Math.max(creepRate.min, ratePerFrame));

export type KickOptions = { px?: number; frames?: number; angleDeg?: number };

export const kickDefaults = { px: 4.5, frames: 7, angleDeg: 60 };

export const kick = (frame: number, startFrame: number, options: KickOptions = {}) => {
  const px = options.px ?? kickDefaults.px;
  const frames = options.frames ?? kickDefaults.frames;
  const n = frame - startFrame;
  if (n < 0 || n >= frames) {
    return 0;
  }
  return px * (n % 2 === 0 ? 1 : -1) * Math.pow(1 - n / frames, 1.5);
};

export const kickOffset = (frame: number, startFrame: number, options: KickOptions = {}): [number, number] => {
  const amount = kick(frame, startFrame, options);
  const angle = deg(options.angleDeg ?? kickDefaults.angleDeg);
  return [amount * Math.cos(angle), amount * Math.sin(angle)];
};

export type EntranceOptions = { frames?: number; turnDeg?: number };

export const entranceLimits = { minFrames: 10, maxFrames: 14, minTurnDeg: 20, maxTurnDeg: 35 };

export const entrance = (frame: number, startFrame: number, options: EntranceOptions = {}) => {
  const frames = Math.min(entranceLimits.maxFrames, Math.max(entranceLimits.minFrames, options.frames ?? 12));
  const turnDeg = Math.min(entranceLimits.maxTurnDeg, Math.max(entranceLimits.minTurnDeg, options.turnDeg ?? 25));
  const p = arrive(progress(frame, startFrame, frames));
  return { p, frames, turn: deg(turnDeg) * (1 - p), done: frame >= startFrame + frames };
};

export const holdSway = (frame: number, startFrame: number, amplitudeDeg: number, periodFrames: number) =>
  frame < startFrame ? 0 : deg(amplitudeDeg) * Math.sin(((frame - startFrame) / periodFrames) * Math.PI * 2);

export const landFrameFor = (atFrame: number, leadFrames = 1) => atFrame - Math.min(3, Math.max(0, leadFrames));
