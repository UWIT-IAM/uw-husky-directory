#!/usr/bin/env bash

test -z "${DEBUG}" || set -x
image_repo=gcr.io/uwit-mci-iam/husky-directory-base
fingerprint=$(./.build-scripts/get-snapshot-fingerprint.sh)
$BUILD_SCRIPTS_DIR/scripts/pull-or-build-image.sh \
  -i $image_repo:$fingerprint \
  -d docker/husky-directory-base.dockerfile
