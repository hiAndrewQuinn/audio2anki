#!/usr/bin/env python3

import click
import csv
import os
import random
import hashlib
import subprocess
import shutil
from io import BytesIO
from pydub import AudioSegment
from tqdm import tqdm
import genanki
from dotenv import load_dotenv

# Load environment variables from a .env file if present.
load_dotenv()


@click.command()
@click.argument("audio_file", required=False, type=click.Path(exists=True))
@click.argument("tsv_file", required=False, type=click.Path())
@click.option(
    "--deck-name",
    default=None,
    help="Optional custom deck name. If not provided, derived from MP3 filename.",
)
@click.option(
    "--audio-dir",
    default="clips",
    help="Directory to save audio clips (default: clips)",
)
@click.option(
    "--output-apkg",
    default=None,
    help="Output Anki package file name (default: auto-generated from MP3 file)",
)
@click.option(
    "--transcripts-dir",
    default="transcripts",
    help="Directory where transcripts are stored (default: transcripts)",
)
@click.option(
    "--whisper",
    is_flag=True,
    default=False,
    help="Force generation of transcript using Whisper",
)
@click.option(
    "--whisper-model", default="turbo", help="Whisper model to use (default: turbo)"
)
@click.option(
    "--youtube",
    default=None,
    help="YouTube URL to download MP3 from. Overrides all other options.",
)
def main(
    audio_file,
    tsv_file,
    deck_name,
    audio_dir,
    output_apkg,
    transcripts_dir,
    whisper,
    whisper_model,
    youtube,
):
    """
    Generate an Anki package (.apkg) from an MP3 file and a Whisper-generated TSV transcript.

    If a transcript TSV file is not provided, the script checks the transcripts directory for a file matching
    the audio file name. It performs a basic check on the transcript's duration relative to the audio.
    If no valid transcript is found (or if --whisper is passed), it will generate one using Whisper.

    --youtube flag: If a YouTube URL is provided via --youtube, this branch is taken.
    It will check for yt-dlp, update it, and then download the MP3 audio only
    from the YouTube URL into the youtube/ directory. In this mode, AUDIO_FILE and TSV_FILE are not required.
    After download, the pipeline continues with transcript generation and Anki package creation.
    """
    # If --youtube is provided, override audio_file and tsv_file.
    if youtube:
        click.echo("YouTube URL provided. Overriding all other options.")
        yt_dlp_path = shutil.which("yt-dlp")
        if yt_dlp_path is None:
            click.echo(
                "Error: 'yt-dlp' command not found in PATH. Please install yt-dlp.",
                err=True,
            )
            return

        # Update yt-dlp to the latest version.
        click.echo("Updating yt-dlp...")
        try:
            subprocess.run([yt_dlp_path, "-U"], check=True)
        except subprocess.CalledProcessError:
            click.echo("Warning: yt-dlp update failed.", err=True)

        # Ensure output directory exists.
        youtube_dir = "youtube"
        os.makedirs(youtube_dir, exist_ok=True)

        # Build the download command.
        cmd = [
            yt_dlp_path,
            "-f",
            "bestaudio",
            "--extract-audio",
            "--audio-format",
            "mp3",
        ]
        browser = os.getenv("BROWSER")
        if browser:
            cmd.extend(["--cookies-from-browser", browser])
        cmd.extend(["-o", os.path.join(youtube_dir, "%(title)s.%(ext)s"), youtube])

        click.echo("Downloading MP3 from YouTube...")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            click.echo("Error: Downloading MP3 from YouTube failed.", err=True)
            return
        click.echo("Download complete.")

        # Find the most recent MP3 file in the youtube directory.
        mp3_files = [
            os.path.join(youtube_dir, f)
            for f in os.listdir(youtube_dir)
            if f.endswith(".mp3")
        ]
        if not mp3_files:
            click.echo(
                "Error: No MP3 file found in the youtube directory after download.",
                err=True,
            )
            return
        downloaded_file = max(mp3_files, key=os.path.getmtime)
        click.echo(f"Using downloaded file: {downloaded_file}")
        audio_file = downloaded_file

    # In non-YouTube mode, require an audio_file.
    if not audio_file:
        click.echo(
            "Error: AUDIO_FILE is required when --youtube is not provided.", err=True
        )
        return

    # Ensure output directories exist.
    os.makedirs(transcripts_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    click.echo("Loading the complete audio file...")
    audio = AudioSegment.from_file(audio_file)
    audio_length = len(audio)  # in milliseconds

    # Determine which transcript to use.
    transcript_to_use = None
    # If a transcript file argument is provided and not forcing whisper, use it directly.
    if tsv_file and not whisper:
        transcript_to_use = tsv_file
    else:
        # Construct the expected transcript filename based on the audio file's basename.
        base = os.path.basename(audio_file)
        name, _ = os.path.splitext(base)
        expected_tsv = os.path.join(transcripts_dir, f"{name}.tsv")
        if os.path.exists(expected_tsv):
            # Basic check: does the last segment cover at least 80% of the audio length?
            try:
                with open(expected_tsv, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    rows = list(reader)
                if rows:
                    last_row = rows[-1]
                    last_end = int(float(last_row.get("end", "0")))
                    if last_end < 0.8 * audio_length:
                        click.echo(
                            "Warning: Existing transcript seems to cover less than 80% of the audio length."
                        )
                        # If in YouTube mode, assume transcript generation is desired.
                        if youtube:
                            confirm = True
                        elif not whisper:
                            confirm = click.confirm(
                                "Do you want to use the existing transcript anyway?",
                                default=False,
                            )
                        else:
                            confirm = True
                        transcript_to_use = expected_tsv if confirm else None
                    else:
                        transcript_to_use = expected_tsv
                else:
                    click.echo("Warning: Existing transcript file is empty.")
                    transcript_to_use = None
            except Exception as e:
                click.echo(f"Error reading existing transcript: {e}")
                transcript_to_use = None

        # If no valid transcript was found or if forcing Whisper, then generate one.
        if transcript_to_use is None or whisper:
            # In YouTube mode, automatically generate transcript.
            if youtube:
                confirm = True
            elif not whisper:
                confirm = click.confirm(
                    "No valid transcript found. Do you want to generate one using Whisper? This may take some time.",
                    default=True,
                )
            else:
                confirm = True
            if confirm:
                click.echo(
                    "Generating transcript with Whisper. This may take a while...."
                )
                # Check that the 'whisper' command exists before trying to run it.
                whisper_cmd = shutil.which("whisper")
                if whisper_cmd is None:
                    click.echo(
                        "Error: 'whisper' command not found in PATH. Please install Whisper or adjust your PATH.",
                        err=True,
                    )
                    return

                click.echo(
                    "If you see a downloading bar appear, it means Whisper is downloading its speech-to-text model. This should only happen once."
                )
                # Build the whisper command.
                cmd = [
                    whisper_cmd,
                    audio_file,
                    "--model",
                    whisper_model,
                    "--output_format",
                    "tsv",
                    "--output_dir",
                    transcripts_dir,
                ]
                result = subprocess.run(cmd)
                if result.returncode != 0:
                    click.echo("Error: Whisper transcript generation failed.", err=True)
                    return
                if os.path.exists(expected_tsv):
                    transcript_to_use = expected_tsv
                    click.echo(f"Transcript generated: {expected_tsv}")
                else:
                    click.echo(
                        "Error: Transcript generation completed, but transcript file not found.",
                        err=True,
                    )
                    return
            else:
                click.echo("Transcript generation aborted by user.")
                return

    if transcript_to_use is None:
        click.echo("No transcript available. Exiting.")
        return

    click.echo(f"Using transcript: {transcript_to_use}")

    # Generate deck name if not provided.
    if deck_name:
        deck_title = deck_name
    else:
        base = os.path.basename(audio_file)
        name, _ = os.path.splitext(base)
        name = name.replace("_", " ").replace("-", " ")
        deck_title = f"audio2anki:: {name}"

    # Generate unique IDs for deck and model.
    deck_id = random.randrange(1 << 30, 1 << 31)
    model_id = random.randrange(1 << 30, 1 << 31)

    # Custom CSS for the card.
    css = """
.card {
  font-family: Arial, sans-serif;
  font-size: 40px;
  padding: 20px;
}
.finnish-audio {
  margin-bottom: 15px;
}
.finnish-text {
  font-weight: bold;
  margin-bottom: 10px;
}
.english-text {
  margin-top: 10px;
}

.notes {
  margin-top: 10px;
  font-size: 70%;
  color: #888;
}
"""

    # Create a model with four fields.
    my_model = genanki.Model(
        model_id,
        "Audio2Anki Model",
        fields=[
            {"name": "Finnish (audio)"},
            {"name": "Finnish (text)"},
            {"name": "English (text)"},
            {"name": "notes"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": """
<div class="finnish-audio">{{Finnish (audio)}}</div>
""",
                "afmt": """{{FrontSide}}
<hr id="answer">
<div class="finnish-text">{{Finnish (text)}}</div>
<div class="english-text">{{English (text)}}</div>
<div class="notes">{{notes}}</div>
""",
            },
        ],
        css=css,
    )

    # Create the deck.
    my_deck = genanki.Deck(deck_id, deck_title)

    # Process the transcript TSV rows.
    with open(transcript_to_use, newline="", encoding="utf-8") as tsvfile:
        reader = csv.DictReader(tsvfile, delimiter="\t")
        rows = list(reader)

    # Preprocessing: Stitch together consecutive segments if the text does not end with a full sentence.
    def is_complete_sentence(text):
        text = text.strip()
        # Check for a period, exclamation mark, or question mark at the end.
        return text.endswith(".") or text.endswith("!") or text.endswith("?")

    merged_rows = []
    i = 0
    while i < len(rows):
        current = rows[i]
        merged_start = current["start"]
        merged_end = current["end"]
        merged_text = current["text"].strip()

        # Merge subsequent rows if the current text doesn't end with a sentence terminator.
        while not is_complete_sentence(merged_text) and (i + 1) < len(rows):
            next_row = rows[i + 1]
            merged_end = next_row["end"]
            merged_text += " " + next_row["text"].strip()
            i += 1
        merged_rows.append(
            {"start": merged_start, "end": merged_end, "text": merged_text}
        )
        i += 1

    # Replace rows with the stitched version.
    rows = merged_rows

    click.echo(f"Processing {len(rows)} segments...")
    for row in tqdm(rows, desc="Processing segments", unit="segment"):
        try:
            start_ms = int(float(row["start"]))
            end_ms = int(float(row["end"]))
        except ValueError:
            click.echo("Skipping a segment due to invalid timing.", err=True)
            continue

        text = row["text"]
        # Extend the end by 1 second (1000 ms) without exceeding the audio length,
        # and apply a fade out over the final 500 ms.
        extended_end = min(len(audio), end_ms + 1000)
        clip = audio[start_ms:extended_end].fade_out(1000)

        # Export the clip to a buffer, hash its data, and create a unique filename.
        buf = BytesIO()
        clip.export(buf, format="mp3")
        clip_data = buf.getvalue()
        clip_hash = hashlib.md5(clip_data).hexdigest()
        clip_filename = f"clip_{clip_hash}.mp3"
        clip_path = os.path.join(audio_dir, clip_filename)
        if not os.path.exists(clip_path):
            with open(clip_path, "wb") as f:
                f.write(clip_data)

        note = genanki.Note(
            model=my_model,
            fields=[
                f"[sound:{clip_filename}]",
                text,
                "",  # English (text) left blank.
                "",  # notes left blank.
            ],
        )
        my_deck.add_note(note)

    # Gather media files (all .mp3 clips).
    media_files = [
        os.path.join(audio_dir, file)
        for file in sorted(os.listdir(audio_dir))
        if file.endswith(".mp3")
    ]

    if output_apkg:
        output_file = output_apkg
    else:
        base = os.path.basename(audio_file)
        name, _ = os.path.splitext(base)
        output_file = f"audio2anki_{name}.apkg"

    click.echo("Generating Anki package...")
    package = genanki.Package(my_deck)
    package.media_files = media_files
    package.write_to_file(output_file)

    click.echo(f"Generated Anki package: {output_file}")


if __name__ == "__main__":
    main()
