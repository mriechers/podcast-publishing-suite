/**
 * YouTube Upload Integration
 *
 * Uploads rendered videos to YouTube using the Data API v3.
 *
 * Setup:
 * 1. Create a project in Google Cloud Console
 * 2. Enable YouTube Data API v3
 * 3. Create OAuth 2.0 credentials (Desktop app)
 * 4. Download credentials and save as .youtube-credentials.json
 * 5. Run this script once to authenticate (opens browser)
 * 6. Token is saved to .youtube-token.json for future use
 *
 * Environment variables (in .env):
 * - YOUTUBE_CLIENT_ID
 * - YOUTUBE_CLIENT_SECRET
 * - YOUTUBE_REDIRECT_URI (default: http://localhost:3000/oauth2callback)
 */

import { google, youtube_v3 } from "googleapis";
import { brand } from "../brand";
import fs from "fs";
import path from "path";
import http from "http";
import url from "url";
import "dotenv/config";

// Configuration
// Anchored to __dirname (src/automation/) so callers from any cwd find the
// same token file. Resolves to modules/audiogram-tools/.youtube-token.json.
const TOKEN_PATH = path.join(__dirname, "..", "..", ".youtube-token.json");
// youtube.upload covers videos.insert + thumbnails.set; youtube.force-ssl is
// additionally required for captions.insert (caption upload). Both are needed
// for end-to-end episode publishing.
const SCOPES = [
  "https://www.googleapis.com/auth/youtube.upload",
  "https://www.googleapis.com/auth/youtube.force-ssl",
];

interface UploadOptions {
  videoPath: string;
  title: string;
  description: string;
  tags?: string[];
  categoryId?: string; // 22 = People & Blogs, 27 = Education
  privacyStatus?: "private" | "unlisted" | "public";
  scheduledStartTime?: string; // ISO 8601 format for scheduled publish
  playlistId?: string;
  thumbnailPath?: string;
  /** Optional pre-authenticated client. If omitted, calls getAuthenticatedClient(). */
  auth?: Awaited<ReturnType<typeof getAuthenticatedClient>>;
}

interface UploadResult {
  videoId: string;
  videoUrl: string;
  title: string;
}

/**
 * Create OAuth2 client from environment variables
 */
function createOAuth2Client() {
  const clientId = process.env.YOUTUBE_CLIENT_ID;
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET;
  const redirectUri = process.env.YOUTUBE_REDIRECT_URI || "http://localhost:3000/oauth2callback";

  if (!clientId || !clientSecret) {
    throw new Error(
      "Missing YouTube credentials. Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env"
    );
  }

  return new google.auth.OAuth2(clientId, clientSecret, redirectUri);
}

/**
 * Load saved tokens from file
 */
function loadTokens(): object | null {
  if (fs.existsSync(TOKEN_PATH)) {
    const content = fs.readFileSync(TOKEN_PATH, "utf-8");
    return JSON.parse(content);
  }
  return null;
}

/**
 * Save tokens to file
 */
function saveTokens(tokens: object): void {
  fs.writeFileSync(TOKEN_PATH, JSON.stringify(tokens, null, 2));
  console.log(`Tokens saved to ${TOKEN_PATH}`);
}

/**
 * Get authorization URL and handle OAuth callback
 */
async function getNewToken(oauth2Client: ReturnType<typeof createOAuth2Client>): Promise<void> {
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    prompt: "consent", // Force consent to get refresh token
  });

  console.log("\n═".repeat(60));
  console.log("YouTube Authorization Required");
  console.log("═".repeat(60));
  console.log("\nOpen this URL in your browser to authorize:");
  console.log(`\n${authUrl}\n`);

  // Start local server to receive OAuth callback
  return new Promise((resolve, reject) => {
    const server = http.createServer(async (req, res) => {
      try {
        const queryParams = url.parse(req.url || "", true).query;
        const code = queryParams.code as string;

        if (code) {
          res.writeHead(200, { "Content-Type": "text/html" });
          res.end(
            "<h1>Authorization successful!</h1><p>You can close this window.</p>"
          );

          const { tokens } = await oauth2Client.getToken(code);
          oauth2Client.setCredentials(tokens);
          saveTokens(tokens);

          server.close();
          resolve();
        } else {
          res.writeHead(400);
          res.end("Authorization failed: No code received");
          server.close();
          reject(new Error("No authorization code received"));
        }
      } catch (error) {
        res.writeHead(500);
        res.end("Authorization failed");
        server.close();
        reject(error);
      }
    });

    server.listen(3000, () => {
      console.log("Waiting for authorization callback on port 3000...");
    });
  });
}

/**
 * Get authenticated OAuth2 client
 */
export async function getAuthenticatedClient(): Promise<ReturnType<typeof createOAuth2Client>> {
  const oauth2Client = createOAuth2Client();

  // Try to load existing tokens
  const tokens = loadTokens();
  if (tokens) {
    oauth2Client.setCredentials(tokens);

    // Set up token refresh handler
    oauth2Client.on("tokens", (newTokens) => {
      const updatedTokens = { ...tokens, ...newTokens };
      saveTokens(updatedTokens);
    });

    return oauth2Client;
  }

  // No tokens, need to authorize
  await getNewToken(oauth2Client);
  return oauth2Client;
}

/**
 * Upload video to YouTube
 */
export async function uploadVideo(options: UploadOptions): Promise<UploadResult> {
  const {
    videoPath,
    title,
    description,
    tags = [],
    categoryId = "27", // Education
    privacyStatus = "private",
    scheduledStartTime,
    thumbnailPath,
    auth: providedAuth,
  } = options;

  // Validate video file exists
  if (!fs.existsSync(videoPath)) {
    throw new Error(`Video file not found: ${videoPath}`);
  }

  console.log("\n═".repeat(60));
  console.log("YouTube Upload");
  console.log("═".repeat(60));
  console.log(`Video: ${path.basename(videoPath)}`);
  console.log(`Title: ${title}`);
  console.log(`Privacy: ${privacyStatus}`);

  // Get authenticated client (use provided client if available to share auth
  // state with sibling calls — avoids stale-closure race in token refresh handler)
  const auth = providedAuth ?? (await getAuthenticatedClient());
  const youtube = google.youtube({ version: "v3", auth });

  // Prepare video metadata
  const requestBody: youtube_v3.Schema$Video = {
    snippet: {
      title,
      description,
      tags,
      categoryId,
    },
    status: {
      privacyStatus,
      selfDeclaredMadeForKids: false,
    },
  };

  // Add scheduled publish time if specified
  if (scheduledStartTime && privacyStatus === "private") {
    requestBody.status!.publishAt = scheduledStartTime;
    requestBody.status!.privacyStatus = "private"; // Must be private for scheduling
  }

  // Upload video
  console.log("\nUploading video...");

  const fileSize = fs.statSync(videoPath).size;
  let uploadedBytes = 0;

  const response = await youtube.videos.insert(
    {
      part: ["snippet", "status"],
      requestBody,
      media: {
        body: fs.createReadStream(videoPath),
      },
    },
    {
      onUploadProgress: (evt) => {
        uploadedBytes = evt.bytesRead;
        const progress = ((uploadedBytes / fileSize) * 100).toFixed(1);
        process.stdout.write(`\rProgress: ${progress}%`);
      },
    }
  );

  const videoId = response.data.id!;
  const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;

  console.log(`\n\n✓ Upload complete!`);
  console.log(`  Video ID: ${videoId}`);
  console.log(`  URL: ${videoUrl}`);

  // Upload thumbnail if provided
  if (thumbnailPath && fs.existsSync(thumbnailPath)) {
    console.log("\nUploading thumbnail...");
    await youtube.thumbnails.set({
      videoId,
      media: {
        body: fs.createReadStream(thumbnailPath),
      },
    });
    console.log("✓ Thumbnail uploaded");
  }

  return {
    videoId,
    videoUrl,
    title,
  };
}

/**
 * Upload an SRT caption track to an existing YouTube video.
 *
 * Uses captions.insert (NOT videos.insert with media). Quota cost is 400 units
 * per call (cheaper than the video upload at 1600 units).
 *
 * @param opts.auth - Optional authenticated OAuth2 client. Pass the same client
 *   used for uploadVideo to avoid re-authenticating + race conditions on the
 *   refresh-token event handler. If omitted, calls getAuthenticatedClient().
 */
export async function uploadCaptions(opts: {
  videoId: string;
  srtPath: string;
  language?: string;  // BCP-47 (e.g. "en")
  name?: string;       // visible track name in YouTube Studio
  auth?: Awaited<ReturnType<typeof getAuthenticatedClient>>;
}): Promise<string> {
  const {
    videoId,
    srtPath,
    language = "en",
    name = "English (auto-generated by WC pipeline)",
    auth: providedAuth,
  } = opts;
  if (!fs.existsSync(srtPath)) throw new Error(`Caption file not found: ${srtPath}`);

  const auth = providedAuth ?? (await getAuthenticatedClient());
  const youtube = google.youtube({ version: "v3", auth });

  console.log(`\nUploading captions: ${path.basename(srtPath)}...`);
  try {
    const response = await youtube.captions.insert({
      part: ["snippet"],
      requestBody: {
        snippet: {
          videoId,
          language,
          name,
          isDraft: false,
        },
      },
      media: {
        mimeType: "application/octet-stream",
        body: fs.createReadStream(srtPath),
      },
    });

    const captionId = response.data.id;
    if (!captionId) {
      throw new Error("captions.insert returned no caption ID");
    }
    console.log(`Captions uploaded: ${captionId}`);
    return captionId;
  } catch (err: unknown) {
    // Gaxios error shape: .status is numeric HTTP status (newer); .code is
    // string-or-number (older). Coerce to number so "403" and 403 both match.
    const rawStatus = (err as { status?: number | string; code?: number | string }).status
      ?? (err as { status?: number | string; code?: number | string }).code;
    if (Number(rawStatus) === 403) {
      throw new Error(
        "Caption upload forbidden (403). The stored OAuth token is likely missing " +
        "the youtube.force-ssl scope. Re-run authorization to refresh scopes:\n" +
        "  cd modules/audiogram-tools && rm .youtube-token.json && npx tsx src/automation/youtube-upload.ts --auth-only"
      );
    }
    throw err;
  }
}

/**
 * Add video to a playlist
 */
export async function addToPlaylist(
  videoId: string,
  playlistId: string
): Promise<void> {
  const auth = await getAuthenticatedClient();
  const youtube = google.youtube({ version: "v3", auth });

  await youtube.playlistItems.insert({
    part: ["snippet"],
    requestBody: {
      snippet: {
        playlistId,
        resourceId: {
          kind: "youtube#video",
          videoId,
        },
      },
    },
  });

  console.log(`✓ Added to playlist: ${playlistId}`);
}

/**
 * Generate YouTube description from episode metadata
 */
export function generateDescription(metadata: {
  guestName: string;
  episodeNumber?: number;
  title?: string;
  showDescription?: string;
}): string {
  const lines: string[] = [];

  if (metadata.title) {
    lines.push(metadata.title);
    lines.push("");
  }

  lines.push(`Guest: ${metadata.guestName}`);

  if (metadata.episodeNumber) {
    lines.push(`Episode ${metadata.episodeNumber}`);
  }

  lines.push("");

  if (metadata.showDescription) {
    lines.push(metadata.showDescription);
    lines.push("");
  }

  lines.push("─".repeat(40));
  lines.push("");
  lines.push(`${brand.show.name}`);
  if (brand.show.tagline) lines.push(brand.show.tagline);
  lines.push("");
  lines.push("Subscribe for more episodes exploring the unknown.");

  return lines.join("\n");
}

/**
 * CLI entry point
 */
async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.includes("--auth-only")) {
    await getAuthenticatedClient();
    console.log("Authentication complete. Token saved to .youtube-token.json");
    return;
  }

  if (args.length === 0) {
    console.log("Usage: npx ts-node youtube-upload.ts <video-path> [title]");
    console.log("");
    console.log("Or import and use programmatically:");
    console.log("  import { uploadVideo } from './youtube-upload';");
    process.exit(1);
  }

  const videoPath = args[0];
  const title = args[1] || path.basename(videoPath, path.extname(videoPath));

  try {
    const result = await uploadVideo({
      videoPath,
      title,
      description: generateDescription({ guestName: "Unknown" }),
      tags: [brand.show.name, "podcast"],
      privacyStatus: "private",
    });

    console.log("\nUpload successful!");
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error("Upload failed:", error);
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  main();
}
