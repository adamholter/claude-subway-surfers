#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
source_app="${CLAUDE_DESKTOP_APP:-/Applications/Claude.app}"
destination="${1:-$HOME/Applications/Claude Subway.app}"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer requires macOS." >&2
  exit 1
fi
if [[ ! -d "$source_app" ]]; then
  echo "Install Claude Desktop first, or set CLAUDE_DESKTOP_APP to its path." >&2
  exit 1
fi
if [[ -e "$destination" ]]; then
  echo "Destination already exists: $destination" >&2
  echo "Choose a new destination or move the existing copy to Trash first." >&2
  exit 1
fi
mkdir -p "$(dirname "$destination")"
ditto "$source_app" "$destination"
python3 "$project_root/scripts/patch-desktop.py" "$destination" --source "$source_app"
codesign --force --deep --sign - "$destination"
codesign --verify --deep --strict "$destination"
printf 'Installed separate app copy: %s\n' "$destination"
printf 'Open it from Finder and sign in to Claude. Keep this source folder in place.\n'
