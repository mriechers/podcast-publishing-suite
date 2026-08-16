/**
 * youtube-auth-only.ts
 *
 * Runs the YouTube OAuth flow only — no upload. Writes `.youtube-token.json`
 * and exits. Use this for first-time setup on a new machine.
 *
 * The companion `youtube-upload.ts` does auth as a side-effect of uploading,
 * but its main() requires a video file argument, so it can't be used for
 * "auth setup only" without a fake upload attempt that burns API quota.
 *
 * Usage:
 *   npx tsx src/automation/youtube-auth-only.ts
 */

import { config } from "dotenv";
import { google } from "googleapis";
import * as http from "http";
import * as fs from "fs";
import * as path from "path";
import { URL } from "url";

config();

const TOKEN_PATH = path.join(__dirname, "../../.youtube-token.json");
// Broad scope: youtube.upload covers videos.insert/thumbnails/playlists;
// youtube.force-ssl additionally covers captions.insert (SRT upload) +
// transcript management. Minted together so one consent serves the full
// export pipeline (upload + captions). See planning/wc_youtube_metadata_design.md.
const SCOPES = [
  "https://www.googleapis.com/auth/youtube.upload",
  "https://www.googleapis.com/auth/youtube.force-ssl",
];

function createOAuth2Client() {
  const clientId = process.env.YOUTUBE_CLIENT_ID;
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET;
  const redirectUri = process.env.YOUTUBE_REDIRECT_URI || "http://localhost:3000/oauth2callback";

  if (!clientId || !clientSecret) {
    throw new Error("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env");
  }
  if (clientId.startsWith("your-") || clientSecret.startsWith("your-")) {
    throw new Error(".env still has placeholder credential values — replace YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET with real values from Google Cloud Console.");
  }

  return new google.auth.OAuth2(clientId, clientSecret, redirectUri);
}

async function getNewToken(oauth2Client: ReturnType<typeof createOAuth2Client>): Promise<void> {
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    prompt: "consent",
  });

  console.log("\nOpen this URL in your browser to authorize:\n");
  console.log(authUrl);
  console.log("");
  console.log("Waiting for authorization callback on port 3000...");

  return new Promise((resolve, reject) => {
    const server = http.createServer(async (req, res) => {
      try {
        const url = new URL(req.url || "", `http://localhost:3000`);
        const code = url.searchParams.get("code");

        if (code) {
          const { tokens } = await oauth2Client.getToken(code);
          oauth2Client.setCredentials(tokens);
          fs.writeFileSync(TOKEN_PATH, JSON.stringify(tokens, null, 2));

          res.writeHead(200, { "Content-Type": "text/html" });
          res.end("<h1>Authorization successful</h1><p>You can close this window and return to the terminal.</p>");

          server.close();
          console.log(`\nToken saved to ${TOKEN_PATH}`);
          resolve();
        } else {
          res.writeHead(400);
          res.end("No authorization code received");
          reject(new Error("No authorization code received"));
        }
      } catch (err) {
        res.writeHead(500);
        res.end("Authorization failed");
        reject(err);
      }
    });

    server.listen(3000);
  });
}

async function main() {
  if (fs.existsSync(TOKEN_PATH)) {
    console.log(`Token already exists at ${TOKEN_PATH}`);
    console.log("Delete it and re-run if you need to re-authorize.");
    process.exit(0);
  }

  const oauth2Client = createOAuth2Client();
  await getNewToken(oauth2Client);
  console.log("Done.");
}

main().catch((err) => {
  console.error("Auth failed:", err.message || err);
  process.exit(1);
});
