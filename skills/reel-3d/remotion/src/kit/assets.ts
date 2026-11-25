import { useEffect, useState } from "react";
import { useDelayRender } from "remotion";

const useGate = <T,>(label: string, load: () => Promise<T>, key: string) => {
  const { delayRender, continueRender, cancelRender } = useDelayRender();
  const [handle] = useState(() => delayRender(label));
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    let alive = true;
    load()
      .then((result) => {
        if (alive) {
          setValue(result);
        }
      })
      .catch((error: unknown) => cancelRender(error instanceof Error ? error : new Error(String(error))));
    return () => {
      alive = false;
    };
  }, [key]);
  useEffect(() => {
    if (value !== null) {
      continueRender(handle);
    }
  }, [value, handle, continueRender]);
  return value;
};

export const useAssetText = (url: string) =>
  useGate(
    `fetch ${url}`,
    async () => {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`${url} returned ${response.status}`);
      }
      return response.text();
    },
    url,
  );

export const useTextWidths = (fontUrl: string, texts: string[]) =>
  useGate(
    `measure ${texts.join(" ")}`,
    async () => {
      const family = `Reel3D${fontUrl.replace(/[^A-Za-z0-9]/g, "")}`;
      const face = await new FontFace(family, `url(${fontUrl})`).load();
      document.fonts.add(face);
      const context = document.createElement("canvas").getContext("2d");
      if (!context) {
        throw new Error("2D canvas is not available");
      }
      context.font = `100px ${family}`;
      return texts.map((text) => context.measureText(text).width / 100);
    },
    `${fontUrl}|${texts.join("|")}`,
  );
