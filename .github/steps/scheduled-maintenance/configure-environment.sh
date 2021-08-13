#!/usr/bin/env bash
set -x

./.github/scripts/install-build-scripts.sh
source $BUILD_SCRIPTS_DIR/sources/github-actions.sh
POETRY_VERSION_GUIDANCE=${POETRY_VERSION_GUIDANCE:-patch}

slack_notification_json="./.github/steps/scheduled-maintenance/slack-notification.json"
slack_notification_json=$(echo `cat $slack_notification_json`)

gcloud auth configure-docker
poetry version ${POETRY_VERSION_GUIDANCE}
new_app_version=$(poetry version -s)
new_di_version=$(date +%Y.%-j.%-I.%-M)
di_fingerprint=$(./scripts/get-snapshot-fingerprint.sh)
set_ci_output workflow-json "$slack_notification_json"
set_ci_output new-app-version "$new_app_version"
set_ci_output new-di-version "$new_di_version"
set_ci_output di-fingerprint "$di_fingerprint"
