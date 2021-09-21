#!/usr/bin/env bash

version=scheduled-maintenance-test

test -z "${DEBUG}" || set -x
image_repo=gcr.io/uwit-mci-iam/husky-directory
fingerprint=$(./scripts/get-snapshot-fingerprint.sh)
docker build \
  -f docker/development-server.dockerfile \
  --build-arg BASE_VERSION=${fingerprint} \
  -t ${image_repo}:${version} \
  .
