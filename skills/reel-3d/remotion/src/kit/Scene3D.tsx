import { ThreeCanvas } from "@remotion/three";
import type { ReactNode } from "react";
import { useVideoConfig } from "remotion";
import type { Palette } from "./brand";

export const Scene3D = ({ palette, children }: { palette: Palette; children: ReactNode }) => {
  const { width, height } = useVideoConfig();
  const camera = palette.three.camera;
  return (
    <ThreeCanvas
      width={width}
      height={height}
      dpr={1}
      gl={{ antialias: true }}
      shadows="percentage"
      flat
      camera={{ fov: camera.fov, near: camera.near, far: camera.far, position: [0, 0, 20] }}
    >
      {children}
    </ThreeCanvas>
  );
};
