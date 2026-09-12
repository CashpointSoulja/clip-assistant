# Local clip assistant runtime

This runtime keeps large interview media local. `ffmpeg` extracts audio, `whisper.cpp` transcribes it, and later analysis may send bounded transcript text only. Rendering uses the original video and produces 480p review cuts after human approval.

## Setup

```sh
./scripts/setup.sh
```

The script prefers `/opt/homebrew/bin`, installs FFmpeg with Homebrew when absent, builds upstream `whisper.cpp` in `.runtime`, and downloads the quantized `large-v3-turbo-q5_0` model there. Set `WHISPER_MODEL_NAME=base.en` for a smaller fallback on low-memory Macs. It makes no privileged changes and never searches for or prints API keys.

## Calibration sample

```sh
./scripts/make_sample.sh
```

This creates a labelled synthetic 60–100 second interview in `.runtime/sample.mp4` and its audio proxy.

## Runtime contract

Copy `.env.example` to `.env`, leave the key blank until you choose to use cloud analysis, then double-click `Start Clip Assistant.command` (or run `python3 server.py`). It serves `127.0.0.1:8765` with `FFMPEG_BIN`, `FFPROBE_BIN`, `WHISPER_BIN`, `WHISPER_MODEL`, and `OPENAI_MODEL=gpt-5-mini`. There is no real-time or every-format guarantee.

The runtime is already installed on this Mac. Open http://127.0.0.1:8765 while the server is running. Choose a video, select local mode for a no-key test, review a candidate, adjust its time ranges and click **Approve & export 480p**. Saved jobs are available in the review section. Live analysis is cached by transcript, settings, model and prompt version so repeating the same run returns the same reviewed result without another model call.

To enable AI analysis, enter your key in the existing ignored `.env` file, then restart the server. Never paste the key into chat. Only transcript text and analysis context are sent to OpenAI; the video and audio stay local. `MAX_ANALYSIS_CALLS` bounds requests per run (default 40); it is not a currency-denominated spending limit.

## Checks

Stop the app first for the HTTP tests, which use its local port:

```sh
python3 -m unittest -v test_pipeline test_analysis test_server
python3 test_integration.py
```

The integration check uses labelled synthetic speech. It tests local transcription, a recording longer than five minutes and an actual 480p multi-range export. See `TEST_RESULTS.md` for what was and was not verified.
