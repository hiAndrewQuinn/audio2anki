# audio2anki - audio flashcards, no SRT, no API, no nothing.

![image](https://github.com/user-attachments/assets/e7667553-a3d5-4734-83fa-875410bd7f91)


**audio2anki** is a command-line tool that generates Anki flashcard decks (.apkg) from an audio file and its transcript. It slices audio into segments based on timestamped transcript data, stitches transcript fragments when needed, and creates Anki cards that pair audio clips with corresponding transcript text. This is especially useful for language learners or anyone who wants to study audio content alongside its textual transcript.

You do *not* need to have subtitles already for audio2anki. Nor do you need an API key for anywhere - everything in audio2anki runs **entirely locally** (except for the YouTube download of course).

## What it looks like to run

![image](https://github.com/user-attachments/assets/6c5c7d77-dd03-4a76-ad55-36d5fb198861)

Here we call the program with `--youtube`.

If you run this on a local audio file instead, but specify `--whisper`, only the whisper and Python sections will run.

If you run this on a local audio file instead, *and* you specify a transcript, only the Python section will run.

## Quickstart

### Linux, Mac (via Bash)

```bash
if ! command -v yt-dlp > /dev/null; then
    echo "yt-dlp is not installed. Please install it from: https://github.com/yt-dlp/yt-dlp/releases/latest"
    exit 1
fi

if ! command -v whisper > /dev/null; then
    echo "whisper is not installed. Please install it from: https://github.com/openai/whisper"
    exit 1
fi

git clone https://github.com/hiAndrewQuinn/audio2anki.git
cd audio2anki

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Download and process a 12-second Spongebob clip from YouTube, as en example.
# Language wil be automatically detected from the clip, don't worry about it being English.
# You will get Spanish subtitles for a Spanish clip, etc.
python main.py --youtube "https://www.youtube.com/watch?v=fJ6ASXsx-nA"

ls *apkg    # There's your Anki deck!
```


### Windows (via PowerShell)

```powershell
if (-not (Get-Command yt-dlp -ErrorAction SilentlyContinue)) {
    Write-Host "yt-dlp is not installed. Please install it from: https://github.com/yt-dlp/yt-dlp/releases/latest"
    exit 1
}

if (-not (Get-Command whisper -ErrorAction SilentlyContinue)) {
    Write-Host "whisper is not installed. Please install it from: https://github.com/openai/whisper"
    exit 1
}

git clone https://github.com/hiAndrewQuinn/audio2anki.git
Set-Location audio2anki

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Download and process a 12-second Spongebob clip from YouTube, as en example.
# Language wil be automatically detected from the clip, don't worry about it being English.
# You will get Spanish subtitles for a Spanish clip, etc.
python main.py --youtube "https://www.youtube.com/watch?v=fJ6ASXsx-nA"

Get-ChildItem *.apkg   # There's your Anki deck!
```

## Features

- **Audio Segmentation:** Automatically slices an audio file into smaller clips based on transcript timestamps.
- **Transcript Handling:**
  - Uses an existing TSV transcript if available.
  - Automatically generates a transcript using OpenAI's Whisper if no valid transcript is found or if transcript generation is forced.
  - Stitches consecutive transcript segments when the text does not end with a complete sentence.
- **YouTube Integration:**
  - Downloads MP3 audio directly from a YouTube URL using `yt-dlp`.
  - Overrides local audio and transcript files when a YouTube URL is provided.
- **Customizability:** Allows you to specify custom deck names, output directories for audio clips and transcripts, and the output filename for the Anki package.
- **Media Packaging:** Automatically gathers generated audio clips as media files to be embedded in the Anki deck.

## Prerequisites

Before running **audio2anki**, ensure you have the following:

1. **yt-dlp Binary:**  
   Download the latest yt-dlp binary from [yt-dlp Releases](https://github.com/yt-dlp/yt-dlp/releases/latest). This tool is used to download audio from YouTube.

2. **OpenAI Whisper:**  
   Download the latest version of OpenAI Whisper from [OpenAI Whisper GitHub](https://github.com/openai/whisper). Whisper is used for automatic transcription when a transcript is not available.

3. **Python Dependencies:**  
   Install the required Python packages using:
   ```bash
   pip install -r requirements.txt
   ```

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/audio2anki.git
   cd audio2anki
   ```

2. **Set Up a Virtual Environment:**
   It's recommended to use a virtual environment to manage dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows use: venv\Scripts\activate
   ```

3. **Install Python Dependencies:**
   With your virtual environment activated, install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. **(Optional) Set Up Environment Variables:**  
   Create a `.env` file in the project root to set any environment variables (e.g., `BROWSER` for cookie support with yt-dlp).

## Usage

**audio2anki** can be used in two main ways:

### Audio from YouTube

You can download audio **directly from YouTube** by providing a YouTube URL. This mode automatically downloads the audio, generates a transcript (if needed), and creates an Anki deck.

After you have done this once, the local audio file should stick around in `youtube/` in case you want to run this again.

**Example Command:**
```bash
./main.py --youtube "https://www.youtube.com/watch?v=example"
```

- **Behavior:**
  - Overrides any provided local audio or transcript files.
  - Downloads the audio using `yt-dlp` (ensure the binary is installed and in your PATH).
  - Uses the downloaded MP3 for transcript generation and deck creation.

### Audio Locally

Alternatively, you can work with a **local audio file** along with an optional transcript file. If no transcript is provided, the program will look for one in the default transcripts directory or generate one using Whisper.

**Example Commands:**

1. **Using a Local Audio File with an Existing Transcript:**
   ```bash
   ./main.py path/to/audio.mp3 path/to/transcript.tsv
   ```

2. **Using a Local Audio File with Automatic Transcript Generation:**
   ```bash
   ./main.py path/to/audio.mp3 --whisper
   ```

- **Behavior:**
  - Processes the provided audio file.
  - Searches for a transcript in the `transcripts` directory if a transcript file isn’t explicitly given.
  - Prompts the user or automatically generates a transcript using Whisper if no valid transcript is found.
  - Uses the local audio and transcript files for deck creation.

## Docker Support (WIP)

**Note:** The provided `Dockerfile` is still a work in progress and **does not currently work**. For now, please run the tool using your local Python environment as described above.

## License

This project is licensed under the Unlicense. Do whatever you want with it!

## Contributing

Contributions, bug reports, and feature requests are welcome! Please open an issue or submit a pull request with your improvements.
