import type { CalculateMetadataFunction } from "remotion";
import type { BrandInput } from "./brand";

export type EventKind = "whoosh" | "impact" | "pop" | "glint";

export type InsertEvent = { id: string; frame: number; kind: EventKind };

export type Fit = "full" | "card";

export type InsertProps<P> = {
  fps: number;
  durationInFrames: number;
  width: number;
  height: number;
  fit: Fit;
  brand: BrandInput;
  assetBase: string;
  beatProps: Partial<P>;
  events?: InsertEvent[];
};

export type Timeline = { events: InsertEvent[] };

export const resolveBeatProps = <P extends object>(name: string, defaults: P, given: Partial<P>): P => {
  const known = new Set(Object.keys(defaults));
  const unknown = Object.keys(given).filter((key) => !known.has(key));
  if (unknown.length > 0) {
    throw new Error(`${name}: unknown props ${unknown.join(", ")} (known: ${[...known].join(", ")})`);
  }
  return { ...defaults, ...given };
};

export const insertMetadata =
  <P extends object>(name: string, defaults: P, timeline: (props: P, frames: number, fps: number) => Timeline): CalculateMetadataFunction<InsertProps<P>> =>
  ({ props }) => {
    const beatProps = resolveBeatProps(name, defaults, props.beatProps);
    const events = timeline(beatProps, props.durationInFrames, props.fps).events.filter((event) => event.frame >= 0 && event.frame < props.durationInFrames);
    return {
      fps: props.fps,
      durationInFrames: props.durationInFrames,
      width: props.width,
      height: props.height,
      props: { ...props, events },
    };
  };
