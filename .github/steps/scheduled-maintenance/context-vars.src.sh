#!/usr/bin/env bash

source ./.build-scripts/sources/slack.sh
source ./.build-scripts/sources/github-actions.sh

BASE_IMAGE=${BASE_IMAGE_REPO}
APP_IMAGE=${APP_IMAGE_REPO}
PR_URL_BASE=${PR_URL_BASE}

new_app_version=$(poetry version -s)
new_di_version=$(date +%Y.%-j.%-I.%-M)
di_fingerprint=$(./scripts/get-snapshot-fingerprint.sh)
di_img_url=https://${BASE_IMAGE}:${new_di_version}
app_img_url=https://${APP_IMAGE}:${new_app_version}
app_link="$(slack_link $app_img_url $new_app_version)"
di_link="$(slack_link $di_img_url $new_di_version)"
