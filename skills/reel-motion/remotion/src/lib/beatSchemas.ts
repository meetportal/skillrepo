import { z } from "zod";
import { iconNames } from "../components/ui/Icon";
import { toneNames } from "../components/ui/tone";

export const timeSchema = z.number().min(-0.5);
export const toneSchema = z.enum(toneNames);
export const iconSchema = z.enum(iconNames);
export const markupLineSchema = z.string().min(1);
