#!/usr/bin/env bash
# Records the routine's state on the `routine-status` branch so the manager's
# dashboard can show it (Usopp on deck while a run is going).
# Usage: bash scripts/routine_status.sh running|done
# Never touches main or the working tree. Failures are harmless; the review
# itself does not depend on this.
set -euo pipefail
state="${1:?usage: routine_status.sh running|done}"
branch=routine-status
tmp="$(mktemp -d)"
trap 'git worktree remove --force "$tmp" >/dev/null 2>&1 || true' EXIT
if git fetch -q origin "$branch" 2>/dev/null; then
  git worktree add -q --detach "$tmp" FETCH_HEAD
else
  git worktree add -q --detach "$tmp"
  git -C "$tmp" checkout -q --orphan status-tmp
  git -C "$tmp" rm -rqf . >/dev/null
fi
printf '{"state":"%s","at":"%s"}\n' "$state" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$tmp/status.json"
git -C "$tmp" add status.json
git -C "$tmp" -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -qm "routine $state"
git -C "$tmp" push -q origin "HEAD:refs/heads/$branch"
echo "routine-status: $state"
