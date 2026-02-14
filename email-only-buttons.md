# Email-Only "Listen Now" Buttons for Existing Episodes

These are the Lexical HTML card nodes to add to each episode. Insert them after the opening audio player card (which should also have its visibility updated to hide from email).

---

## Carlo Rovelli: Cosmic Mysteries and the Politics of Wonder

**Episode URL:** `https://wondercabinetproductions.com/carlo-rovelli-cosmic-mysteries-and-the-politics-of-wonder/`

### Lexical node to insert:

```json
{
  "type": "html",
  "version": 1,
  "html": "<div style=\"text-align: center; margin: 24px 0;\"><a href=\"https://wondercabinetproductions.com/carlo-rovelli-cosmic-mysteries-and-the-politics-of-wonder/\" style=\"display: inline-block; background-color: #10A544; color: #ffffff; font-family: Jost, sans-serif; font-size: 16px; font-weight: 600; text-decoration: none; padding: 12px 32px; border-radius: 4px;\">Listen to this episode →</a></div>",
  "visibility": {
    "web": {
      "nonMember": false,
      "memberSegment": ""
    },
    "email": {
      "memberSegment": "status:free,status:-free"
    }
  }
}
```

### Raw HTML (for Ghost Admin paste):

```html
<div style="text-align: center; margin: 24px 0;"><a href="https://wondercabinetproductions.com/carlo-rovelli-cosmic-mysteries-and-the-politics-of-wonder/" style="display: inline-block; background-color: #10A544; color: #ffffff; font-family: Jost, sans-serif; font-size: 16px; font-weight: 600; text-decoration: none; padding: 12px 32px; border-radius: 4px;">Listen to this episode →</a></div>
```

---

## Sophie Strand: Ecological Storytelling and Mythic Imagination

**Episode URL:** `https://wondercabinetproductions.com/sophie-strand-ecological-storytelling-and-mythic-imagination/`

### Lexical node to insert:

```json
{
  "type": "html",
  "version": 1,
  "html": "<div style=\"text-align: center; margin: 24px 0;\"><a href=\"https://wondercabinetproductions.com/sophie-strand-ecological-storytelling-and-mythic-imagination/\" style=\"display: inline-block; background-color: #10A544; color: #ffffff; font-family: Jost, sans-serif; font-size: 16px; font-weight: 600; text-decoration: none; padding: 12px 32px; border-radius: 4px;\">Listen to this episode →</a></div>",
  "visibility": {
    "web": {
      "nonMember": false,
      "memberSegment": ""
    },
    "email": {
      "memberSegment": "status:free,status:-free"
    }
  }
}
```

### Raw HTML (for Ghost Admin paste):

```html
<div style="text-align: center; margin: 24px 0;"><a href="https://wondercabinetproductions.com/sophie-strand-ecological-storytelling-and-mythic-imagination/" style="display: inline-block; background-color: #10A544; color: #ffffff; font-family: Jost, sans-serif; font-size: 16px; font-weight: 600; text-decoration: none; padding: 12px 32px; border-radius: 4px;">Listen to this episode →</a></div>
```

---

## How to add in Ghost Admin

1. Open the post in Ghost Admin
2. Add an HTML card where you want the button (typically right after the audio player position, before the episode description)
3. Paste the raw HTML
4. Click the card settings (gear icon) or use the visibility toggle
5. Set **Web** visibility to "Hidden"
6. Set **Email** visibility to "All members" or "Everyone"

Note: Ghost's visual editor may show this as the card visibility UI rather than requiring raw JSON editing.
