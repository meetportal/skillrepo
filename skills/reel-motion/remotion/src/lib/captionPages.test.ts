import assert from "node:assert/strict";
import { breakStopWords, buildCaptionPages, splitPunctuation } from "./captionPages";
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

console.log(`caption page tests passed (${pages.length} pages)`);
for (const page of pages) {
  console.log(`  ${page.start.toFixed(2)}  ${page.lines.map((line) => line.map((token) => (token.accent ? `*${token.text}*` : token.text)).join(" ")).join(" | ")}`);
}
