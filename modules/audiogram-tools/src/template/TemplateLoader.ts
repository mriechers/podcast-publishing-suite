import fs from "fs";
import path from "path";
import { ZodError } from "zod";
import { TemplateConfigSchema, TemplateConfig } from "./types";

/**
 * Load and validate a show's video template config.
 *
 * @param showSlug - e.g. "wonder-cabinet"
 * @param suiteRoot - path to podcast-publishing-suite root
 * @returns Validated TemplateConfig
 */
export function loadTemplate(
  showSlug: string,
  suiteRoot: string
): TemplateConfig {
  const templatePath = path.join(
    suiteRoot,
    "shows",
    showSlug,
    "video-template",
    "template.json"
  );

  if (!fs.existsSync(templatePath)) {
    throw new Error(
      `Template not found for show "${showSlug}" at ${templatePath}`
    );
  }

  let raw: unknown;
  try {
    raw = JSON.parse(fs.readFileSync(templatePath, "utf-8"));
  } catch (err) {
    throw new Error(
      `Failed to parse template JSON for show "${showSlug}" at ${templatePath}: ${err instanceof Error ? err.message : err}`
    );
  }

  try {
    return TemplateConfigSchema.parse(raw);
  } catch (err) {
    if (err instanceof ZodError) {
      const issues = err.issues
        .map((i) => `  - ${i.path.join(".")}: ${i.message}`)
        .join("\n");
      throw new Error(
        `Template validation failed for show "${showSlug}" at ${templatePath}:\n${issues}`
      );
    }
    throw err;
  }
}

/**
 * Resolve an asset filename to its path in the audiogram-tools images/ directory.
 * Assets referenced in template.json are filenames only (e.g. "bg-galaxy-spiral-1200w@2x.png").
 * They must exist in modules/audiogram-tools/images/.
 */
export function resolveAssetPath(
  assetFilename: string,
  audiogramRoot: string
): string {
  const assetPath = path.join(audiogramRoot, "images", assetFilename);
  if (!fs.existsSync(assetPath)) {
    throw new Error(
      `Asset "${assetFilename}" not found at ${assetPath}`
    );
  }
  return assetPath;
}
