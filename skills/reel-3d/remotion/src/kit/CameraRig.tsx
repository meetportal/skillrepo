import { useThree } from "@react-three/fiber";
import { useLayoutEffect } from "react";
import * as THREE from "three";
import { useVideoConfig } from "remotion";
import type { Palette } from "./brand";

export type CameraRigProps = {
  palette: Palette;
  position: [number, number, number];
  target: [number, number, number];
  principal: [number, number];
  shiftPx?: [number, number];
  dolly?: number;
};

export const pxPerUnit = (palette: Palette, height: number, distance: number) =>
  height / (2 * distance * Math.tan(THREE.MathUtils.degToRad(palette.three.camera.fov / 2)));

export const CameraRig = ({ palette, position, target, principal, shiftPx = [0, 0], dolly = 0 }: CameraRigProps) => {
  const camera = useThree((state) => state.camera);
  const { width, height } = useVideoConfig();
  const apply = () => {
    if (!(camera instanceof THREE.PerspectiveCamera)) {
      throw new Error("Scene3D needs a perspective camera");
    }
    const tokens = palette.three.camera;
    const [px, py] = principal;
    camera.fov = tokens.fov;
    camera.near = tokens.near;
    camera.far = tokens.far;
    camera.aspect = width / height;
    camera.setViewOffset(width, height, width / 2 - (px + shiftPx[0]), height / 2 - (py + shiftPx[1]), width, height);
    const k = 1 / (1 + dolly);
    camera.position.set(target[0] + (position[0] - target[0]) * k, target[1] + (position[1] - target[1]) * k, target[2] + (position[2] - target[2]) * k);
    camera.lookAt(target[0], target[1], target[2]);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
  };
  apply();
  useLayoutEffect(apply);
  return null;
};
