import type { CalculateMetadataFunction } from "remotion";
import { layoutCaptionPages, type CaptionPageLayout } from "./components/Captions";
import { fontsReady } from "./fonts";
import { reelPropsSchema } from "./types";

export type CaptionBoxesProps = Record<string, unknown> & { captionBoxes?: CaptionPageLayout[] };

export const CaptionBoxes = () => null;

export const calculateCaptionBoxes: CalculateMetadataFunction<CaptionBoxesProps> = async ({ props }) => {
  const reel = reelPropsSchema.parse(props);
  const totalFrames = Math.max(1, Math.round(reel.durationSec * reel.fps));
  await fontsReady;
  const captionBoxes = layoutCaptionPages({
    captions: reel.captions,
    accents: reel.accents,
    modes: reel.captionModes,
    hookEndSec: reel.cues.cuts.find((cut) => cut > 0) ?? reel.durationSec,
    fps: reel.fps,
    totalFrames,
    cuts: reel.cues.cuts,
    options: reel.captionOptions,
  });
  return { fps: reel.fps, durationInFrames: 1, props: { ...props, captionBoxes } };
};
