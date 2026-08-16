#!/usr/bin/env python3
"""
Update the test posts in Ghost with proper episode templates.
Uses real episode data from the Luminous PRX feed.
"""

import jwt
import requests
from datetime import datetime, timezone


def get_auth_headers(api_key: str) -> dict:
    """Generate Ghost Admin API auth headers."""
    key_id, secret = api_key.split(':')

    iat = int(datetime.now(timezone.utc).timestamp())
    header = {'alg': 'HS256', 'typ': 'JWT', 'kid': key_id}
    payload = {'iat': iat, 'exp': iat + 300, 'aud': '/admin/'}
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers=header)

    return {
        'Authorization': f'Ghost {token}',
        'Accept-Version': 'v5.0',
        'Content-Type': 'application/json'
    }


def load_transcript(slug: str) -> str:
    """Load transcript from TTBOOK cache."""
    from pathlib import Path
    cache_dir = Path(__file__).parent.parent / 'sample-data' / 'ttbook-cache' / 'luminous'
    transcript_file = cache_dir / f'{slug}_transcript.txt'
    if transcript_file.exists():
        return transcript_file.read_text()
    return None


def format_transcript_html(transcript: str) -> str:
    """Convert transcript text to HTML with speaker formatting."""
    if not transcript:
        return '<p><em>[Transcript not yet available for this episode.]</em></p>'

    lines = transcript.strip().split('\n')
    html_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Format speaker attribution: "- [Speaker]" -> "<p><strong>Speaker:</strong>"
        if line.startswith('- ['):
            # Find speaker name between [ and ]
            bracket_end = line.find(']')
            if bracket_end > 3:
                speaker = line[3:bracket_end]
                content = line[bracket_end + 1:].strip()
                html_lines.append(f'<p><strong>{speaker}:</strong> {content}</p>')
            else:
                html_lines.append(f'<p>{line}</p>')
        else:
            html_lines.append(f'<p>{line}</p>')

    return '\n'.join(html_lines)


def build_luminous_html() -> str:
    """Build HTML template for Luminous episode with real transcript."""
    # Using Melissa Etheridge episode which has a full transcript
    transcript = load_transcript('luminous-melissa-etheridge-ayahuasca')
    transcript_html = format_transcript_html(transcript)

    return f'''
<div class="episode-header">
<p class="episode-meta"><strong>Duration:</strong> 24:35 | <strong>Original Air Date:</strong> October 2023</p>
</div>

<div class="episode-player">
<figure class="kg-card kg-audio-card">
<audio controls preload="metadata" style="width: 100%;">
<source src="https://dts.podtrac.com/redirect.mp3/dovetail.prxu.org/3329/luminous-melissa-etheridge.mp3" type="audio/mpeg">
Your browser does not support the audio element.
</audio>
</figure>
<p class="listen-links"><a href="https://www.ttbook.org/show/luminous-melissa-etheridge-ayahuasca" target="_blank">Listen on TTBOOK.org</a> | <a href="https://link.chtbl.com/TTBOOK">Subscribe to the podcast</a></p>
</div>

<hr>

<div class="episode-content">
<p>Melissa Etheridge recently stopped by the Usona Institute, which is running clinical trials on psilocybin and 5-MeO-DMT. Steve Paulson sat down with her to talk about the death of her son from an opioid overdose, her own life-changing experiences with ayahuasca, and why she is fascinated by psychedelics as both a path for spiritual exploration and a source of creativity.</p>

<h3>Guest</h3>
<p><strong>Melissa Etheridge</strong> — Singer, songwriter, and founder of the Etheridge Foundation, which supports scientific research on opioid drug addiction.</p>

<h3>About Luminous</h3>
<p><em>Luminous</em> is a podcast series from <em>To The Best Of Our Knowledge</em> featuring conversations about psychedelics with scientists, healers and religious scholars. Executive producer Steve Paulson explores the philosophical and cultural implications of the psychedelic renaissance.</p>
<p>For more from Luminous: <a href="https://www.ttbook.org/luminous"><strong>ttbook.org/luminous</strong></a></p>
</div>

<hr>

<div class="episode-transcript">
<h2>Full Transcript</h2>
{transcript_html}
</div>

<hr>

<div class="episode-footer">
<p><em>Never want to miss an episode?</em> <a href="https://link.chtbl.com/TTBOOK"><strong>Subscribe to the podcast.</strong></a></p>
<p><em>Want to hear more from us?</em> <a href="https://ttbook.us11.list-manage.com/subscribe/post?u=3cb4c021b28e511db7dc0b1ca&amp;id=64562fd7d9"><strong>Subscribe to our newsletter.</strong></a></p>
</div>
'''


def build_wonder_cabinet_html() -> str:
    """Build HTML template for Wonder Cabinet episode (from TTBOOK main feed)."""
    return '''
<div class="episode-header">
<p class="episode-meta"><strong>Duration:</strong> 52:02 | <strong>Original Air Date:</strong> September 13, 2025</p>
</div>

<div class="episode-player">
<figure class="kg-card kg-audio-card">
<audio controls preload="metadata" style="width: 100%;">
<source src="https://dts.podtrac.com/redirect.mp3/mgln.ai/e/48/dovetail.prxu.org/_/120/f49f790d-b51d-4fab-8201-53f67d7f09b2/tbk250913a0.mp3" type="audio/mpeg">
Your browser does not support the audio element.
</audio>
</figure>
<p class="listen-links"><a href="https://www.ttbook.org/show/giving" target="_blank">Listen on TTBOOK.org</a> | <a href="https://link.chtbl.com/TTBOOK">Subscribe to the podcast</a></p>
</div>

<hr>

<div class="episode-content">
<p>We get the message before we're out of training pants — when the going gets tough, look on the bright side, make lemonade out of lemons and just do it. We're going to consider the exact opposite — the wisdom of giving up and letting go. Because sometimes, the strongest and most courageous thing you can do is walk away.</p>

<h3>Interviews In This Hour</h3>
<ul>
<li><a href="https://www.ttbook.org/interview/boundary-breaking-power-fasting"><strong>The boundary-breaking power of fasting</strong></a></li>
<li><a href="https://www.ttbook.org/interview/how-do-we-know-when-call-it-quits"><strong>How do we know when to call it quits?</strong></a></li>
<li><a href="https://www.ttbook.org/interview/escaping-tyranny-certainty"><strong>Escaping the tyranny of certainty</strong></a></li>
</ul>

<h3>Guests</h3>
<ul>
<li><strong><a href="https://www.ttbook.org/people/john-oakes">John Oakes</a></strong></li>
<li><strong><a href="https://www.ttbook.org/people/adam-phillips">Adam Phillips</a></strong></li>
<li><strong><a href="https://www.ttbook.org/people/maggie-jackson">Maggie Jackson</a></strong></li>
</ul>

<h3>About To The Best Of Our Knowledge</h3>
<p><em>To the Best of Our Knowledge</em> is a Peabody award-winning national public radio show that explores big ideas and beautiful questions. Deep interviews with philosophers, writers, artists, scientists, historians, and others help listeners find new sources of meaning, purpose, and wonder in daily life.</p>
<p>For more: <a href="https://ttbook.org"><strong>ttbook.org</strong></a></p>
</div>

<hr>

<div class="episode-transcript">
<h2>Transcript</h2>
<p><em>[Transcript not yet available for this episode. When transcripts are provided in the RSS feed, they will appear here automatically.]</em></p>

<details>
<summary><strong>Sample Transcript Format (click to expand)</strong></summary>
<p><strong>Anne Strainchamps:</strong> From Wisconsin Public Radio and PRX, this is To The Best Of Our Knowledge. I'm Anne Strainchamps.</p>
<p><strong>Steve Paulson:</strong> And I'm Steve Paulson. Today we're exploring the wisdom of giving up...</p>
<p><strong>John Oakes:</strong> There's something profound about choosing to let go. It's not weakness — it's a different kind of strength...</p>
</details>
</div>

<hr>

<div class="episode-footer">
<p><em>Never want to miss an episode?</em> <a href="https://link.chtbl.com/TTBOOK"><strong>Subscribe to the podcast.</strong></a></p>
<p><em>Want to hear more from us?</em> <a href="https://ttbook.us11.list-manage.com/subscribe/post?u=3cb4c021b28e511db7dc0b1ca&amp;id=64562fd7d9"><strong>Subscribe to our newsletter.</strong></a></p>
</div>
'''


def update_post(base_url: str, headers: dict, post_id: str, update_data: dict) -> bool:
    """Update a Ghost post."""
    # Get current post for updated_at
    resp = requests.get(f'{base_url}/ghost/api/admin/posts/{post_id}/', headers=headers)
    if resp.status_code != 200:
        print(f"Error getting post {post_id}: {resp.status_code}")
        return False

    current_post = resp.json()['posts'][0]
    update_data['updated_at'] = current_post['updated_at']

    # Update post - use source=html to tell Ghost we're providing HTML content
    resp = requests.put(
        f'{base_url}/ghost/api/admin/posts/{post_id}/?source=html',
        headers=headers,
        json={'posts': [update_data]}
    )

    if resp.status_code == 200:
        print(f"Updated: {resp.json()['posts'][0]['title']}")
        return True
    else:
        print(f"Error updating post: {resp.status_code}")
        print(resp.text)
        return False


def main():
    # Configuration
    api_key = '695986a3fd51b4640fe0a714:1a2b9fb8986fe7d5b31753f8cb37d2ff809fb03c676ec19e59a2abd98ee7bd6a'
    base_url = 'http://192.168.5.156:2368'

    headers = get_auth_headers(api_key)

    # Update Luminous test post with Melissa Etheridge episode (has full transcript)
    luminous_post_id = '6959871cfd51b4640fe0a71d'
    luminous_data = {
        'title': 'Luminous: Melissa Etheridge on Ayahuasca',
        'html': build_luminous_html(),
        'custom_excerpt': 'Steve Paulson talks with Melissa Etheridge about the death of her son from an opioid overdose, her own life-changing experiences with ayahuasca, and why she is fascinated by psychedelics.',
        'feature_image': 'https://f.prxu.org/3329/images/d73402a7-a0b0-449c-a697-829d745953dd/TTBOOK_Podcast_luminous_FINAL.png',
        'canonical_url': 'https://www.ttbook.org/show/luminous-melissa-etheridge-ayahuasca',
        'tags': [{'name': 'Luminous'}, {'name': 'Psychedelics'}, {'name': 'Ayahuasca'}, {'name': 'TTBOOK'}]
    }
    update_post(base_url, headers, luminous_post_id, luminous_data)

    # Update Wonder Cabinet test post
    wonder_cabinet_post_id = '69598709fd51b4640fe0a717'
    wonder_cabinet_data = {
        'title': 'Giving Up',
        'html': build_wonder_cabinet_html(),
        'custom_excerpt': 'We get the message before we are out of training pants — when the going gets tough, look on the bright side. But sometimes, the strongest and most courageous thing you can do is walk away.',
        'feature_image': 'https://f.prxu.org/120/f49f790d-b51d-4fab-8201-53f67d7f09b2/images/02f59e40-4026-442e-a549-733fdb63ad19/Giving_Up_-_Podcast_Art.png',
        'canonical_url': 'https://www.ttbook.org/show/giving',
        'tags': [{'name': 'TTBOOK'}, {'name': 'Philosophy'}, {'name': 'Wonder Cabinet'}]
    }
    update_post(base_url, headers, wonder_cabinet_post_id, wonder_cabinet_data)

    print("\nDone! Check Ghost Admin to preview the updated posts.")


if __name__ == '__main__':
    main()
