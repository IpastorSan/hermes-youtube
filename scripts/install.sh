#!/usr/bin/env bash
# Link this checkout into $HERMES_HOME/plugins/youtube-transcript for development.
# Always links the main checkout, even when run from a git worktree, so the link
# survives worktree cleanup. Idempotent; refuses to replace a real directory or file.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if common="$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"; then
  repo="$(dirname "$common")"
fi
home="${HERMES_HOME:-$HOME/.hermes}"
target="$home/plugins/youtube-transcript"

mkdir -p "$home/plugins"
if [[ -e "$target" && ! -L "$target" ]]; then
  echo "refusing to replace $target: it exists and is not a symlink" >&2
  exit 1
fi
ln -sfn "$repo" "$target"
echo "linked $target -> $repo"
echo "next: hermes plugins enable youtube-transcript"
