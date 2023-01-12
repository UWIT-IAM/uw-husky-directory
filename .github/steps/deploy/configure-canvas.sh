#!/usr/bin/env bash

canvas=$(${STEP_SCRIPTS}/get_slack_notification.sh \
  -b canvas \
  -v "$target_version" \
  -s "$target_cluster" \
  -q "${deployment_qualifier}" \
  -c "#iam-bot-sandbox")  # TODO

echo "slack-canvas=$(echo $canvas)" >> $GITHUB_OUTPUT
echo "Slack canvas json: $canvas"

context_artifact=$(${STEP_SCRIPTS}/get_slack_notification.sh \
  -b context_artifact \
  -v "$target_version" \
  -s "$target_cluster" \
  -q "${deployment_qualifier}")

echo "context-artifact=$(echo $context_artifact)" >> $GITHUB_OUTPUT
echo "Context artifact: $context_artifact"

set -e
test -n "$canvas"
test -n "$context_artifact"
