import type { ComponentType } from "react";
import { z } from "zod";

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

export const cameraEaseSchema = z.enum(["cut", "push", "creep"]);

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

export const reelPropsSchema = z.object({
  aroll: z.string(),
  durationSec: z.number().positive(),
  fps: z.number().int().positive(),
  cues: cuesSchema,
  camera: z.array(cameraKeySchema),
  captions: z.array(captionSchema),
  captionModes: z.array(captionModeSchema),
  beats: z.array(beatSchema),
  accents: z.array(z.string()),
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
export type ReelProps = z.infer<typeof reelPropsSchema>;

export type BeatRenderProps = {
  beat: Beat;
};

export type BeatComponent = ComponentType<BeatRenderProps>;
