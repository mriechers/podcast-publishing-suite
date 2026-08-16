import { z } from "zod";

/**
 * Schema for a single layer in the video template stack.
 * Layers render bottom-to-top (index 0 = back).
 */
export const LayerDefSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("solid"),
    color: z.string().regex(/^#[0-9a-fA-F]{6}$/, "Must be a hex color (e.g. #2d8c46)"),
    grain: z.boolean().optional(),
  }),
  z.object({
    type: z.literal("spiral"),
    asset: z.string(),
    rotationSpeed: z.number().optional(),
    opacity: z.number().min(0).max(1).optional(),
  }),
  z.object({
    type: z.literal("cabinet-frame"),
    asset: z.string(),
    artClip: z.boolean().optional(),
  }),
  z.object({
    type: z.literal("title-image"),
    asset: z.string(),
    layout: z.enum(["flanking", "stacked"]),
    leftAsset: z.string().optional(),
    rightAsset: z.string().optional(),
  }),
]);

export type LayerDef = z.infer<typeof LayerDefSchema>;

export const OrientationSchema = z.object({
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  layers: z.array(LayerDefSchema).min(1),
});

export type OrientationConfig = z.infer<typeof OrientationSchema>;

export const TemplateConfigSchema = z.object({
  name: z.string(),
  show: z.string(),
  fps: z.number().int().positive().default(30),
  horizontal: OrientationSchema,
  vertical: OrientationSchema,
});

export type TemplateConfig = z.infer<typeof TemplateConfigSchema>;
