import { useEffect, useMemo, type DependencyList } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { SVGLoader } from "three/examples/jsm/loaders/SVGLoader.js";

type Disposable = { dispose: () => void };

export const useDisposable = <T extends Disposable>(factory: () => T, deps: DependencyList): T => {
  const value = useMemo(factory, deps);
  useEffect(() => () => value.dispose(), [value]);
  return value;
};

export const roundedRectShape = (width: number, height: number, radius: number, cx = 0, cy = 0) => {
  const r = Math.min(radius, width / 2, height / 2);
  const x = cx - width / 2;
  const y = cy - height / 2;
  const shape = new THREE.Shape();
  shape.moveTo(x + r, y);
  shape.lineTo(x + width - r, y);
  shape.quadraticCurveTo(x + width, y, x + width, y + r);
  shape.lineTo(x + width, y + height - r);
  shape.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  shape.lineTo(x + r, y + height);
  shape.quadraticCurveTo(x, y + height, x, y + height - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  return shape;
};

export type SlabOptions = { depth: number; bevel?: number; bevelSegments?: number; curveSegments?: number; centered?: boolean };

export const extrudeShape = (shape: THREE.Shape | THREE.Shape[], options: SlabOptions) => {
  const bevel = options.bevel ?? 0;
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: options.depth,
    bevelEnabled: bevel > 0,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelOffset: bevel > 0 ? -bevel : 0,
    bevelSegments: options.bevelSegments ?? 4,
    curveSegments: options.curveSegments ?? 10,
  });
  if (options.centered !== false) {
    geometry.translate(0, 0, -options.depth / 2);
  }
  return geometry;
};

export const roundedSlab = (width: number, height: number, radius: number, options: SlabOptions) =>
  extrudeShape(roundedRectShape(width, height, radius), options);

export const shieldHalf = (width: number, height: number, side: 1 | -1, shoulder = 0.42, segments = 72) => {
  const w = width / 2;
  const top = height / 2;
  const bottom = -height / 2;
  const corner = Math.min(w, height) * 0.18;
  const sideBottom = top - height * shoulder;
  const drop = sideBottom - bottom;
  const path = new THREE.Path();
  path.moveTo(0, top);
  path.lineTo(side * (w - corner), top);
  path.quadraticCurveTo(side * w, top, side * w, top - corner);
  path.lineTo(side * w, sideBottom);
  path.bezierCurveTo(side * w, sideBottom - drop * 0.55, side * w * 0.42, bottom + drop * 0.18, 0, bottom);
  const points = path.getSpacedPoints(segments);
  return new THREE.CatmullRomCurve3(
    points.map((p) => new THREE.Vector3(p.x, p.y, 0)),
    false,
    "centripetal",
  );
};

export const flipWinding = (geometry: THREE.BufferGeometry) => {
  const index = geometry.getIndex();
  if (index) {
    const array = index.array;
    for (let i = 0; i < array.length; i += 3) {
      const b = array[i + 1] ?? 0;
      array[i + 1] = array[i + 2] ?? 0;
      array[i + 2] = b;
    }
    index.needsUpdate = true;
    return geometry;
  }
  for (const attribute of Object.values(geometry.attributes)) {
    const size = attribute.itemSize;
    const array = attribute.array;
    for (let i = 0; i < attribute.count; i += 3) {
      for (let k = 0; k < size; k += 1) {
        const a = (i + 1) * size + k;
        const b = (i + 2) * size + k;
        const tmp = array[a] ?? 0;
        array[a] = array[b] ?? 0;
        array[b] = tmp;
      }
    }
    attribute.needsUpdate = true;
  }
  return geometry;
};

export type SvgBox = { minX: number; minY: number; width: number; height: number };

export const svgViewBox = (svg: string): SvgBox => {
  const values = (svg.match(/viewBox\s*=\s*"([^"]+)"/)?.[1] ?? "").trim().split(/[\s,]+/).map(Number);
  const [minX = Number.NaN, minY = Number.NaN, width = Number.NaN, height = Number.NaN] = values;
  if (values.length === 4 && [minX, minY, width, height].every(Number.isFinite) && width > 0 && height > 0) {
    return { minX, minY, width, height };
  }
  const plainWidth = Number(svg.match(/\swidth\s*=\s*"([\d.]+)/)?.[1]);
  const plainHeight = Number(svg.match(/\sheight\s*=\s*"([\d.]+)/)?.[1]);
  if (plainWidth > 0 && plainHeight > 0) {
    return { minX: 0, minY: 0, width: plainWidth, height: plainHeight };
  }
  throw new Error("logo SVG has neither a viewBox nor width and height");
};

export type SvgPart = { color: string; geometry: THREE.BufferGeometry };

const dedupe = (points: THREE.Vector2[], closed: boolean) => {
  const unique = points.filter((p, i) => i === 0 || p.distanceTo(points[i - 1] ?? p) > 1e-6);
  const first = unique[0];
  const last = unique[unique.length - 1];
  return closed && first && last && unique.length > 2 && first.distanceTo(last) < 1e-6 ? unique.slice(0, -1) : unique;
};

const offsetLine = (points: THREE.Vector2[], distance: number, closed: boolean) =>
  points.map((p, i) => {
    const prev = points[closed ? (i - 1 + points.length) % points.length : Math.max(0, i - 1)] ?? p;
    const next = points[closed ? (i + 1) % points.length : Math.min(points.length - 1, i + 1)] ?? p;
    const inDir = new THREE.Vector2().subVectors(p, prev);
    const outDir = new THREE.Vector2().subVectors(next, p);
    const a = inDir.lengthSq() > 0 ? inDir.normalize() : outDir.clone().normalize();
    const b = outDir.lengthSq() > 0 ? outDir.normalize() : a.clone();
    const tangent = a.clone().add(b);
    if (tangent.lengthSq() < 1e-12) {
      tangent.copy(b);
    }
    tangent.normalize();
    const normal = new THREE.Vector2(-tangent.y, tangent.x);
    const miter = Math.min(2, 1 / Math.max(0.5, normal.dot(new THREE.Vector2(-b.y, b.x))));
    return new THREE.Vector2(p.x + normal.x * distance * miter, p.y + normal.y * distance * miter);
  });

const capArc = (center: THREE.Vector2, from: THREE.Vector2, radius: number, steps = 12) => {
  const start = Math.atan2(from.y - center.y, from.x - center.x);
  return Array.from({ length: steps - 1 }, (_, k) => {
    const angle = start - (Math.PI * (k + 1)) / steps;
    return new THREE.Vector2(center.x + Math.cos(angle) * radius, center.y + Math.sin(angle) * radius);
  });
};

const strokeShape = (points: THREE.Vector2[], width: number, closed: boolean) => {
  const line = dedupe(points, closed);
  const half = width / 2;
  if (line.length < 2) {
    return null;
  }
  if (closed) {
    const a = offsetLine(line, half, true);
    const b = offsetLine(line, -half, true);
    const aOuter = Math.abs(THREE.ShapeUtils.area(a)) > Math.abs(THREE.ShapeUtils.area(b));
    const shape = new THREE.Shape(aOuter ? a : b);
    shape.holes.push(new THREE.Path(aOuter ? b : a));
    return shape;
  }
  const left = offsetLine(line, half, false);
  const right = offsetLine(line, -half, false);
  const first = line[0];
  const last = line[line.length - 1];
  const leftLast = left[left.length - 1];
  const rightFirst = right[0];
  if (!first || !last || !leftLast || !rightFirst) {
    return null;
  }
  return new THREE.Shape([...left, ...capArc(last, leftLast, half), ...right.reverse(), ...capArc(first, rightFirst, half)]);
};

export const svgToParts = (svg: string, depth: number, bevel: number, scale: number): SvgPart[] => {
  const data = new SVGLoader().parse(svg);
  const byColor = new Map<string, THREE.BufferGeometry[]>();
  const add = (color: string, geometry: THREE.BufferGeometry) => {
    const list = byColor.get(color) ?? [];
    list.push(geometry);
    byColor.set(color, list);
  };
  const options = { depth: depth / scale, bevel: bevel / scale, bevelSegments: 3, curveSegments: 12, centered: false };
  for (const path of data.paths) {
    const style = path.userData?.style as { fill?: string; stroke?: string; strokeWidth?: number } | undefined;
    const fill = style?.fill;
    if (fill && fill !== "none") {
      const shapes = path.toShapes();
      if (shapes.length > 0) {
        add(new THREE.Color(fill).getHexString(), extrudeShape(shapes, options));
      }
    }
    const stroke = style?.stroke;
    if (stroke && stroke !== "none") {
      const width = style?.strokeWidth ?? 1;
      for (const subPath of path.subPaths) {
        const points = subPath.getPoints(24);
        const first = points[0];
        const last = points[points.length - 1];
        const closed = subPath.autoClose || (first !== undefined && last !== undefined && first.distanceTo(last) < 1e-6);
        const shape = strokeShape(points, width, closed);
        if (shape) {
          add(new THREE.Color(stroke).getHexString(), extrudeShape(shape, { ...options, bevel: Math.min(options.bevel, width * 0.3), curveSegments: 10 }));
        }
      }
    }
  }
  const parts: SvgPart[] = [];
  for (const [color, list] of byColor) {
    const merged = mergeGeometries(list.map((g) => g.index ? g.toNonIndexed() : g), false);
    list.forEach((g) => g.dispose());
    if (!merged) {
      throw new Error("could not merge logo geometry");
    }
    merged.translate(0, 0, -depth / scale);
    merged.scale(scale, -scale, scale);
    flipWinding(merged);
    merged.computeBoundingBox();
    parts.push({ color: `#${color.toUpperCase()}`, geometry: merged });
  }
  return parts;
};
