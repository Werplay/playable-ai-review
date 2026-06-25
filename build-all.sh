#!/usr/bin/env bash
#
# Build the playable for every supported ad network, concurrently.
#
# Usage:
#   ./build-all.sh                 # build all networks, parallelism = CPU cores
#   JOBS=4 ./build-all.sh          # cap to 4 parallel builds
#   ./build-all.sh fb unity google # build only the given networks
#
# Output:  dist/Blizzard_..._<NETWORK>.{html,zip}
# Logs:    build-logs/<network>.log  (one per network)
#
set -uo pipefail
cd "$(dirname "$0")"

# Network list: CLI args if given, else the full playable-scripts allow-list.
if [ "$#" -gt 0 ]; then
  NETWORKS="$*"
else
  NETWORKS=$(node -e "require('./node_modules/@smoud/playable-scripts/core/utils/parseArgvOptions.js').allowedAdNetworks.forEach(n=>console.log(n))")
fi

# Parallelism: default to CPU cores (override with JOBS=N).
JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}"

mkdir -p dist build-logs
count=$(printf '%s\n' $NETWORKS | grep -c .)
echo "Building $count network(s) with up to $JOBS parallel jobs..."
start=$(date +%s)

# Run one `node build.js --network <n>` per network, up to $JOBS at a time.
# Each writes a uniquely-named file into dist/, so concurrent builds don't clobber each other.
printf '%s\n' $NETWORKS | xargs -P "$JOBS" -I {} bash -c '
  n="$1"
  if node build.js --network "$n" > "build-logs/$n.log" 2>&1; then
    printf "  %-12s OK\n" "$n"
  else
    printf "  %-12s FAIL  -> build-logs/%s.log\n" "$n" "$n"
  fi
' _ {}

echo "------------------------------------------------------------"
echo "Done in $(( $(date +%s) - start ))s. $(find dist -type f | wc -l | tr -d ' ') file(s) in dist/"
