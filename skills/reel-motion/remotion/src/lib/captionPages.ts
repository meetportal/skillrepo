import { createTikTokStyleCaptions } from "@remotion/captions";
import { captionRules } from "../theme";
import type { AccentSpec, CaptionMode, CaptionModeName, CaptionWord } from "../types";

export type PageToken = { text: string; start: number; end: number; accent: boolean };
export type CaptionPage = { tokens: PageToken[]; lines: PageToken[][]; start: number; end: number };
export type TimedPage = CaptionPage & { firstFrame: number; endFrame: number };

export type PageRules = { hookMaxWords: number; bodyMinWords: number; bodyMaxWords: number; mergeAcrossPauseSec: number };

export const defaultPageRules: PageRules = {
  hookMaxWords: captionRules.hookMaxWords,
  bodyMinWords: captionRules.bodyMinWords,
  bodyMaxWords: captionRules.bodyMaxWords,
  mergeAcrossPauseSec: captionRules.phrasePauseSec,
};

export const cutSnapMaxFrames = 3;

type RawToken = { text: string; start: number; end: number };
type Span = { first: number; last: number };

export const breakStopWords = new Set([
  "a", "an", "the", "from", "to", "your", "my", "our", "their", "his", "her", "its",
  "and", "or", "but", "too", "very", "of", "in", "on", "at", "with", "by", "for", "as",
  "into", "than", "that", "these", "this", "those", "if", "not", "so", "is", "are", "be",
  "even", "just", "only", "more", "most", "less",
]);

export const weakEndWords = new Set([
  "i", "you", "we", "they", "he", "she", "it", "youll", "well", "theyll", "youre", "were", "theyre", "its",
  "will", "can", "could", "would", "should", "has", "have", "had", "was", "do", "does", "did",
  "dont", "doesnt", "isnt", "arent", "wont", "cant", "long",
]);

const breakCost = {
  stopWordEnd: 12,
  weakWordEnd: 5,
  singleWordPage: 3,
  hookSingleWordPage: 0.5,
  shortPage: 6,
  perPage: 1,
  gapRewardPerSec: 18,
  unfittable: 1000,
};

const normalize = (text: string) => text.toLowerCase().replace(/[^a-z0-9]/g, "");

const endsPhrase = (text: string) => /[,.?!;:]["')\]]*$/.test(text);

export const splitPunctuation = (text: string) => {
  const match = /^(["'([]*)(.*?)([,.?!;:…"')\]]*)$/.exec(text);
  return { lead: match?.[1] ?? "", core: match?.[2] ?? text, trail: match?.[3] ?? "" };
};

const tokenize = (captions: CaptionWord[]): RawToken[] => {
  const { pages } = createTikTokStyleCaptions({ captions, combineTokensWithinMilliseconds: Number.MAX_SAFE_INTEGER });
  return pages
    .flatMap((page) => page.tokens)
    .map((token) => ({ text: token.text.trim(), start: token.fromMs / 1000, end: token.toMs / 1000 }))
    .filter((token) => token.text.length > 0);
};

const matchPhraseAt = (tokens: RawToken[], first: number, target: string): number | null => {
  let joined = "";
  for (let last = first; last < tokens.length; last++) {
    joined += normalize(tokens[last]!.text);
    if (joined === target) {
      return last;
    }
    if (!target.startsWith(joined)) {
      return null;
    }
  }
  return null;
};

export const normalizeAccents = (accents: AccentSpec[]) =>
  accents.map((accent) => (typeof accent === "string" ? { text: accent, n: 1 as number | "all" } : { text: accent.text, n: accent.n ?? 1 }));

export const findAccentSpans = (tokens: RawToken[], accents: AccentSpec[]): Span[] => {
  const taken = new Set<number>();
  const spans: Span[] = [];
  const specs = normalizeAccents(accents)
    .map((spec) => ({ ...spec, target: normalize(spec.text) }))
    .filter((spec) => spec.target.length > 0)
    .sort((a, b) => b.target.length - a.target.length);
  for (const spec of specs) {
    let seen = 0;
    for (let index = 0; index < tokens.length; index++) {
      const last = matchPhraseAt(tokens, index, spec.target);
      if (last === null) {
        continue;
      }
      seen += 1;
      const free = Array.from({ length: last - index + 1 }, (_, offset) => index + offset).every((position) => !taken.has(position));
      if ((spec.n === "all" || spec.n === seen) && free) {
        spans.push({ first: index, last });
        for (let position = index; position <= last; position++) {
          taken.add(position);
        }
      }
      if (spec.n !== "all" && seen >= spec.n) {
        break;
      }
    }
  }
  return spans.sort((a, b) => a.first - b.first);
};

const lineLength = (tokens: RawToken[]) => tokens.reduce((sum, token, index) => sum + token.text.length + (index > 0 ? 1 : 0), 0);

export const layoutLines = <T extends RawToken>(tokens: T[]): T[][] | null => {
  const { maxCharsPerLine, maxLines } = captionRules;
  if (lineLength(tokens) <= maxCharsPerLine) {
    return [tokens];
  }
  if (maxLines < 2) {
    return null;
  }
  let best: T[][] | null = null;
  let bestWidest = Number.POSITIVE_INFINITY;
  for (let split = 1; split < tokens.length; split++) {
    const top = tokens.slice(0, split);
    const bottom = tokens.slice(split);
    const widest = Math.max(lineLength(top), lineLength(bottom));
    if (widest <= maxCharsPerLine && widest < bestWidest) {
      best = [top, bottom];
      bestWidest = widest;
    }
  }
  return best;
};

const splitIntoPhrases = (tokens: RawToken[], rules: PageRules): number[][] => {
  const phrases: number[][] = [];
  let current: number[] = [];
  tokens.forEach((token, index) => {
    const previous = tokens[index - 1];
    if (previous && current.length > 0) {
      const gap = token.start - previous.end;
      if (endsPhrase(previous.text) || gap >= rules.mergeAcrossPauseSec) {
        phrases.push(current);
        current = [];
      }
    }
    current.push(index);
  });
  if (current.length > 0) {
    phrases.push(current);
  }
  return phrases;
};

const spanOf = (spans: Span[], index: number) => spans.find((span) => index >= span.first && index <= span.last);

const accentCount = (page: number[], spans: Span[]) => spans.filter((span) => page.some((index) => index >= span.first && index <= span.last)).length;

const isStopWord = (text: string) => breakStopWords.has(normalize(text));

const pageFits = (page: number[], tokens: RawToken[], spans: Span[], maxWords: number) =>
  page.length <= maxWords && accentCount(page, spans) <= 1 && layoutLines(page.map((index) => tokens[index]!)) !== null;

const pageCost = (
  page: number[],
  tokens: RawToken[],
  spans: Span[],
  maxWords: number,
  isHook: boolean,
  nextStart: number | null,
  endsPhraseHere: boolean,
  rules: PageRules,
) => {
  const first = tokens[page[0]!]!;
  const last = tokens[page[page.length - 1]!]!;
  let cost = breakCost.perPage;
  if (!pageFits(page, tokens, spans, maxWords)) {
    cost += page.length === 1 ? breakCost.unfittable / 10 : breakCost.unfittable;
  }
  if (!endsPhraseHere && nextStart !== null) {
    if (isStopWord(last.text) && !endsPhrase(last.text)) {
      cost += breakCost.stopWordEnd;
    } else if (weakEndWords.has(normalize(last.text)) && !endsPhrase(last.text)) {
      cost += breakCost.weakWordEnd;
    }
    const pauseDiscount = Math.max(0, rules.mergeAcrossPauseSec - captionRules.phrasePauseSec);
    cost -= Math.max(0, nextStart - last.end - pauseDiscount) * breakCost.gapRewardPerSec;
  }
  if (isHook && page.length === 1) {
    cost += breakCost.hookSingleWordPage;
  } else if (!isHook && page.length < rules.bodyMinWords) {
    cost += breakCost.singleWordPage * (rules.bodyMinWords - page.length);
  }
  const shownFor = (nextStart ?? last.end + captionRules.holdAfterLastWordSec) - first.start;
  if (shownFor < captionRules.minPageSec) {
    cost += breakCost.shortPage;
  }
  return cost;
};

const breakPhrase = (
  phrase: number[],
  tokens: RawToken[],
  spans: Span[],
  maxWordsAt: (startSec: number) => number,
  hookEndSec: number,
  phraseEndNext: number | null,
  rules: PageRules,
): number[][] => {
  const widest = Math.max(rules.hookMaxWords, rules.bodyMaxWords);
  const count = phrase.length;
  const best: number[] = [0, ...Array<number>(count).fill(Number.POSITIVE_INFINITY)];
  const from: number[] = Array<number>(count + 1).fill(0);
  for (let end = 1; end <= count; end++) {
    if (end < count && spanOf(spans, phrase[end - 1]!) && spanOf(spans, phrase[end - 1]!) === spanOf(spans, phrase[end]!)) {
      continue;
    }
    for (let start = Math.max(0, end - widest); start < end; start++) {
      if (!Number.isFinite(best[start]!)) {
        continue;
      }
      const page = phrase.slice(start, end);
      const pageStart = tokens[page[0]!]!.start;
      const maxWords = maxWordsAt(pageStart);
      const isHook = pageStart < hookEndSec;
      const nextStart = end < count ? tokens[phrase[end]!]!.start : phraseEndNext;
      const total = best[start]! + pageCost(page, tokens, spans, maxWords, isHook, nextStart, end === count, rules);
      if (total < best[end]!) {
        best[end] = total;
        from[end] = start;
      }
    }
  }
  const pages: number[][] = [];
  let cursor = count;
  while (cursor > 0) {
    const start = from[cursor]!;
    pages.unshift(phrase.slice(start, cursor));
    cursor = start;
  }
  return pages;
};

const mergeShortPages = (chunks: number[][], tokens: RawToken[], spans: Span[], maxWordsAt: (startSec: number) => number): number[][] => {
  const pages = chunks.map((chunk) => [...chunk]);
  const startOf = (page: number[]) => tokens[page[0]!]!.start;
  const shownFor = (pageIndex: number) => {
    const page = pages[pageIndex]!;
    const next = pages[pageIndex + 1];
    const end = next ? startOf(next) : tokens[page[page.length - 1]!]!.end + captionRules.holdAfterLastWordSec;
    return end - startOf(page);
  };
  const fits = (page: number[]) => pageFits(page, tokens, spans, maxWordsAt(startOf(page)));
  let changed = true;
  while (changed) {
    changed = false;
    for (let pageIndex = 0; pageIndex < pages.length; pageIndex++) {
      const page = pages[pageIndex]!;
      if (shownFor(pageIndex) >= captionRules.minPageSec) {
        continue;
      }
      const next = pages[pageIndex + 1];
      const previous = pages[pageIndex - 1];
      if (next && fits([...page, ...next])) {
        pages.splice(pageIndex, 2, [...page, ...next]);
        changed = true;
        break;
      }
      if (previous && fits([...previous, ...page])) {
        pages.splice(pageIndex - 1, 2, [...previous, ...page]);
        changed = true;
        break;
      }
    }
  }
  return pages;
};

export const buildCaptionPages = (
  captions: CaptionWord[],
  accents: AccentSpec[],
  hookEndSec: number,
  rules: PageRules = defaultPageRules,
): CaptionPage[] => {
  const tokens = tokenize(captions);
  const spans = findAccentSpans(tokens, accents);
  const maxWordsAt = (startSec: number) => (startSec < hookEndSec ? rules.hookMaxWords : rules.bodyMaxWords);
  const phrases = splitIntoPhrases(tokens, rules);

  const chunks = phrases.flatMap((phrase, phraseIndex) => {
    const nextPhrase = phrases[phraseIndex + 1];
    const nextStart = nextPhrase ? tokens[nextPhrase[0]!]!.start : null;
    return breakPhrase(phrase, tokens, spans, maxWordsAt, hookEndSec, nextStart, rules);
  });

  return mergeShortPages(chunks, tokens, spans, maxWordsAt).map((page) => {
    const pageTokens: PageToken[] = page.map((index) => ({ ...tokens[index]!, accent: spanOf(spans, index) !== undefined }));
    const lines = layoutLines(pageTokens) ?? [pageTokens];
    return {
      tokens: pageTokens,
      lines,
      start: pageTokens[0]!.start,
      end: pageTokens[pageTokens.length - 1]!.end,
    };
  });
};

export const modeFrames = (mode: CaptionMode, fps: number) => ({ first: Math.round(mode.from * fps), end: Math.round(mode.to * fps) });

const holdBreakingModes: CaptionModeName[] = ["takeover", "hidden"];

export const snapEndToCut = (endFrame: number, firstFrame: number, cutFrames: number[]) => {
  const cut = cutFrames.find((frame) => frame > firstFrame && endFrame - frame >= 1 && endFrame - frame <= cutSnapMaxFrames);
  return cut ?? endFrame;
};

export const timePages = (pages: CaptionPage[], modes: CaptionMode[], fps: number, totalFrames: number, cutFrames: number[] = []): TimedPage[] => {
  const firstFrames = pages.map((page) => Math.max(0, Math.round(page.start * fps) - captionRules.leadFrames));
  const holdBreaks = modes
    .filter((mode) => holdBreakingModes.includes(mode.mode))
    .map((mode) => modeFrames(mode, fps).first)
    .sort((a, b) => a - b);
  const cuts = [...cutFrames].sort((a, b) => a - b);
  return pages.map((page, index) => {
    const firstFrame = firstFrames[index]!;
    const nextFirst = firstFrames[index + 1] ?? totalFrames;
    const holdEnd = Math.round((page.end + captionRules.holdAfterLastWordSec) * fps);
    const spokenEnd = Math.max(firstFrame + 1, Math.round(page.end * fps));
    const holdBreak = holdBreaks.find((breakFrame) => breakFrame >= spokenEnd) ?? totalFrames;
    const endFrame = Math.min(nextFirst, holdEnd, holdBreak, totalFrames);
    return { ...page, firstFrame, endFrame: snapEndToCut(endFrame, firstFrame, cuts) };
  });
};
