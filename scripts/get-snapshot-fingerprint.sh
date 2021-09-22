#!/usr/bin/env bash
# Generates the sha256 fingerprint of the current
# dependency image based on the declared lock files.
./scripts/install-build-scripts.sh >/dev/null
source ./.build-scripts/sources/fingerprints.sh

image_name='husky-directory-base'

lock_files=(
  pyproject.toml
  poetry.lock
  ./docker/${image_name}.dockerfile
)

echo $(calculate_paths_fingerprint ${lock_files[@]})
