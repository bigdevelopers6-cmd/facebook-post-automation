#!/bin/bash
# Safe grep -c: GNU grep exits 1 when count is 0, which breaks "|| echo 0" (prints 0 twice).
grep_count() {
  local pattern="$1" file="$2"
  local n=0
  if [ -f "$file" ]; then
    n=$(grep -c "$pattern" "$file" 2>/dev/null) || n=0
  fi
  echo "${n:-0}"
}
