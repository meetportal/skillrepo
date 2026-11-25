import { useMemo } from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { Backdrop } from "../kit/Backdrop";
import { makePalette } from "../kit/brand";
import { CameraRig, pxPerUnit } from "../kit/CameraRig";
import type { InsertProps, Timeline } from "../kit/insert";
import { resolveBeatProps } from "../kit/insert";
import { Scene3D } from "../kit/Scene3D";

export type BrandPatchProps = { tokens: string[] };

export const brandPatchDefaults: BrandPatchProps = { tokens: ["brandBlueOnDark", "navyPanel", "danger", "success", "accent", "cream"] };

export const brandPatchTimeline = (): Timeline => ({ events: [] });

export const BrandPatch3D = (input: InsertProps<BrandPatchProps>) => {
  const { width, height } = useVideoConfig();
  const props = resolveBeatProps("BrandPatch3D", brandPatchDefaults, input.beatProps);
  const palette = useMemo(() => makePalette(input.brand, input.assetBase), [input.brand, input.assetBase]);
  const distance = 20;
  const unit = pxPerUnit(palette, height, distance);
  const patchPx = 200;
  const columns = 2;
  return (
    <AbsoluteFill>
      <Scene3D palette={palette}>
        <Backdrop palette={palette} />
        <CameraRig palette={palette} position={[0, 0, distance]} target={[0, 0, 0]} principal={[width / 2, height / 2]} />
        {props.tokens.map((token, i) => {
          const cx = (i % columns) * 300 + width / 2 - 150;
          const cy = Math.floor(i / columns) * 300 + 300;
          return (
            <mesh key={token} position={[(cx - width / 2) / unit, (height / 2 - cy) / unit, 0]}>
              <planeGeometry args={[patchPx / unit, patchPx / unit]} />
              <meshBasicMaterial color={palette.color(token)} />
            </mesh>
          );
        })}
      </Scene3D>
    </AbsoluteFill>
  );
};
