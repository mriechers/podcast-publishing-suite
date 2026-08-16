/**
 * compose-metadata.ts
 *
 * Reads episode artifacts (manifest.json, chapters.md, keywords.md) from an
 * episode folder and returns a ComposedMetadata object ready to pass to
 * uploadVideo() in youtube-upload.ts.
 *
 * YouTube hard limits honoured:
 *   - title: 100 chars
 *   - description: 5000 chars
 *   - tags: 30 tags (API also enforces ~500 total chars across all tags)
 */

import fs from "fs";
import path from "path";
import { z } from "zod";

export interface ComposedMetadata {
  title: string;
  description: string;
  tags: string[];
  categoryId: string;
  privacyStatus: "private" | "unlisted" | "public";
  thumbnailPath?: string;
}

// Minimal manifest shape we consume. Manifests in the wild may have many
// other fields; we only validate what we read here.
const ManifestSchema = z.object({
  episodeNumber: z.union([z.number(), z.string()]).optional(),
  guestName: z.string(),
  title: z.string().optional(),
  ghost: z.object({
    url: z.string().optional(),
    publicUrl: z.string().optional(),
    title: z.string().optional(),
  }).optional(),
});

type Manifest = z.infer<typeof ManifestSchema>;

interface ComposeOpts {
  episodeDir: string;       // shows/wonder-cabinet/episodes/<slug>/
  thumbnailPath?: string;
  privacyStatus?: ComposedMetadata["privacyStatus"];
}

/**
 * YouTube enforces both a per-video tag count limit (~30 effective) and a
 * total-character limit across all tags (~500). Drop tags from the end once
 * either limit is reached.
 */
function truncateTagsByBudget(tags: string[], maxCount: number, maxChars: number): string[] {
  const result: string[] = [];
  let chars = 0;
  for (const tag of tags) {
    if (result.length >= maxCount) break;
    if (chars + tag.length > maxChars) break;
    result.push(tag);
    chars += tag.length;
  }
  return result;
}

export function composeMetadata(opts: ComposeOpts): ComposedMetadata {
  const { episodeDir, thumbnailPath, privacyStatus = "private" } = opts;

  // 1. Read manifest.json
  const manifestPath = path.join(episodeDir, "manifest.json");
  if (!fs.existsSync(manifestPath)) throw new Error(`No manifest at ${manifestPath}`);
  const manifestRaw = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  const manifest: Manifest = ManifestSchema.parse(manifestRaw);

  const epNum = manifest.episodeNumber;
  const guest: string = manifest.guestName;

  // Ghost URL — manifest may use either ghost.url or ghost.publicUrl
  const ghostUrl: string | undefined =
    manifest.ghost?.publicUrl ?? manifest.ghost?.url;

  // 2. Title — pull from manifest.title or manifest.ghost.title if present,
  //    else fall back to a constructed label
  const episodeTitle: string = manifest.title ?? manifest.ghost?.title ?? "";
  const title = episodeTitle
    ? `${guest}: ${episodeTitle}`
    : `${guest} — Wonder Cabinet E${epNum}`;

  // 3. Description — chapters.md (section 3) + ghost link + boilerplate
  const chaptersText = extractYouTubeChapters(path.join(episodeDir, "chapters.md"));
  const description = composeDescription({ guest, episodeTitle, chaptersText, ghostUrl });

  // 4. Tags — keywords.md, one keyword per line
  const tags = readKeywords(path.join(episodeDir, "keywords.md"));

  return {
    title: title.slice(0, 100),
    description: description.slice(0, 5000),
    tags: truncateTagsByBudget(tags, 30, 500),
    categoryId: "27",  // Education
    privacyStatus,
    thumbnailPath,
  };
}

/**
 * Pull the YouTube chapter block from chapters.md.
 *
 * Looks for a section heading matching "## 3. YouTube..." followed by a
 * fenced code block and returns the contents of that block.
 */
function extractYouTubeChapters(chaptersMdPath: string): string {
  if (!fs.existsSync(chaptersMdPath)) return "";
  const text = fs.readFileSync(chaptersMdPath, "utf-8");
  // Match "## 3. YouTube..." heading then the first fenced code block after it
  const match = text.match(/##\s*3\.\s*YouTube[^\n]*\n+```[^\n]*\n([\s\S]*?)\n```/);
  if (!match) return "";
  return match[1].trim();
}

/**
 * Read keywords from keywords.md.
 *
 * Each non-empty, non-comment line is a tag. Lines starting with # are
 * comments. Leading bullet characters (•, *, -) are stripped.
 */
function readKeywords(keywordsMdPath: string): string[] {
  if (!fs.existsSync(keywordsMdPath)) return [];
  return fs.readFileSync(keywordsMdPath, "utf-8")
    .split("\n")
    .map(l => l.trim())
    .filter(l => l && !l.startsWith("#"))   // skip blanks + comments
    .map(l => l.replace(/^[-•*]\s*/, ""))    // strip ANY bullet style
    .filter(l => l.length > 0);              // drop now-empty lines (was just a bullet)
}

function composeDescription(opts: {
  guest: string;
  episodeTitle: string;
  chaptersText: string;
  ghostUrl?: string;
}): string {
  const { guest, episodeTitle, chaptersText, ghostUrl } = opts;
  const parts: string[] = [];

  parts.push(episodeTitle ? `${guest} on Wonder Cabinet — ${episodeTitle}` : guest);
  parts.push("");

  if (chaptersText) {
    parts.push("Chapters:");
    parts.push(chaptersText);
    parts.push("");
  }

  if (ghostUrl) {
    parts.push(`Full episode notes & transcript: ${ghostUrl}`);
    parts.push("");
  }

  parts.push(
    "Subscribe wherever you get your podcasts. Newsletter: https://wondercabinetproductions.com"
  );

  return parts.join("\n");
}

// CLI entry — print composed metadata to stdout for inspection
if (require.main === module) {
  const epDir = process.argv[2];
  if (!epDir) {
    console.error("Usage: npx tsx src/automation/compose-metadata.ts <episode-dir>");
    process.exit(1);
  }
  const md = composeMetadata({ episodeDir: epDir });
  console.log(JSON.stringify(md, null, 2));
}
