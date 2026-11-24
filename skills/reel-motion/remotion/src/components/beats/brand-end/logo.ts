import { useEffect, useState } from "react";
import { cancelRender, continueRender, delayRender } from "remotion";
import { brand, brandAsset, brandLogo, type Brand } from "../../../lib/brand";

export type LogoMeta = { minX: number; minY: number; width: number; height: number };

export type LogoPlacement = { originX: number; originY: number; unit: number };

export type LogoRect = { left: number; top: number; width: number; height: number };

const isLogoKey = (name: string): name is keyof Brand["logos"] => Object.prototype.hasOwnProperty.call(brand.logos, name);

export const resolveLogoSrc = (name: string) => (isLogoKey(name) ? brandLogo(name) : brandAsset(name));

const parseViewBox = (svg: string): LogoMeta => {
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
  throw new Error("Logo SVG has neither a viewBox nor width and height");
};

export const useLogoMeta = (src: string) => {
  const [handle] = useState(() => delayRender(`Reading logo ${src}`));
  const [meta, setMeta] = useState<LogoMeta | null>(null);
  useEffect(() => {
    fetch(src)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Logo ${src} returned ${response.status}`);
        }
        return response.text();
      })
      .then((text) => {
        setMeta(parseViewBox(text));
        continueRender(handle);
      })
      .catch((error: unknown) => cancelRender(error));
  }, [src, handle]);
  return meta;
};

export const placeLogoCentered = (meta: LogoMeta, centerX: number, centerY: number, widthPx: number): LogoPlacement => {
  const unit = widthPx / meta.width;
  const left = centerX - widthPx / 2;
  const top = centerY - (meta.height * unit) / 2;
  return { originX: left - meta.minX * unit, originY: top - meta.minY * unit, unit };
};

export const logoRect = (meta: LogoMeta, placement: LogoPlacement): LogoRect => ({
  left: placement.originX + meta.minX * placement.unit,
  top: placement.originY + meta.minY * placement.unit,
  width: meta.width * placement.unit,
  height: meta.height * placement.unit,
});

export const mixPlacement = (a: LogoPlacement, b: LogoPlacement, t: number): LogoPlacement => ({
  originX: a.originX + (b.originX - a.originX) * t,
  originY: a.originY + (b.originY - a.originY) * t,
  unit: a.unit + (b.unit - a.unit) * t,
});
