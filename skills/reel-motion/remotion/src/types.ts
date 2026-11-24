import type { ComponentType } from "react";
import { z } from "zod";
import { brand } from "./lib/brand";

export const faceBoxSchema = z.object({
  cx: z.number(),
  cy: z.number(),
  w: z.number(),
  h: z.number(),
});

export const cueSegmentSchema = z.object({
  index: z.number().int(),
  clip: z.string(),
  start: z.number(),
  end: z.number(),
  face: faceBoxSchema.nullable(),
});

export const cuesSchema = z.object({
  segments: z.array(cueSegmentSchema),
  cuts: z.array(z.number()),
});

export const cameraEaseSchema = z.enum(["cut", "push", "creep", "hold"]);

export const cameraKeySchema = z.object({
  t: z.number(),
  scale: z.number(),
  tx: z.number(),
  ty: z.number(),
  ease: cameraEaseSchema,
});

export const captionSchema = z.object({
  text: z.string(),
  startMs: z.number(),
  endMs: z.number(),
  timestampMs: z.number().nullable(),
  confidence: z.number().nullable(),
});

export const captionModeNameSchema = z.enum(["talk", "card", "takeover", "hidden"]);

export const captionModeSchema = z.object({
  from: z.number(),
  to: z.number(),
  mode: captionModeNameSchema,
});

export const beatSchema = z.object({
  id: z.string(),
  component: z.string(),
  from: z.number(),
  to: z.number(),
  props: z.record(z.string(), z.unknown()),
});

export const accentSpecSchema = z.union([
  z.string(),
  z.object({ text: z.string(), n: z.union([z.number().int().positive(), z.literal("all")]).optional() }),
]);

export const topLogoRangeSchema = z.object({
  from: z.number().nonnegative(),
  to: z.number().positive(),
});

export const topLogoSchema = z.object({
  enabled: z.boolean().default(false),
  logo: z.string().min(1).default("white"),
  widthPx: z.number().min(brand.logoMark.minWidthPx).max(400).default(brand.layout.topLogo.widthPx),
  centerY: z.number().min(brand.layout.topLogo.y0).max(brand.layout.topLogo.centerYMax).default(brand.layout.topLogo.centerY),
  ranges: z.array(topLogoRangeSchema).default([]),
  hideDuring: z.array(z.string()).default(["EndCard"]),
  enterFrames: z.number().int().min(0).max(20).default(8),
  exitFrames: z.number().int().min(1).max(20).default(5),
  slidePx: z.number().min(0).max(40).default(14),
  shadow: z.number().min(0).max(1).default(1),
  scrim: z.number().min(0).max(1).default(0.22),
});

export const reelPropsSchema = z.object({
  aroll: z.string(),
  durationSec: z.number().positive(),
  fps: z.number().int().positive(),
  cues: cuesSchema,
  camera: z.array(cameraKeySchema),
  captions: z.array(captionSchema),
  captionModes: z.array(captionModeSchema),
  beats: z.array(beatSchema),
  accents: z.array(accentSpecSchema),
  topLogo: topLogoSchema.optional(),
  guides: z.boolean().optional(),
});

export type FaceBox = z.infer<typeof faceBoxSchema>;
export type CueSegment = z.infer<typeof cueSegmentSchema>;
export type Cues = z.infer<typeof cuesSchema>;
export type CameraEase = z.infer<typeof cameraEaseSchema>;
export type CameraKey = z.infer<typeof cameraKeySchema>;
export type CaptionWord = z.infer<typeof captionSchema>;
export type CaptionModeName = z.infer<typeof captionModeNameSchema>;
export type CaptionMode = z.infer<typeof captionModeSchema>;
export type Beat = z.infer<typeof beatSchema>;
export type AccentSpec = z.infer<typeof accentSpecSchema>;
export type TopLogoRange = z.infer<typeof topLogoRangeSchema>;
export type TopLogoProps = z.infer<typeof topLogoSchema>;
export type ReelProps = z.infer<typeof reelPropsSchema>;

export type BeatContext = {
  beat: Beat;
  frame: number;
  durationInFrames: number;
  fps: number;
  toFrame: (absoluteSec: number) => number;
};

export type BeatProps<P> = BeatContext & { props: P };

export type BeatComponent<P> = ComponentType<BeatProps<P>>;
