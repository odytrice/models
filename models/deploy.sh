#!/usr/bin/env bash
# Build and push the RTX-4090 and RTX-5090 Ollama Modelfiles to the odytrice/* namespace.
#
# Examples:
#   ./deploy.sh                            # build + push everything
#   ./deploy.sh --filter 4090              # only the 4090 variants
#   ./deploy.sh --filter gemma4            # only the gemma models
#   ./deploy.sh --filter qwen3.6:5090-35b  # single model
#   ./deploy.sh --build-only               # build locally without pushing
#   ./deploy.sh --push-only                # push pre-built tags
#   ./deploy.sh --dry-run                  # preview commands without executing

set -euo pipefail

BUILD_ONLY=0
PUSH_ONLY=0
DRY_RUN=0
FILTER=""

usage() {
  cat <<EOF
Usage: $0 [--build-only] [--push-only] [--filter PATTERN] [--dry-run]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-only) BUILD_ONLY=1; shift ;;
    --push-only)  PUSH_ONLY=1;  shift ;;
    --dry-run)    DRY_RUN=1;    shift ;;
    --filter)     FILTER="${2:-}"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    *)            echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# folder | modelfile | tag
MODELS=(
  "gemma4/12b|5090.Modelfile|odytrice/gemma4:5090-12b"
  "gemma4/12b|4090.Modelfile|odytrice/gemma4:4090-12b"
  "gemma4/26b|5090.Modelfile|odytrice/gemma4:5090-26b"
  "gemma4/26b|4090.Modelfile|odytrice/gemma4:4090-26b"
  "gemma4/31b|5090.Modelfile|odytrice/gemma4:5090-31b"
  "qwen3.6/27b|4090.Modelfile|odytrice/qwen3.6:4090-27b"
  "qwen3.6/27b|5090.Modelfile|odytrice/qwen3.6:5090-27b"
  "qwen3.6/35b|5090.Modelfile|odytrice/qwen3.6:5090-35b"
  "qwen3.8/27b|4090.Modelfile|odytrice/qwen3.8:4090-27b"
  "qwen3.8/27b|5090.Modelfile|odytrice/qwen3.8:5090-27b"
  "muse/30b|Modelfile|odytrice/muse:30b"
  "muse/30b|Modelfile|odytrice/muse:latest"
)

run_step() {
  local label="$1"; shift
  echo
  echo "==> $label"
  echo "    ollama $*"
  [[ $DRY_RUN -eq 1 ]] && return 0
  ollama "$@"
}

for entry in "${MODELS[@]}"; do
  IFS='|' read -r folder file tag <<<"$entry"

  if [[ -n "$FILTER" && "$tag" != *"$FILTER"* ]]; then
    continue
  fi

  modelfile="$SCRIPT_DIR/$folder/$file"
  if [[ ! -f "$modelfile" ]]; then
    echo "Modelfile not found: $modelfile" >&2
    exit 1
  fi

  if [[ $PUSH_ONLY -eq 0 ]]; then
    run_step "Build $tag" create "$tag" -f "$modelfile"
  fi
  if [[ $BUILD_ONLY -eq 0 ]]; then
    run_step "Push  $tag" push "$tag"
  fi
done

echo
echo "Done."
