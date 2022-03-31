#!/usr/bin/env bash
set -ex
source ./scripts/globals.sh
source ./.build-scripts/sources/github-actions.sh

current_version=$(get_poetry_version)
latest_release=$(curl -s https://api.github.com/repos/UWIT-IAM/uw-husky-directory/releases | jq '.[0].tag_name')
latest_release=$(echo "${latest_release}" | sed 's|"||g')
set_ci_output latest-release "${latest_release}"

if [[ "${GITHUB_REF}" == "refs/heads/main" ]]
then
  set_ci_output version "${current_version}"
  if [[ "${current_version}" == "${latest_release}" ]]
  then
    set_ci_output release-required false
  else
    set_ci_output release-required true
  fi
else
  set_ci_output release-required true
  set_ci_output version "dry-run-${current_version}"
fi
