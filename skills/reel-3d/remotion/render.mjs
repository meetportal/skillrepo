import fs from "node:fs";
import path from "node:path";
import { openBrowser, renderFrames, renderMedia, renderStill, selectComposition } from "@remotion/renderer";

const usage = `usage: node render.mjs --serve-url DIR --composition ID --props FILE
  [--out FILE.mov] [--stills 4,17,32 --stills-dir DIR] [--sequence DIR] [--concurrency 2] [--gl swangle]

Renders one reel-3d insert with the Node API (ProRes 4444, PNG frames, muted, bt709)
and prints {composition, fps, frames, width, height, events, gl, renderSec} as JSON.
--stills renders single PNG frames; --sequence writes a PNG per frame (determinism checks).`;

const args = process.argv.slice(2);
const option = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`);
  return index >= 0 && index + 1 < args.length ? args[index + 1] : fallback;
};
if (args.includes("--help") || args.includes("-h")) {
  console.log(usage);
  process.exit(0);
}

const serveUrl = option("serve-url");
const id = option("composition");
const propsFile = option("props");
const out = option("out");
const stills = option("stills");
const stillsDir = option("stills-dir");
const sequence = option("sequence");
const gl = option("gl", "swangle");
const concurrency = Number(option("concurrency", process.env.REEL_CONCURRENCY ?? "2"));
if (!serveUrl || !id || !propsFile || (!out && !stills && !sequence)) {
  console.error(usage);
  process.exit(2);
}
if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 2) {
  console.error("concurrency must be 1 or 2");
  process.exit(2);
}

const inputProps = JSON.parse(fs.readFileSync(propsFile, "utf8"));
const chromiumOptions = { gl };
const started = performance.now();
const browser = await openBrowser("chrome", { chromiumOptions, logLevel: "warn" });
try {
  const composition = await selectComposition({ serveUrl, id, inputProps, puppeteerInstance: browser, chromiumOptions, logLevel: "warn" });
  const common = { composition, serveUrl, inputProps, puppeteerInstance: browser, chromiumOptions, logLevel: "warn" };
  if (out) {
    fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
    await renderMedia({
      ...common,
      codec: "prores",
      proResProfile: "4444",
      pixelFormat: "yuv444p10le",
      imageFormat: "png",
      muted: true,
      colorSpace: "bt709",
      concurrency,
      outputLocation: out,
      overwrite: true,
    });
  }
  if (sequence) {
    fs.mkdirSync(sequence, { recursive: true });
    await renderFrames({
      ...common,
      imageFormat: "png",
      concurrency,
      outputDir: sequence,
      onStart: () => undefined,
      onFrameUpdate: () => undefined,
    });
  }
  if (stills) {
    const dir = stillsDir ?? path.dirname(path.resolve(out ?? propsFile));
    fs.mkdirSync(dir, { recursive: true });
    for (const value of stills.split(",")) {
      const frame = Number(value);
      await renderStill({ ...common, frame, imageFormat: "png", output: path.join(dir, `${id}_f${String(frame).padStart(3, "0")}.png`), overwrite: true });
    }
  }
  console.log(
    JSON.stringify({
      composition: id,
      fps: composition.fps,
      frames: composition.durationInFrames,
      width: composition.width,
      height: composition.height,
      events: composition.props.events ?? [],
      gl,
      renderSec: Math.round((performance.now() - started) / 10) / 100,
    }),
  );
} finally {
  await browser.close({ silent: true });
}
