# audio2anki — audio flashcards, no SRT, no API, no nothing.

![image](https://github.com/user-attachments/assets/e7667553-a3d5-4734-83fa-875410bd7f91)

**audio2anki** turns any audio file or YouTube URL into an Anki flashcard deck (`.apkg`) where each card pairs a short audio clip with its transcript text. Nothing is sent to any cloud API — Whisper transcription and audio processing both run **entirely locally**. The only network call is the YouTube download itself.

Useful for language learners, podcast students, or anyone who wants to study audio alongside text.

## Install

You only need [`uv`](https://docs.astral.sh/uv/). Then:

```bash
uv tool install --with openai-whisper "audio2anki @ git+https://github.com/hiAndrewQuinn/audio2anki"
```

That's it. `audio2anki` is now on your `$PATH` from any directory and bundles **everything** it needs: `yt-dlp`, `openai-whisper`, plus auto-downloads of `ffmpeg`/`ffprobe` and a JavaScript runtime (`deno`) on first use. No system-level prereqs beyond `uv` itself.

Bundled binaries are preferred over any system installs of the same tools, so behavior stays consistent across machines.

### Windows

The same install command works. A few first-time gotchas:

- If `audio2anki` isn't recognized after install, run `uv tool update-shell` (or restart your shell) so `uv`'s tool directory ends up on `PATH`.
- First YouTube run downloads ~85 MB total (ffmpeg ~50 MB + deno ~35 MB) into `%LOCALAPPDATA%`. Windows Defender / SmartScreen occasionally flag fresh GitHub-release binaries — if a subprocess fails with a missing-file error right after install, allow the binary in your AV settings.
- Behind a corporate proxy, set `HTTPS_PROXY` before the first YouTube run so the Deno download can reach GitHub.

## Use

```bash
# YouTube URL — downloads audio, transcribes, builds deck
audio2anki "https://www.youtube.com/watch?v=fJ6ASXsx-nA"

# Local audio file — transcribes (if no .tsv exists), builds deck
audio2anki path/to/audio.mp3

# Local audio + existing Whisper TSV — just builds the deck
audio2anki path/to/audio.mp3 path/to/transcript.tsv
```

The `.apkg` lands in your current directory. Language is auto-detected, so you'll get Spanish subtitles for a Spanish clip, Finnish for a Finnish clip, etc.

![image](https://github.com/user-attachments/assets/6c5c7d77-dd03-4a76-ad55-36d5fb198861)

First-run downloads (cached afterward, all done automatically):

- Whisper model (~1.5 GB for the default `turbo` model)
- `ffmpeg` + `ffprobe` v8 (~50 MB, via `static-ffmpeg`)
- `deno` (~35 MB, only if you use a YouTube URL)

## Options

| Flag | What it does |
|---|---|
| `--whisper` | Force re-transcribing with Whisper, even if a `.tsv` already exists |
| `--whisper-model NAME` | Pick a Whisper model (default: `turbo`; options: `tiny`, `base`, `small`, `medium`, `large`, `turbo`) |
| `--deck-name NAME` | Override the auto-derived deck name |
| `--slow` / `--slower` / `--slowest` | Render audio at 0.75× / 0.5× / 0.25× (pitch preserved). The slower it gets, the more echo-ey it sounds — that's how time-stretching math works. |
| `--audio-dir PATH` | Where to save clip MP3s (default: `clips`) |
| `--transcripts-dir PATH` | Where to look for / save transcripts (default: `transcripts`) |
| `--output-apkg PATH` | Output filename (default: auto-derived from the audio filename) |
| `--youtube URL` | Explicit YouTube URL flag (positional URL works too) |

## YouTube notes

YouTube uses a JavaScript "n-challenge" signature scheme that `yt-dlp` needs a JS runtime to solve. audio2anki **auto-downloads [Deno](https://deno.land/) on first YouTube use** (~35MB, cached at `~/.cache/audio2anki/deno`) so this just works — no manual install. If you already have `deno` on `$PATH`, that one is used instead.

Beyond that, audio2anki tries the default player client first and then falls back through `tv → ios → web_safari → android_vr → mweb` if YouTube has broken the default extraction path for that client. If every client fails, it prints `--list-formats` output for diagnosis.

For age-gated or subscription videos, set `BROWSER=firefox` (or `chrome`, `chromium`, etc.) in a `.env` file in your working directory. `yt-dlp` will pull cookies from that browser.

## Develop

```bash
git clone https://github.com/hiAndrewQuinn/audio2anki
cd audio2anki
uv sync --extra whisper
uv run audio2anki "https://www.youtube.com/watch?v=fJ6ASXsx-nA"
```

## License

[Unlicense](LICENSE). Do whatever you want with it.
