#!/usr/bin/env bash
set -euo pipefail

for s in files/scripts/*.sh files/system/usr/bin/kushagra-*; do
    bash -n "$s"
    echo "PASS bash -n: $s"
done
