import { seeded } from "./kit";

export type CrackGeometry = {
  mainPath: string;
  branchPaths: string[];
  leftClip: string;
  rightClip: string;
};

type Point = { x: number; y: number };

const pathOf = (points: Point[]) => points.map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");

const px = (point: Point) => `${point.x.toFixed(1)}px ${point.y.toFixed(1)}px`;

export const crackGeometry = (width: number, height: number, seed: number): CrackGeometry => {
  const random = seeded(seed);
  const segments = 6;
  const baseX = width * (0.5 + (random() - 0.5) * 0.22);
  const flip = random() < 0.5 ? 1 : -1;
  const amplitude = width * 0.06;
  const points: Point[] = [];
  for (let index = 0; index <= segments; index += 1) {
    const along = index / segments;
    const side = (index % 2 === 0 ? -1 : 1) * flip;
    const jitterY = index === 0 || index === segments ? 0 : (random() - 0.5) * (height / segments) * 0.5;
    points.push({
      x: baseX + side * amplitude * (0.5 + random() * 0.8) + (along - 0.5) * width * 0.08 * -flip,
      y: index === 0 ? -6 : index === segments ? height + 6 : along * height + jitterY,
    });
  }
  const branchFrom = (point: Point, direction: number): Point[] => {
    const reach = width * (0.1 + random() * 0.06);
    const drop = height * (0.08 + random() * 0.06);
    return [point, { x: point.x + direction * reach * 0.55, y: point.y + drop * 0.6 }, { x: point.x + direction * reach, y: point.y + drop }];
  };
  const pick = (index: number): Point => points[index] ?? { x: baseX, y: 0 };
  const first = pick(0);
  const last = pick(points.length - 1);
  const outside = 80;
  const left = [`${-outside}px ${-outside}px`, `${first.x.toFixed(1)}px ${-outside}px`, ...points.map(px), `${last.x.toFixed(1)}px ${height + outside}px`, `${-outside}px ${height + outside}px`];
  const right = [
    `${width + outside}px ${-outside}px`,
    `${first.x.toFixed(1)}px ${-outside}px`,
    ...points.map(px),
    `${last.x.toFixed(1)}px ${height + outside}px`,
    `${width + outside}px ${height + outside}px`,
  ];
  return {
    mainPath: pathOf(points),
    branchPaths: [pathOf(branchFrom(pick(2), -flip)), pathOf(branchFrom(pick(4), flip))],
    leftClip: `polygon(${left.join(", ")})`,
    rightClip: `polygon(${right.join(", ")})`,
  };
};
