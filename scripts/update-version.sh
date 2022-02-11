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

spec_file="rpm-build/SPECS/hexagon.spec"

sed -i "s/^version = .*$/version = \"${new_version}\"/" setup.py
sed -i "s/^VERSION = .*$/VERSION = \"${new_version}\"/" hexagon/cli.py
sed -i "s/^%global version .*$/%global version ${new_version}/" "$spec_file"
perl -pi -e "s/hexagon-[\\d\\.]+-1.fc25.noarch.rpm/hexagon-${new_version}-1.fc25.noarch.rpm/" README.md
perl -pi -e "s/hexagon-[\\d\\.]+-1.fc32.noarch.rpm/hexagon-${new_version}-1.fc32.noarch.rpm/" README.md

echo "Updated to version $new_version"
echo "Edit the spec file to add changelog: $spec_file"
echo "Then run: "
# Not automating the tag creation, because the changelog
# still needs updates. =/
printf '\n\tgit tag -a -s %s -m "hexagon %s"\n\n' "$new_version" "$new_version"
