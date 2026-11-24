import { z } from "zod";

export const railStates = ["empty", "active", "marked", "fixed"] as const;

export type RailState = (typeof railStates)[number];

export const railEventSchema = z.object({
  t: z.number().nonnegative(),
  segment: z.number().int().nonnegative(),
  state: z.enum(railStates),
});

export type RailEvent = z.infer<typeof railEventSchema>;

export type RailSegmentState = { state: RailState; since: number; previous: RailState };

export const railStateAt = (events: RailEvent[], segment: number, absoluteSec: number): RailSegmentState => {
  let current: RailSegmentState = { state: "empty", since: Number.NEGATIVE_INFINITY, previous: "empty" };
  for (const event of [...events].sort((a, b) => a.t - b.t)) {
    if (event.segment === segment && event.t <= absoluteSec) {
      current = { state: event.state, since: event.t, previous: current.state };
    }
  }
  return current;
};

export const railStatesAt = (events: RailEvent[], segments: number, absoluteSec: number) =>
  Array.from({ length: segments }, (_, segment) => railStateAt(events, segment, absoluteSec));
