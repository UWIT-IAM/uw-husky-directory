#!/usr/bin/env bash

source ./.build-scripts/sources/github-actions.sh

canvas=$(${STEP_SCRIPTS}/get_slack_notification.sh \
  -b canvas \
  -v "$target_version" \
  -s "$target_cluster" \
  -q "${deployment_qualifier}" \
  -c "#iam-bot-sandbox")  # TODO

set_ci_output slack-canvas "$(echo $canvas)"
echo "Slack canvas json: $canvas"

context_artifact=$(${STEP_SCRIPTS}/get_slack_notification.sh \
  -b context_artifact \
  -v "$target_version" \
  -s "$target_cluster" \
  -q "${deployment_qualifier}")

set_ci_output context-artifact "$(echo $context_artifact)"
echo "Context artifact: $context_artifact"

set -e
test -n "$canvas"
test -n "$context_artifact"
