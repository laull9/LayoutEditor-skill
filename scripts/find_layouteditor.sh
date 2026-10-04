#!/usr/bin/env bash
# Print the path of LayoutEditor's bundled Python interpreter (the one that can `import LayoutScript`).
#
# Usage:   LE_PY="$(scripts/find_layouteditor.sh)" && "$LE_PY" my_generator.py
# Overrides (checked first):
#   LE_PY=/path/to/python             use this interpreter directly
#   LAYOUTEDITOR_HOME=/install/dir    search this LayoutEditor installation
#
# Search order: $LE_PY, $LAYOUTEDITOR_HOME, then common install locations on macOS, Linux and
# Windows (Git Bash / MSYS / WSL paths). Only the macOS layout has been verified; on other systems
# the script looks for any `LayoutScript.py` shipped next to a bundled python3.x.
set -euo pipefail

works() { [[ -x "$1" ]] && "$1" -c "import LayoutScript" >/dev/null 2>&1; }

if [[ -n "${LE_PY:-}" ]]; then
  if works "$LE_PY"; then echo "$LE_PY"; exit 0; fi
  echo "LE_PY=$LE_PY cannot import LayoutScript" >&2; exit 1
fi

roots=()
[[ -n "${LAYOUTEDITOR_HOME:-}" ]] && roots+=("$LAYOUTEDITOR_HOME")
roots+=(
  "/Applications/layout.app" "$HOME/Applications/layout.app"                       # macOS .dmg
  "/opt/layout" "/opt/LayoutEditor" "/usr/lib/layout" "/usr/share/layout"          # Linux .deb/.rpm
  "/usr/local/layout" "$HOME/layout" "$HOME/LayoutEditor"
  "/c/Program Files/LayoutEditor" "/c/Program Files/layout"                        # Windows (Git Bash)
  "/mnt/c/Program Files/LayoutEditor" "/mnt/c/Program Files/layout"                # Windows (WSL)
)

for root in "${roots[@]}"; do
  [[ -d "$root" ]] || continue
  while IFS= read -r ls_py; do
    libdir="$(dirname "$ls_py")"                       # …/lib/python3.X  (or …/Lib on Windows)
    for cand in "$(cd "$libdir/../.." 2>/dev/null && pwd)/bin/$(basename "$libdir")" \
                "$(cd "$libdir/../.." 2>/dev/null && pwd)/bin/python3" \
                "$(cd "$libdir/.." 2>/dev/null && pwd)/python.exe" \
                "$(cd "$libdir/.." 2>/dev/null && pwd)/python3"; do
      if works "$cand"; then echo "$cand"; exit 0; fi
    done
  done < <(find "$root" -name LayoutScript.py 2>/dev/null | head -n 5)
done

cat >&2 <<'MSG'
LayoutEditor's bundled Python (with the LayoutScript module) was not found.
  * Install LayoutEditor: https://layouteditor.com/download.html (free edition is sufficient)
  * Or point to it: export LE_PY=/path/to/bundled/python   or   export LAYOUTEDITOR_HOME=/install/dir
  * Tip: find / -name LayoutScript.py 2>/dev/null   shows where the module lives.
MSG
exit 1
