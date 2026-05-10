#!/usr/bin/env python3
"""relabel_speakers.py — map WhisperX SPEAKER_NN clusters to real names via voice-embedding similarity.

Compares each anonymous cluster's mean voice embedding to a set of named reference
reels (e.g. anne.wav, steve.wav) and rewrites the WhisperX output files with the
matched names. Clusters that don't pass the similarity threshold for any reference
are left as their original SPEAKER_NN tag (typically the per-episode guest).

Run with the whisperx pipx venv's Python:
  /Users/mriechers/.local/pipx/venvs/whisperx/bin/python relabel_speakers.py ...
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch
from pyannote.audio import Model, Inference


def parse_reference(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        sys.exit(f"--reference must be NAME=PATH, got: {spec!r}")
    name, path = spec.split("=", 1)
    p = Path(path).expanduser()
    if not p.exists():
        sys.exit(f"reference file not found: {p}")
    return name, p


def load_diarization(json_path: Path) -> dict[str, list[tuple[float, float]]]:
    """Group WhisperX segment timings by speaker label."""
    data = json.loads(json_path.read_text())
    by_speaker: dict[str, list[tuple[float, float]]] = {}
    for seg in data.get("segments", []):
        spk = seg.get("speaker")
        if spk is None:
            continue
        by_speaker.setdefault(spk, []).append((float(seg["start"]), float(seg["end"])))
    return by_speaker


def extract_speaker_audio(
    audio_path: Path,
    segments: list[tuple[float, float]],
    out_path: Path,
    max_seconds: float = 60.0,
) -> float:
    """Concatenate up to max_seconds of audio for one speaker into out_path. Returns total seconds."""
    selected: list[tuple[float, float]] = []
    total = 0.0
    for start, end in segments:
        dur = end - start
        if dur < 0.4:  # skip ultra-short blips that are likely diarization noise
            continue
        if total + dur > max_seconds:
            dur = max_seconds - total
            end = start + dur
        selected.append((start, end))
        total += dur
        if total >= max_seconds:
            break

    if not selected:
        return 0.0

    # Build ffmpeg filter_complex for atrim+concat
    inputs: list[str] = []
    for start, end in selected:
        inputs += ["-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(audio_path)]
    n = len(selected)
    parts = "".join(f"[{i}:a]" for i in range(n))
    filter_complex = f"{parts}concat=n={n}:v=0:a=1[out]"
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ac", "1", "-ar", "16000", "-codec:a", "pcm_s16le",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return total


def _load_wav(path: Path) -> tuple[torch.Tensor, int]:
    """Load a wav file as (channels, samples) float32 tensor + sample_rate.

    Avoids pyannote 4.x's default torchcodec-based loader, which is broken in
    this environment. Falls back from torchaudio → scipy.io.wavfile.
    """
    try:
        import torchaudio
        waveform, sr = torchaudio.load(str(path))
        return waveform.float(), int(sr)
    except Exception:
        from scipy.io import wavfile
        sr, data = wavfile.read(str(path))
        if data.ndim == 1:
            data = data[None, :]
        else:
            data = data.T
        # Normalize ints to float32 [-1, 1]
        if np.issubdtype(data.dtype, np.integer):
            max_val = float(np.iinfo(data.dtype).max)
            data = data.astype(np.float32) / max_val
        return torch.from_numpy(np.ascontiguousarray(data)).float(), int(sr)


def embed(inference: Inference, wav: Path) -> np.ndarray:
    waveform, sr = _load_wav(wav)
    emb = inference({"waveform": waveform, "sample_rate": sr})
    arr = np.asarray(emb)
    # Inference(window="whole") returns a (1, dim) or (dim,) array depending on version
    if arr.ndim == 2:
        arr = arr.mean(axis=0)
    return arr / (np.linalg.norm(arr) + 1e-9)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def rewrite_files(mapping: dict[str, str], paths: list[Path]) -> list[Path]:
    """Apply SPEAKER_NN → real-name substitutions in the listed files. Returns rewritten paths."""
    rewritten: list[Path] = []
    pat = re.compile(r"SPEAKER_(\d+)")

    def repl(m: re.Match) -> str:
        key = f"SPEAKER_{m.group(1)}"
        return mapping.get(key, m.group(0))

    for p in paths:
        if not p.exists():
            continue
        text = p.read_text()
        new_text = pat.sub(repl, text)
        if new_text != text:
            p.write_text(new_text)
            rewritten.append(p)
    return rewritten


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", required=True, type=Path, help="Source audio (mp3/wav)")
    ap.add_argument("--json", required=True, type=Path, help="WhisperX JSON output with per-segment speaker labels")
    ap.add_argument("--reference", action="append", required=True, help='Reference reel: NAME=PATH (repeat per host)')
    ap.add_argument("--threshold", type=float, default=0.5, help="Min cosine similarity to assign a name (default 0.5)")
    ap.add_argument("--max-seconds", type=float, default=60.0, help="Max audio per cluster to embed (default 60s)")
    ap.add_argument("--out-mapping", type=Path, help="Write mapping JSON to this path (default: stdout)")
    ap.add_argument("--apply", nargs="*", type=Path, default=[], help="Files to rewrite in place with the mapping")
    ap.add_argument("--model", default="pyannote/embedding", help="Pyannote embedding model (default: pyannote/embedding)")
    args = ap.parse_args()

    references = dict(parse_reference(s) for s in args.reference)

    by_speaker = load_diarization(args.json)
    if not by_speaker:
        sys.exit(f"No speaker-labeled segments found in {args.json}")

    print(f"Found {len(by_speaker)} speaker cluster(s): {sorted(by_speaker)}", file=sys.stderr)

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    model = Model.from_pretrained(args.model)
    model.to(device)
    inference = Inference(model, window="whole", device=device)

    ref_embeddings: dict[str, np.ndarray] = {}
    for name, path in references.items():
        print(f"  embedding reference: {name} ({path.name})", file=sys.stderr)
        ref_embeddings[name] = embed(inference, path)

    cluster_embeddings: dict[str, np.ndarray] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for spk, segs in sorted(by_speaker.items()):
            wav = tmp_dir / f"{spk}.wav"
            secs = extract_speaker_audio(args.audio, segs, wav, max_seconds=args.max_seconds)
            print(f"  extracted {secs:.1f}s for {spk}", file=sys.stderr)
            if secs < 1.0:
                continue
            cluster_embeddings[spk] = embed(inference, wav)

    rows: list[dict] = []
    mapping: dict[str, str] = {}
    for spk, emb in cluster_embeddings.items():
        sims = {name: cosine(emb, r) for name, r in ref_embeddings.items()}
        best_name, best_sim = max(sims.items(), key=lambda kv: kv[1])
        assigned = best_name if best_sim >= args.threshold else None
        rows.append({"speaker": spk, "similarities": sims, "assigned": assigned})
        if assigned is not None:
            mapping[spk] = assigned

    print("\n=== similarity matrix ===", file=sys.stderr)
    print(f"{'cluster':10s}  " + "  ".join(f"{n[:18]:>18s}" for n in references) + "  → assigned", file=sys.stderr)
    for row in rows:
        sims_str = "  ".join(f"{row['similarities'][n]:>18.3f}" for n in references)
        print(f"{row['speaker']:10s}  {sims_str}  → {row['assigned'] or '(unassigned)'}", file=sys.stderr)

    out = {"mapping": mapping, "details": rows, "threshold": args.threshold}
    if args.out_mapping:
        args.out_mapping.write_text(json.dumps(out, indent=2))
        print(f"\nwrote mapping to {args.out_mapping}", file=sys.stderr)
    else:
        print(json.dumps(out, indent=2))

    if args.apply:
        rewritten = rewrite_files(mapping, args.apply)
        print(f"\nrewrote {len(rewritten)} file(s):", file=sys.stderr)
        for p in rewritten:
            print(f"  {p}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
