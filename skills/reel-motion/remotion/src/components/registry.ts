import { defineBeat, type BeatDefinition } from "../lib/beat";
import HookHeadline, { schema as hookHeadlineSchema } from "./beats/HookHeadline";
import DomainChips, { schema as domainChipsSchema } from "./beats/DomainChips";
import TitleSlam, { schema as titleSlamSchema } from "./beats/TitleSlam";
import ProgressRail, { schema as progressRailSchema } from "./beats/ProgressRail";
import CompareCards, { schema as compareCardsSchema } from "./beats/CompareCards";
import IconCrackTiles, { schema as iconCrackTilesSchema } from "./beats/IconCrackTiles";
import Gauge, { schema as gaugeSchema } from "./beats/Gauge";
import LineChart, { schema as lineChartSchema } from "./beats/LineChart";
import EcgFlatline, { schema as ecgFlatlineSchema } from "./beats/EcgFlatline";
import AuthTiles, { schema as authTilesSchema } from "./beats/AuthTiles";
import EnvelopeToSpam, { schema as envelopeToSpamSchema } from "./beats/EnvelopeToSpam";
import Checklist, { schema as checklistSchema } from "./beats/Checklist";
import ShieldSeal, { schema as shieldSealSchema } from "./beats/ShieldSeal";
import LogoPop, { schema as logoPopSchema } from "./beats/LogoPop";
import EndCard, { schema as endCardSchema } from "./beats/EndCard";

export const registry: Record<string, BeatDefinition> = {
  HookHeadline: defineBeat(hookHeadlineSchema, HookHeadline),
  DomainChips: defineBeat(domainChipsSchema, DomainChips),
  TitleSlam: defineBeat(titleSlamSchema, TitleSlam),
  ProgressRail: defineBeat(progressRailSchema, ProgressRail),
  CompareCards: defineBeat(compareCardsSchema, CompareCards),
  IconCrackTiles: defineBeat(iconCrackTilesSchema, IconCrackTiles),
  Gauge: defineBeat(gaugeSchema, Gauge),
  LineChart: defineBeat(lineChartSchema, LineChart),
  EcgFlatline: defineBeat(ecgFlatlineSchema, EcgFlatline),
  AuthTiles: defineBeat(authTilesSchema, AuthTiles),
  EnvelopeToSpam: defineBeat(envelopeToSpamSchema, EnvelopeToSpam),
  Checklist: defineBeat(checklistSchema, Checklist),
  ShieldSeal: defineBeat(shieldSealSchema, ShieldSeal),
  LogoPop: defineBeat(logoPopSchema, LogoPop),
  EndCard: defineBeat(endCardSchema, EndCard),
};
