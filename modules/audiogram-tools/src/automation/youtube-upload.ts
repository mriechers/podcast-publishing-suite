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
const TOKEN_PATH = ".youtube-token.json";
const SCOPES = ["https://www.googleapis.com/auth/youtube.upload"];

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
async function getAuthenticatedClient(): Promise<ReturnType<typeof createOAuth2Client>> {
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

  // Get authenticated client
  const auth = await getAuthenticatedClient();
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
