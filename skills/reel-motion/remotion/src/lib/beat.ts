import { createElement, type ReactElement } from "react";
import type { z } from "zod";
import type { BeatComponent, BeatContext } from "../types";

export type ParsedProps = { ok: true; value: unknown } | { ok: false; issues: string[] };

export type BeatDefinition = {
  parse: (raw: unknown) => ParsedProps;
  render: (context: BeatContext, props: unknown) => ReactElement;
};

export const defineBeat = <S extends z.ZodType>(schema: S, Component: BeatComponent<z.output<S>>): BeatDefinition => ({
  parse: (raw) => {
    const result = schema.safeParse(raw);
    return result.success
      ? { ok: true, value: result.data }
      : { ok: false, issues: result.error.issues.map((issue) => `${issue.path.join(".") || "props"}: ${issue.message}`) };
  },
  render: (context, props) => createElement(Component, { ...context, props: props as z.output<S> }),
});

export const beatSecondsToLocalFrame = (beatSec: number, beatFrom: number, fps: number) =>
  Math.round((beatFrom + beatSec) * fps) - Math.round(beatFrom * fps);
