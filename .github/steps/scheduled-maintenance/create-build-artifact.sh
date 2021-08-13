#!/usr/bin/env bash

source ${STEP_SCRIPTS}/context-vars.src.sh

pr_number=${GITHUB_PR_NUMBER}
pr_url=${PR_URL_BASE}/${pr_number}
pr_link="$(slack_link $pr_url PR#${pr_number})"
workflow_artifact="Created ${pr_link} for version ${app_link} "
workflow_artifact+="and pushed dependency image version ${di_link}"

echo "$workflow_artifact"
set_ci_output slack-artifact "$workflow_artifact"
