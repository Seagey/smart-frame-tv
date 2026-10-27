#!/bin/sh
# Installs the privacy scan as a git pre-commit hook in this clone.
# Usage: scripts/install-hook.sh [path/to/your-denylist.txt]
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DENY="${1:-}"
HOOK="$ROOT/.git/hooks/pre-commit"
printf '#!/bin/sh\nexec "%s/scripts/privacy-scan.sh" %s --no-history\n' "$ROOT" "${DENY:+\"$DENY\"}" > "$HOOK"
chmod +x "$HOOK"
echo "Installed: $HOOK"
