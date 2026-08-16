/**
 * render-thumbnail.ts — CLI wrapper for the WC-Thumbnail Remotion still render.
 *
 * Copies episode art into public/ so Remotion's staticFile() can resolve it,
 * writes props to a temp JSON file to avoid shell-tokenization issues, then
 * spawns `npx remotion still WC-Thumbnail`. Cleans up both temp files on exit.
 *
 * Usage:
 *   npx tsx src/automation/render-thumbnail.ts --art <path> --output <path>
 */

import fs from "fs";
import os from "os";
import path from "path";
import { spawn } from "child_process";

interface ThumbnailOptions {
  artPath: string;
  outputPath: string;
}

function parseArgs(): ThumbnailOptions {
  const args = process.argv.slice(2);
  let artPath = "";
  let outputPath = "";
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--art") artPath = args[++i];
    else if (args[i] === "--output") outputPath = args[++i];
  }
  if (!artPath || !outputPath) {
    console.error("Usage: render-thumbnail.ts --art <path> --output <path>");
    process.exit(1);
  }
  return { artPath, outputPath };
}

async function main() {
  const { artPath, outputPath } = parseArgs();

  const resolvedArt = path.resolve(artPath);
  if (!fs.existsSync(resolvedArt)) {
    throw new Error(`Art file not found: ${resolvedArt}`);
  }

  const publicDir = path.join(__dirname, "../../public");
  if (!fs.existsSync(publicDir)) fs.mkdirSync(publicDir, { recursive: true });

  const artFilename = `thumbnail-art-${Date.now()}${path.extname(artPath)}`;
  const artInPublic = path.join(publicDir, artFilename);
  fs.copyFileSync(resolvedArt, artInPublic);

  const propsFile = path.join(os.tmpdir(), `thumb-props-${Date.now()}.json`);
  fs.writeFileSync(propsFile, JSON.stringify({ episodeArtSrc: artFilename }));

  const cleanup = () => {
    try { fs.unlinkSync(propsFile); } catch {}
    try { fs.unlinkSync(artInPublic); } catch {}
  };

  await new Promise<void>((resolve, reject) => {
    const render = spawn("npx", [
      "remotion", "still", "WC-Thumbnail",
      path.resolve(outputPath),
      `--props=${propsFile}`,
    ], { stdio: "inherit" });
    render.on("close", (code) => {
      cleanup();
      if (code === 0) resolve();
      else reject(new Error(`Thumbnail render failed: ${code}`));
    });
    render.on("error", (err) => { cleanup(); reject(err); });
  });

  console.log(`Thumbnail: ${outputPath}`);
}

main().catch((err) => { console.error(err); process.exit(1); });
