#!/bin/sh
set -eu
state=/tmp/aift-health-failures
if wget -q -T 2 -t 1 -O /dev/null http://127.0.0.1:8001/internal-health; then
  rm -f "$state"
  exit 0
fi
failures=0
[ ! -f "$state" ] || failures=$(cat "$state" 2>/dev/null || printf 0)
case "$failures" in *[!0-9]*|'') failures=0 ;; esac
failures=$((failures + 1))
printf '%s' "$failures" > "$state"
[ "$failures" -lt 3 ] || kill -TERM 1
exit 1
