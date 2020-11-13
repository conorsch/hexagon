#!/bin/bash
set -e
set -u
set -o pipefail


if [[ $# != 1 ]]; then
    echo "ERROR: No new version declared"
    echo "Usage: $0 <new_version>"
    exit 1
fi

new_version="$1"
shift

sed -i "s/^version = .*$/version = \"$new_version\"/" setup.py
sed -i "s/^%global version .*$/%global version $new_version/" rpm-build/SPECS/hexagon.spec
