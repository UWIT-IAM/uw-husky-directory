#!/usr/bin/env bash

source $BUILD_SCRIPTS_DIR/sources/github-actions.sh
source $BUILD_SCRIPTS_DIR/sources/slack.sh
source ${STEP_SCRIPTS}/context-vars.src.sh

PR_NUMBER=${GITHUB_PR_NUMBER}
pr_url=${PR_URL_BASE}/${PR_NUMBER}
pr_link="$(slack_link $pr_url PR#${PR_NUMBER})"
workflow_artifact="Created ${pr_link} for version ${app_link} "
workflow_artifact+="and pushed dependency image version ${di_link}"

echo "$workflow_artifact"
set_ci_output slack-artifact "$workflow_artifact"
