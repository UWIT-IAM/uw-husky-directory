# Sets up variables that are used in the rest of the workflow.
# Expects the following variables to be set by the workflow yml:
# REPO_HOST -- e.g., gcr.io
# REPO_PROJECT
# APP_NAME -- e.g., husky-directory
# DEPLOY_TARGET -- e.g., 'dev'
# BASE_FINGERPRINT -- The SHA256 fingerprint of the poetry lock file and the
#                            base image dockerfile,
#                            calculated using Actions hashFiles function.
# Other variables are depended on but set by github:
# GITHUB_SHA -- the commit reference of the change being built
#     Note that this will not be deterministic, nor will it match the repository
#     history after it is merged. That's a Github problem.

set -ex

test -n "$BASE_FINGERPRINT"

#!/usr/bin/env bash

DEPLOY_TARGET=${DEPLOY_TARGET:-dev}

COMMIT_PREFIX=${GITHUB_SHA:0:10}
APP_BUILD_LABEL=commit-${COMMIT_PREFIX}
echo ::set-output name=app_build_version::${APP_BUILD_LABEL}

APP_REPO=${REPO_HOST}/${REPO_PROJECT}/${APP_NAME}
echo ::set-output name=app_repo::${APP_REPO}

APP_BUILD_TAG=${APP_REPO}:commit-${COMMIT_PREFIX}
echo ::set-output name=app_build_tag::${APP_BUILD_TAG}

APP_HEAD_TAG=${APP_REPO}:deploy-${DEPLOY_TARGET}.${COMMIT_PREFIX}
echo ::set-output name=app_head_tag::${APP_HEAD_TAG}

echo ::set-output name=base_build_version::${BASE_FINGERPRINT}

BASE_REPO=${REPO_HOST}/${REPO_PROJECT}/${APP_NAME}-base
echo ::set-output name=base_repo::${BASE_REPO}

BASE_BUILD_TAG=${BASE_REPO}:${BASE_FINGERPRINT}
echo ::set-output name=base_build_tag::${BASE_BUILD_TAG}

BASE_HEAD_TAG=${BASE_REPO}:latest
echo ::set-output name=base_head_tag::${BASE_HEAD_TAG}
