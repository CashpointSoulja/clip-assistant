#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$ROOT/.runtime"
SRC="$RUNTIME/whisper.cpp"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p "$RUNTIME"
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  command -v /opt/homebrew/bin/brew >/dev/null || { echo 'Homebrew required to install ffmpeg' >&2; exit 1; }
  /opt/homebrew/bin/brew install ffmpeg
fi
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
command -v cmake >/dev/null || { echo 'cmake required to build whisper.cpp' >&2; exit 1; }
if [[ ! -d "$SRC/.git" ]]; then git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$SRC"; fi
cmake -S "$SRC" -B "$SRC/build" -DWHISPER_COREML=OFF
cmake --build "$SRC/build" --config Release --parallel
ln -sf "$SRC/build/bin/whisper-cli" "$RUNTIME/whisper-cli"
MODEL_NAME="${WHISPER_MODEL_NAME:-large-v3-turbo-q5_0}"
MODEL_FILE="$RUNTIME/ggml-${MODEL_NAME}.bin"
if [[ ! -f "$MODEL_FILE" ]]; then
  if (cd "$SRC" && bash models/download-ggml-model.sh "$MODEL_NAME"); then
    cp "$SRC/models/ggml-${MODEL_NAME}.bin" "$MODEL_FILE"
  elif [[ "$MODEL_NAME" != "base.en" ]]; then
    rm -f "$SRC/models/ggml-${MODEL_NAME}.bin" "$MODEL_FILE"
    echo "${MODEL_NAME} unavailable; falling back to base.en" >&2
    MODEL_NAME="base.en"
    MODEL_FILE="$RUNTIME/ggml-${MODEL_NAME}.bin"
    if [[ ! -f "$MODEL_FILE" ]]; then
      (cd "$SRC" && bash models/download-ggml-model.sh "$MODEL_NAME")
      cp "$SRC/models/ggml-${MODEL_NAME}.bin" "$MODEL_FILE"
    fi
  else
    exit 1
  fi
fi
printf 'FFMPEG_BIN=%s\nFFPROBE_BIN=%s\nWHISPER_BIN=%s\nWHISPER_MODEL=%s\n' "$(command -v ffmpeg)" "$(command -v ffprobe)" "$RUNTIME/whisper-cli" "$MODEL_FILE"
