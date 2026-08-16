# Theme Liaison Agent To-Do List

**Role:** Coordinate between the PRX-to-Ghost Publisher project and the Ghost theme customization project to ensure both systems are aligned and compatible.

**Projects:**
- **Publisher:** PRX-to-Ghost Publisher (this repo) - automation backend
- **Theme:** Ghost theme customization project - frontend/templates

---

## Critical Alignment Tasks

### Routing & Collections
- [ ] Confirm `routes.yaml` structure with theme team
  - Publisher expects: `/luminous/` and `/wonder-cabinet/` collections
  - Theme must support collection routing via `primary_tag` filter
- [ ] Verify collection URL patterns match between projects
  - Posts: `/luminous/{slug}/` and `/wonder-cabinet/{slug}/`
- [ ] Ensure theme has `podcast.hbs` template for collection pages

### Tag Conventions
- [ ] Align on exact tag names and slugs
  - Primary tags: `luminous`, `wonder-cabinet`
  - Internal tags: `#show-luminous`, `#show-wonder-cabinet`
  - Content tags: `Podcast`, `Season X`, episode types
- [ ] Confirm tag creation in Ghost Admin before go-live
- [ ] Document any additional tags theme expects for styling hooks

### Template Requirements
- [ ] Confirm theme includes these templates:
  - [ ] `podcast.hbs` - show landing/collection pages
  - [ ] `post.hbs` - individual episode pages (or podcast-specific variant)
  - [ ] `index.hbs` - homepage with dual-show sections
- [ ] Verify `episode-card.hbs` partial exists for episode listings
- [ ] Check if theme needs `tag.hbs` customization for show pages

---

## Content Structure Alignment

### Post Fields
- [ ] Document which Ghost post fields the publisher will populate:
  - `title` - Episode title
  - `slug` - Prefixed with show name (e.g., `luminous-episode-title`)
  - `html` - Content with PRX player embed
  - `feature_image` - Episode artwork URL
  - `custom_excerpt` - Episode summary (300 chars)
  - `published_at` - Original publication date
  - `tags` - Array with primary tag first
  - `meta_title`, `meta_description` - SEO fields
- [ ] Confirm theme templates use these fields correctly
- [ ] Identify any additional fields theme expects (custom fields, etc.)

### PRX Player Embed
- [ ] Share PRX player HTML structure with theme team:
  ```html
  <div class="prx-player-container">
    <iframe src="https://exchange.prx.org/embed/episodes/{id}" ...></iframe>
  </div>
  <div class="episode-metadata">...</div>
  <div class="episode-description">...</div>
  ```
- [ ] Confirm theme has CSS for `.prx-player-container` class
- [ ] Verify iframe responsive behavior works with theme
- [ ] Test dark mode compatibility if theme supports it

### Transcript Content (Luminous)
- [ ] Decide on transcript display format
  - Inline in post? Collapsible section? Separate page?
- [ ] Share transcript HTML structure with theme team
- [ ] Confirm CSS styling for transcript speaker attribution

---

## Visual Design Coordination

### Show Branding
- [ ] Confirm show-specific styling approach:
  - Different accent colors per show?
  - Show logos in headers?
  - Distinct collection page layouts?
- [ ] Share any branding assets (logos, colors) between projects
- [ ] Document CSS class conventions for show-specific styling

### Homepage Layout
- [ ] Align on homepage design showing both podcasts
- [ ] Confirm number of episodes to display per show (design doc suggests 3)
- [ ] Verify `{{#get}}` helper usage for filtered episode queries

### Episode Cards
- [ ] Share expected card content structure
- [ ] Confirm image aspect ratios and sizes
- [ ] Align on date format display
- [ ] Verify excerpt length matches theme card design

---

## Technical Integration

### Ghost API Compatibility
- [ ] Confirm Ghost version compatibility between projects
- [ ] Verify Admin API version publisher will use (`v5.0`)
- [ ] Check if theme uses any features requiring specific Ghost version

### Testing Coordination
- [ ] Establish shared test Ghost instance (if available)
- [ ] Create test posts matching publisher output format
- [ ] Verify theme renders test posts correctly
- [ ] Test with actual PRX player embeds

### Deployment Sequence
- [ ] Document deployment order:
  1. Theme uploaded and activated
  2. `routes.yaml` deployed
  3. Tags created in Ghost Admin
  4. Publisher automation enabled
- [ ] Coordinate go-live timing between projects

---

## Documentation Sync

### Shared References
- [ ] Keep both projects updated on:
  - [ ] Feed configuration changes
  - [ ] Tag naming changes
  - [ ] HTML structure changes
  - [ ] CSS class naming conventions
- [ ] Establish communication channel for cross-project updates

### Handoff Documentation
- [ ] Document theme dependencies on publisher output
- [ ] Document publisher assumptions about theme structure
- [ ] Create integration testing checklist

---

## Issue Tracking

### Open Questions for Theme Team
- [ ] _List questions that need answers from theme project_

### Open Questions from Theme Team
- [ ] _List questions theme team has asked about publisher_

### Blocking Dependencies
- [ ] _List items blocking one project waiting on the other_

---

## Completion Criteria

This liaison work is complete when:
- [ ] Both projects agree on all tag names and routing
- [ ] PRX player embed renders correctly in theme
- [ ] Test posts from publisher display correctly in theme
- [ ] Homepage shows episodes from both podcasts
- [ ] Collection pages filter correctly by show
- [ ] Deployment sequence is documented and agreed upon
- [ ] Both teams have reviewed integration points

---

**Last Updated:** 2025-12-31
**Status:** Initial creation - needs review with theme team
