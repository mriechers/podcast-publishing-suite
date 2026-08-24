# podcast-publishing-suite

An agentic publishing pipeline for semi-autonomous multi-platform publishing of podcast episodes week to week. Tailored to each podcast's publishing stack, but benefiting from what each show learns and the common structures shared by all podcasts. 

A key development principle for work was **human in the loop** design. No artifact or data is ever generated and distributed to audiences without human review. There's also a priority to use **deterministic outputs** wherever possible — agents are often used to handle exceptions, rather than each step of the process. 

## Pipeline

```
Audio File
  │
  ├─→ modules/podcast-whisper-transcription  (transcribe + diarize)
  │
  ├─→ modules/prx-to-ghost-publisher        (PRX feed → Ghost CMS)
  │
  └─→  modules/audiogram-tools               (video audiograms)
  
```
## Roles
- Producer - audio producer/talent focused on content of program
- Operator - digital producer/technologist comfortable with Claude or other similar agentic systems
- Agent - AI that drives autonomous or interactive parts of pipeline via skills. Designed around Claude, adaptable to other systems. 

## Overall workflow features
- Standardized show structure (the fact that the workflow enforces this is actually huge for archiving!)
- Slack alerts for each step of pipeline

## Proven Workflows

### [Wonder Cabinet Productions](https://wondercabinetproductions.com)
Two podcasts, Wonder Cabinet and Luminous. 

| Step | Platform | Who drives? |
|--------|-------------|-------|
| Pre-Production | Google Drive (via API) | Producers |
| Transcription, Metadata, Timestamps | [WhisperX](https://github.com/m-bain/whisperx) (with per-show glossary)| Agent |
| Show Art | Custom Art Generator with Unsplash API hooks (could be generalized, TBD) | Agent/Producer Collab |
| Podcast Distribution | [PRX Dovetail](https://dovetail.prx.org) | Operator led, Agent Assists |
| Website Distribution | [Ghost](https://ghost.org) | Agent led, operator assists |
| Audio Waveform Generation/Custom Video Version | [Remotion](https://github.com/remotion-dev/remotion) | Agent led, operator assists |

## Pending Work
- Improved and generalized documentation - what works, what doesn't.
- Firming up video pipeline to support clipping/shorts
- Producer analytics dashboard
- Other content publishing workflows - newsletters, social

## Future direction
This project was at least partially sparked by the question of how much of podcast publishing even COULD be automated without sacrificing on quality or producer authorship, and has thus been pretty slow and steady, relying on iteration and extensive review of session transcripts to identify problems and refinements. We are way beyond viable but spinning this up and operating it week to week still has a pretty high skill ceiling, so work will continue to trend toward giving producers more direct control over each step in the chain, rather than handing it off to an operator — eventually, the agent would be their primary week to week collaborator, with an operator managing many agents that are each supporting their own production team. 
