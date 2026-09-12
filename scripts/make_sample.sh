#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$ROOT/.runtime"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
FFMPEG_BINARY="${FFMPEG_BINARY:-$(command -v ffmpeg)}"
mkdir -p "$RUNTIME"
VOICE="$RUNTIME/sample.aiff"
say -o "$VOICE" 'This is a synthetic interview calibration sample. The hook is simple: reliable systems turn long conversations into useful clips. First, keep the original video untouched, because every later edit must point back to the source. Next, extract one predictable audio format so the local transcription step behaves consistently. The specific lesson is to keep absolute source timestamps attached to every transcript segment, even when a long interview is processed in overlapping chunks. Overlap protects words at chunk boundaries, but duplicate words must be removed before candidate clips are made. The payoff is a reviewable rough cut that an editor can correct quickly. A candidate is a segment identifier with a start time, end time, transcript span, and context warning. OpenAI receives only bounded transcript text, never the original video or audio. A separate human check is required for factual claims and visual delivery. This sample is labelled synthetic and is not a real interview. The intended output is a contiguous clip between thirty and ninety seconds, rendered at 480p for approval.'
"$FFMPEG_BINARY" -y -f lavfi -i "color=c=0x152238:s=1280x720:r=25" -i "$VOICE" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$RUNTIME/sample.mp4" >/dev/null 2>&1
"$FFMPEG_BINARY" -y -i "$RUNTIME/sample.mp4" -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le "$RUNTIME/sample.wav" >/dev/null 2>&1
printf 'sample=%s\naudio=%s\n' "$RUNTIME/sample.mp4" "$RUNTIME/sample.wav"
