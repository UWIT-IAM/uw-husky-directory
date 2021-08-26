#!/usr/bin/env bash
set -x

workspace=${GITHUB_WORKSPACE:-.}

${GITHUB_WORKSPACE}/scripts/install-build-scripts.sh

POETRY_VERSION_GUIDANCE=${POETRY_VERSION_GUIDANCE:-patch}

gcloud auth configure-docker
poetry version ${POETRY_VERSION_GUIDANCE}
poetry lock
source ${STEP_SCRIPTS}/context-vars.src.sh

slack_notification_json="./.github/steps/scheduled-maintenance/slack-notification.json"
slack_notification_json=$(echo `cat $slack_notification_json`)

set_ci_output workflow-json "$slack_notification_json"
set_ci_output new-app-version "$new_app_version"
set_ci_output new-di-version "$new_di_version"
set_ci_output di-fingerprint "$di_fingerprint"
