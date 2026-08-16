# PRX/Dovetail RSS Feed Structure Analysis

## Feed Access Status

**Attempted Feed URL:** https://f.prxu.org/3329/feed-rss.xml
**Access Result:** 403 Forbidden
**Analysis Date:** 2025-11-14

### Access Restrictions

The specified PRX feed returned "Access denied" (HTTP 403) when accessed via:
- Python urllib with user agent
- curl with podcast-compatible user agent
- Crawl4AI browser automation
- WebFetch tool

**Possible Reasons:**
1. **Private/Unpublished Feed** - The feed may not be publicly accessible yet
2. **Authentication Required** - Some PRX feeds require API keys or OAuth
3. **Geo-restrictions** - Feed may be restricted by region
4. **Feed ID Incorrect** - The feed ID (3329) may not exist or may have changed
5. **Cloudflare/WAF Protection** - Advanced bot detection blocking automated access

**Recommendation:** Verify the feed URL is publicly accessible by:
- Opening the URL in a web browser
- Checking PRX Dovetail dashboard for the correct RSS feed URL
- Confirming the podcast is published and the feed is active
- Checking if authentication credentials are needed

---

## Expected PRX/Dovetail Feed Structure

Based on PRX's Dovetail platform documentation and standard podcast RSS 2.0 structure, here's what we would typically expect to find:

### Standard RSS 2.0 Elements

#### Channel-Level Metadata

| Element | Description | Example | Usage for Ghost |
|---------|-------------|---------|-----------------|
| `<title>` | Podcast title | "Example Podcast" | Blog title/author |
| `<description>` | Podcast description | "A show about..." | Bio/About section |
| `<link>` | Podcast website URL | https://example.org | Reference link |
| `<language>` | Primary language | en-us | Content language |
| `<copyright>` | Copyright notice | © 2025 Example Media | Attribution |
| `<managingEditor>` | Editor email | editor@example.org | - |
| `<webMaster>` | Webmaster email | tech@example.org | - |
| `<pubDate>` | Feed publish date | Mon, 14 Nov 2025 12:00:00 GMT | - |
| `<lastBuildDate>` | Last updated | Mon, 14 Nov 2025 12:00:00 GMT | - |
| `<generator>` | Feed generator | PRX Dovetail | - |
| `<image>` | Podcast artwork | URL to image | Featured image |

#### Item-Level Metadata (Per Episode)

| Element | Description | Example | Usage for Ghost Post |
|---------|-------------|---------|---------------------|
| `<title>` | Episode title | "Episode 1: Introduction" | **Post title** |
| `<description>` | Episode description | "In this episode..." | **Post excerpt/summary** |
| `<link>` | Episode webpage | https://example.org/ep1 | Canonical URL |
| `<guid>` | Unique identifier | prx:3329:episode:12345 | Track published episodes |
| `<pubDate>` | Publication date | Mon, 14 Nov 2025 09:00:00 GMT | **Post publish date** |
| `<enclosure>` | Audio file | URL, length, type | Audio player embed |
| `<author>` | Episode author | author@example.org | Ghost author |

### iTunes/Apple Podcasts Namespace (itunes:)

PRX feeds typically include iTunes-specific metadata:

| Element | Description | Example | Usage for Ghost |
|---------|-------------|---------|-----------------|
| `<itunes:title>` | iTunes title | "Episode 1" | Alternative title |
| `<itunes:subtitle>` | Subtitle | "An introduction" | Post subtitle |
| `<itunes:summary>` | Full summary | Long description | **Post content preview** |
| `<itunes:author>` | Show author | "Jane Podcaster" | Ghost author name |
| `<itunes:duration>` | Episode length | 00:45:30 | Display in post |
| `<itunes:explicit>` | Explicit content | yes/no/clean | Tag/content warning |
| `<itunes:image>` | Episode artwork | URL | **Post featured image** |
| `<itunes:season>` | Season number | 1 | Tag: "Season 1" |
| `<itunes:episode>` | Episode number | 5 | Tag: "Episode 5" |
| `<itunes:episodeType>` | Type | full/trailer/bonus | Tag or category |
| `<itunes:keywords>` | Keywords | "news, politics" | **Ghost tags** |

### PRX-Specific Elements

PRX Dovetail may include proprietary elements:

| Element | Description | Potential Value |
|---------|-------------|-----------------|
| `<prx:audio>` | PRX audio metadata | Audio file details |
| `<prx:embed>` | Embed code | **PRX player embed HTML** |
| `<prx:id>` | PRX episode ID | Internal PRX identifier |
| `<prx:seriesId>` | Series ID | Internal series identifier |

### Content/Encoded Elements

| Element | Description | Example | Usage for Ghost |
|---------|-------------|---------|-----------------|
| `<content:encoded>` | HTML content | `<![CDATA[<p>Episode notes</p>]]>` | **Post body HTML** |
| `<description>` (with CDATA) | Rich description | `<![CDATA[...]]>` | **Post content** |

### Podcast Namespace (podcast:)

Modern feeds may include the Podcast Namespace elements:

| Element | Description | Example | Usage for Ghost |
|---------|-------------|---------|-----------------|
| `<podcast:transcript>` | Transcript URL/text | URL or embedded text | **Post content/appendix** |
| `<podcast:chapters>` | Chapter markers | JSON URL | Structure post sections |
| `<podcast:person>` | Contributors | Host, guest names | Author/contributor credits |
| `<podcast:season>` | Season info | Structured season data | Tags |
| `<podcast:episode>` | Episode info | Structured episode data | Post metadata |
| `<podcast:funding>` | Support links | Donation URLs | Call-to-action |
| `<podcast:value>` | Value4Value | Payment info | - |

---

## Data Mapping Strategy for Ghost Posts

### Priority 1: Essential Post Fields

These fields are critical for creating a functional Ghost post:

1. **Post Title** ← `<title>` or `<itunes:title>`
2. **Post Content** ← Combination of:
   - `<content:encoded>` (if available)
   - `<itunes:summary>` (full description)
   - `<description>` (fallback)
   - **PRX player embed code**
3. **Publish Date** ← `<pubDate>`
4. **Slug** ← Generated from title or `<guid>`
5. **Featured Image** ← `<itunes:image>` or `<image>`

### Priority 2: Enhanced Metadata

These fields improve the post quality:

6. **Excerpt** ← `<itunes:subtitle>` or truncated description
7. **Tags** ← Combination of:
   - `<itunes:keywords>` (if present)
   - `<category>` elements
   - Season/Episode numbers as tags
   - Episode type (full/trailer/bonus)
8. **Author** ← `<itunes:author>` or `<author>`
9. **Custom Excerpt** ← `<itunes:summary>`

### Priority 3: Optional Enhancements

These fields could be used for advanced features:

10. **Transcript** ← `<podcast:transcript>` (if available)
    - Could be appended to post content
    - Could be a separate section
    - Improves SEO and accessibility
11. **Duration** ← `<itunes:duration>`
    - Display in post metadata
    - Add to excerpt
12. **Season/Episode Numbers** ← `<itunes:season>` and `<itunes:episode>`
    - Format as tags
    - Include in post title
13. **Chapters** ← `<podcast:chapters>`
    - Format as structured content sections
    - Create table of contents
14. **Contributors** ← `<podcast:person>`
    - List in post footer
    - Create contributor index

---

## Empty/Potentially Unused Fields

Based on typical PRX feeds, these fields might be **present but empty** or **not utilized**:

### Likely Empty in Current Feed

1. **`<podcast:transcript>`** - Most podcasts don't provide transcripts yet
   - **Opportunity:** Could be added later, automation should support it
2. **`<podcast:chapters>`** - Chapter markers are less common
   - **Opportunity:** If added, could structure Ghost post into sections
3. **`<podcast:person>`** - Structured contributor data is uncommon
   - **Opportunity:** Guest names could become tags or metadata
4. **`<content:encoded>`** - Many feeds only use `<description>`
   - **Fallback:** Use `<itunes:summary>` or `<description>`
5. **`<itunes:keywords>`** - Often unused or deprecated
   - **Fallback:** Auto-generate tags from title/description

### Fields That May Exist But Are Often Generic

1. **`<link>`** - Often points to main podcast site, not episode page
2. **`<comments>`** - Rarely used in podcast feeds
3. **`<author>`** (email) - Often a generic podcast@ address

---

## PRX Player Embed Code

### Critical Requirement

The most important element for this project is the **PRX player embed code**. This may appear as:

1. **Within `<content:encoded>`** - HTML embed already included
2. **As `<prx:embed>`** - PRX-specific embed element
3. **Constructed from episode ID** - Build embed URL from `<guid>` or PRX ID

### Expected Embed Format

```html
<iframe
  src="https://exchange.prx.org/embed/episodes/{episode_id}"
  width="100%"
  height="200"
  frameborder="0"
  scrolling="no"
  seamless="seamless">
</iframe>
```

Or PRX's newer player:

```html
<div class="prx-embed" data-episode-id="{episode_id}"></div>
<script src="https://exchange.prx.org/embed.js"></script>
```

### Fallback Strategy

If embed code is not in the feed:
1. Extract PRX episode ID from `<guid>` (e.g., `prx:3329:episode:12345`)
2. Construct embed URL: `https://exchange.prx.org/embed/episodes/{episode_id}`
3. Generate embed HTML programmatically

---

## Content Enrichment Opportunities

### From Feed Data

Even if these fields are currently empty, the automation should be designed to leverage them if they become available:

1. **Transcripts** → Full post content or appendix section
   - SEO benefits
   - Accessibility compliance
   - Searchable content
2. **Chapters** → Structured content with headings
   - Jump links
   - Better UX for long episodes
3. **Keywords** → Automatic tagging
   - Content organization
   - Related posts
4. **Season/Episode Metadata** → Structured navigation
   - Series organization
   - Previous/Next episode links

### External Enrichment

Data not in feed but could be added:

1. **Social share images** - Generate from episode artwork
2. **Reading time estimate** - Based on transcript length
3. **Related episodes** - Based on tags/keywords
4. **Sponsor acknowledgments** - From description parsing
5. **Guest bio links** - If mentioned in description

---

## Recommended Feed Analysis Script

Once feed access is restored, run this analysis:

```python
# Pseudo-code for comprehensive feed analysis
feed = parse_feed(url)

for episode in feed.episodes:
    analyze_fields({
        'present_fields': list(episode.keys()),
        'empty_fields': [k for k, v in episode.items() if not v],
        'html_fields': [k for k, v in episode.items() if '<' in str(v)],
        'namespace_usage': detect_namespaces(episode),
        'embed_code_location': find_embed_code(episode),
        'transcript_availability': check_for_transcript(episode),
    })
```

---

## Next Steps

1. **Verify Feed URL** - Confirm the RSS feed is accessible
   - Test in browser: https://f.prxu.org/3329/feed-rss.xml
   - Check PRX Dovetail dashboard for correct URL
   - Verify podcast is published

2. **Obtain Sample Feed** - If URL is correct but protected:
   - Request authentication credentials
   - Download sample XML manually
   - Place in `knowledge/prx/sample-feed.xml`

3. **Run Full Analysis** - Once feed is accessible:
   ```bash
   python3.11 scripts/analyze_prx_feed.py
   ```

4. **Update This Document** - Replace generic analysis with actual feed structure

---

## Reference Documentation

- [RSS 2.0 Specification](https://www.rssboard.org/rss-specification)
- [Apple Podcasts RSS Feed Requirements](https://podcasters.apple.com/support/823-podcast-requirements)
- [Podcast Namespace](https://github.com/Podcast-Standards-Project/PSP-1-Podcast-RSS-Specification)
- [PRX Dovetail Documentation](https://dovetail.prx.org/docs)
- [Google Podcasts RSS Requirements](https://support.google.com/podcast-publishers/answer/9889544)

---

**Status:** Analysis based on standard PRX/podcast feed structure
**Action Required:** Verify feed URL and accessibility
**Last Updated:** 2025-11-14
