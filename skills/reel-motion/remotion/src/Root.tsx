import { Composition, type CalculateMetadataFunction } from "remotion";
import { CaptionBoxes, calculateCaptionBoxes, type CaptionBoxesProps } from "./CaptionBoxes";
import { Reel } from "./Reel";
import { layout } from "./theme";
import { reelPropsSchema, type ReelProps } from "./types";

const defaultProps: ReelProps = {
  aroll: "",
  durationSec: 3,
  fps: 25,
  cues: { segments: [], cuts: [] },
  camera: [],
  captions: [],
  captionModes: [],
  beats: [],
  accents: [],
};

const calculateMetadata: CalculateMetadataFunction<ReelProps> = ({ props }) => ({
  fps: props.fps,
  durationInFrames: Math.max(1, Math.round(props.durationSec * props.fps)),
});

export const RemotionRoot = () => (
  <>
    <Composition
      id="Reel"
      component={Reel}
      schema={reelPropsSchema}
      width={layout.width}
      height={layout.height}
      fps={defaultProps.fps}
      durationInFrames={Math.round(defaultProps.durationSec * defaultProps.fps)}
      defaultProps={defaultProps}
      calculateMetadata={calculateMetadata}
    />
    <Composition
      id="CaptionBoxes"
      component={CaptionBoxes}
      width={layout.width}
      height={layout.height}
      fps={defaultProps.fps}
      durationInFrames={1}
      defaultProps={defaultProps as CaptionBoxesProps}
      calculateMetadata={calculateCaptionBoxes}
    />
  </>
);
