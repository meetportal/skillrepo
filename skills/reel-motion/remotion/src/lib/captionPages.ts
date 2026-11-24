import { createTikTokStyleCaptions } from "@remotion/captions";
import { captionRules } from "../theme";
import type { CaptionWord } from "../types";

export type PageToken = { text: string; start: number; end: number; accent: boolean };
export type CaptionPage = { tokens: PageToken[]; lines: PageToken[][]; start: number; end: number };

type RawToken = { text: string; start: number; end: number };
type Span = { first: number; last: number };

const normalize = (text: string) => text.toLowerCase().replace(/[^a-z0-9]/g, "");

const endsPhrase = (text: string) => /[,.?!;:]$/.test(text);

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

const findAccentSpans = (tokens: RawToken[], accents: string[]): Span[] => {
  const targets = accents.map(normalize).filter(Boolean).sort((a, b) => b.length - a.length);
  const spans: Span[] = [];
  let index = 0;
  while (index < tokens.length) {
    const last = targets.map((target) => matchPhraseAt(tokens, index, target)).find((match) => match !== null);
    if (last !== undefined && last !== null) {
      spans.push({ first: index, last });
      index = last + 1;
    } else {
      index += 1;
    }
  }
  return spans;
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

const splitIntoPhrases = (tokens: RawToken[], hookEndSec: number): number[][] => {
  const phrases: number[][] = [];
  let current: number[] = [];
  tokens.forEach((token, index) => {
    const previous = tokens[index - 1];
    if (previous && current.length > 0) {
      const gap = token.start - previous.end;
      const crossesHookEnd = previous.start < hookEndSec && token.start >= hookEndSec;
      if (endsPhrase(previous.text) || gap >= captionRules.phrasePauseSec || crossesHookEnd) {
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

const evenChunks = (indices: number[], maxWords: number): number[][] => {
  const count = Math.ceil(indices.length / maxWords);
  const chunks: number[][] = [];
  let cursor = 0;
  for (let chunk = 0; chunk < count; chunk++) {
    const size = Math.ceil((indices.length - cursor) / (count - chunk));
    chunks.push(indices.slice(cursor, cursor + size));
    cursor += size;
  }
  return chunks;
};

const spanOf = (spans: Span[], index: number) => spans.find((span) => index >= span.first && index <= span.last);

const repairAccentBoundaries = (chunks: number[][], spans: Span[]): number[][] => {
  const result = chunks.map((chunk) => [...chunk]);
  for (let chunkIndex = 0; chunkIndex < result.length - 1; chunkIndex++) {
    const current = result[chunkIndex]!;
    const next = result[chunkIndex + 1]!;
    const lastIndex = current[current.length - 1];
    const firstNext = next[0];
    if (lastIndex === undefined || firstNext === undefined) {
      continue;
    }
    const span = spanOf(spans, lastIndex);
    if (span && span.last >= firstNext) {
      const moveCount = span.last - lastIndex;
      current.push(...next.splice(0, moveCount));
    }
  }
  return result.filter((chunk) => chunk.length > 0);
};

const splitUntilFits = (chunk: number[], tokens: RawToken[]): number[][] => {
  if (chunk.length <= 1 || layoutLines(chunk.map((index) => tokens[index]!))) {
    return [chunk];
  }
  const half = Math.ceil(chunk.length / 2);
  return [...splitUntilFits(chunk.slice(0, half), tokens), ...splitUntilFits(chunk.slice(half), tokens)];
};

const mergeShortPages = (chunks: number[][], tokens: RawToken[], maxWordsAt: (startSec: number) => number): number[][] => {
  const pages = chunks.map((chunk) => [...chunk]);
  const startOf = (page: number[]) => tokens[page[0]!]!.start;
  const durationOf = (pageIndex: number) => {
    const page = pages[pageIndex]!;
    const next = pages[pageIndex + 1];
    const end = next ? startOf(next) : tokens[page[page.length - 1]!]!.end;
    return end - startOf(page);
  };
  const fits = (page: number[]) =>
    page.length <= maxWordsAt(startOf(page)) + 1 && layoutLines(page.map((index) => tokens[index]!)) !== null;
  let changed = true;
  while (changed) {
    changed = false;
    for (let pageIndex = 0; pageIndex < pages.length; pageIndex++) {
      const page = pages[pageIndex]!;
      if (durationOf(pageIndex) >= captionRules.minPageSec) {
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

export const buildCaptionPages = (captions: CaptionWord[], accents: string[], hookEndSec: number): CaptionPage[] => {
  const tokens = tokenize(captions);
  const spans = findAccentSpans(tokens, accents);
  const maxWordsAt = (startSec: number) => (startSec < hookEndSec ? captionRules.hookMaxWords : captionRules.bodyMaxWords);

  const chunks = splitIntoPhrases(tokens, hookEndSec).flatMap((phrase) => {
    const maxWords = maxWordsAt(tokens[phrase[0]!]!.start);
    return repairAccentBoundaries(evenChunks(phrase, maxWords), spans).flatMap((chunk) => splitUntilFits(chunk, tokens));
  });

  return mergeShortPages(chunks, tokens, maxWordsAt).map((page) => {
    const firstSpan = page.map((index) => spanOf(spans, index)).find((span) => span !== undefined);
    const pageTokens: PageToken[] = page.map((index) => ({
      ...tokens[index]!,
      accent: firstSpan !== undefined && index >= firstSpan.first && index <= firstSpan.last,
    }));
    const lines = layoutLines(pageTokens) ?? [pageTokens];
    return {
      tokens: pageTokens,
      lines,
      start: pageTokens[0]!.start,
      end: pageTokens[pageTokens.length - 1]!.end,
    };
  });
};
