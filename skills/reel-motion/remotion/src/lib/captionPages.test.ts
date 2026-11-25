import assert from "node:assert/strict";
import { breakStopWords, buildCaptionPages, defaultPageRules, splitPunctuation, timePages, type CaptionPage } from "./captionPages";
import { captionRules } from "../theme";
import type { CaptionWord } from "../types";

const sentence =
  "Most teams send the first message to a cold list from a brand new domain and wonder why the replies stop. " +
  "Warm up every inbox for two weeks, keep the daily volume low, and check the records on your domain before you scale.";

const fixture: CaptionWord[] = sentence.split(" ").map((text, index) => {
  const pause = /[.,]$/.test(text) ? 0.3 : 0;
  const startMs = Math.round(index * 260 + (index > 0 ? 0 : 0));
  return { text: ` ${text}`, startMs, endMs: startMs + 220 - pause, timestampMs: startMs + 110, confidence: null };
});

const hookEndSec = 2.0;
const pages = buildCaptionPages(fixture, ["inbox", { text: "domain", n: 2 }, "replies stop", "volume"], hookEndSec);

const words = (text: string) => text.toLowerCase().replace(/[^a-z0-9]/g, "");

for (const [index, page] of pages.entries()) {
  const last = page.tokens[page.tokens.length - 1]!.text;
  const isPhraseEnd = /[,.?!;:]$/.test(last);
  assert.ok(isPhraseEnd || !breakStopWords.has(words(last)), `page ${index} ends on "${last}"`);
  const limit = page.start < hookEndSec ? captionRules.hookMaxWords : captionRules.bodyMaxWords;
  assert.ok(page.tokens.length <= limit, `page ${index} has ${page.tokens.length} words, limit ${limit}`);
  const accentRuns = page.tokens.filter((token, position) => token.accent && !page.tokens[position - 1]?.accent).length;
  assert.ok(accentRuns <= 1, `page ${index} has ${accentRuns} accents`);
}

const accented = pages.flatMap((page) => page.tokens.filter((token) => token.accent).map((token) => words(token.text)));
assert.deepEqual(accented, ["replies", "stop", "inbox", "volume", "domain"], "accents follow the n selector and first occurrence");
const stopPage = pages.find((page) => page.tokens.some((token) => words(token.text) === "replies"))!;
assert.ok(stopPage.tokens.some((token) => words(token.text) === "stop" && token.accent), "accent phrase stays on one page");
assert.deepEqual(splitPunctuation("soon."), { lead: "", core: "soon", trail: "." });
assert.deepEqual(splitPunctuation("\"2026?\""), { lead: "\"", core: "2026", trail: "?\"" });

assert.deepEqual(
  buildCaptionPages(fixture, ["inbox"], hookEndSec, defaultPageRules).map((page) => page.tokens.length),
  buildCaptionPages(fixture, ["inbox"], hookEndSec).map((page) => page.tokens.length),
  "explicit default rules give the same pages",
);
const narrow = buildCaptionPages(fixture, [], hookEndSec, { ...defaultPageRules, hookMaxWords: 2, bodyMaxWords: 3 });
for (const [index, page] of narrow.entries()) {
  const limit = page.start < hookEndSec ? 2 : 3;
  assert.ok(page.tokens.length <= limit, `narrow page ${index} has ${page.tokens.length} words, limit ${limit}`);
}

const listFixture: CaptionWord[] = ["First", "warm", "every", "inbox.", "Second", "keep", "volume", "low."].map((text, index) => {
  const startMs = 3000 + index * 300 + (index >= 1 ? 280 : 0) + (index >= 5 ? 280 : 0);
  return { text: ` ${text}`, startMs, endMs: startMs + 240, timestampMs: startMs + 120, confidence: null };
});
const pauseSplit = buildCaptionPages(listFixture, [], 0, defaultPageRules);
const pauseMerged = buildCaptionPages(listFixture, [], 0, { ...defaultPageRules, mergeAcrossPauseSec: 0.5, bodyMinWords: 2 });
assert.ok(pauseSplit.some((page) => page.tokens.length === 1), "a 0.34 s pause splits a one-word list marker page by default");
assert.ok(pauseMerged.every((page) => page.tokens.length >= 2), "mergeAcrossPauseSec 0.5 keeps the list marker with its words");

const fps = 25;
const timingPage = (startSec: number, endSec: number): CaptionPage => ({ tokens: [], lines: [], start: startSec, end: endSec });
const cutPages = [timingPage(1.0, 1.4), timingPage(1.48, 1.9), timingPage(3.0, 3.3), timingPage(5.0, 5.2)];
const uncut = timePages(cutPages, [], fps, 300);
const cutFrame = uncut[0]!.endFrame - 2;
const farCut = uncut[2]!.endFrame - 4;
const cut = timePages(cutPages, [], fps, 300, [cutFrame, farCut, uncut[3]!.firstFrame]);
assert.equal(cut[0]!.endFrame, cutFrame, "a page that would end 2 frames after a cut ends on the cut frame");
assert.equal(cut[1]!.endFrame, uncut[1]!.endFrame, "a page with no cut near its end keeps its end");
assert.equal(cut[2]!.endFrame, uncut[2]!.endFrame, "a cut 4 frames before the end does not move it");
assert.equal(cut[3]!.endFrame, uncut[3]!.endFrame, "a cut on the page's first frame does not move its end");
for (const offset of [1, 2, 3, 4]) {
  const moved = timePages(cutPages, [], fps, 300, [uncut[0]!.endFrame - offset])[0]!;
  const expected = offset <= 3 ? uncut[0]!.endFrame - offset : uncut[0]!.endFrame;
  assert.equal(moved.endFrame, expected, `page end ${offset} frames after a cut`);
}

console.log(`caption page tests passed (${pages.length} pages, cut snap and page options)`);
for (const page of pages) {
  console.log(`  ${page.start.toFixed(2)}  ${page.lines.map((line) => line.map((token) => (token.accent ? `*${token.text}*` : token.text)).join(" ")).join(" | ")}`);
}
