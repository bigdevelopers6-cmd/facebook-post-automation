#!/usr/bin/env bash
# Run on your Ubuntu/AWS server: bash server-resource-check.sh
set -euo pipefail

echo "=============================================="
echo "  SERVER RESOURCE CHECK — $(hostname) — $(date -u)"
echo "=============================================="
echo

echo "--- MEMORY ---"
free -h
echo
TOTAL_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
AVAIL_KB=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
echo "Total RAM:     $(( TOTAL_KB / 1024 )) MB"
echo "Available now: $(( AVAIL_KB / 1024 )) MB"
echo

echo "--- CPU / LOAD ---"
nproc
uptime
echo

echo "--- DISK ---"
df -h /
echo

echo "--- LISTENING PORTS (TCP) ---"
if command -v ss >/dev/null 2>&1; then
  sudo ss -tlnp 2>/dev/null || ss -tlnp
else
  sudo netstat -tlnp 2>/dev/null || netstat -tlnp
fi
echo

echo "--- DOCKER (if installed) ---"
if command -v docker >/dev/null 2>&1; then
  docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}' 2>/dev/null || docker ps
else
  echo "Docker not installed"
fi
echo

echo "--- SUGGESTED FREE PORTS FOR n8n (common choices) ---"
for p in 5678 5680 5681 8080 8888; do
  if ss -tln 2>/dev/null | grep -q ":${p} "; then
    echo "  Port $p — IN USE"
  else
    echo "  Port $p — FREE"
  fi
done
echo
echo "Done. Share this output to pick n8n port and confirm RAM headroom."
