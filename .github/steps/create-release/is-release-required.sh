#!/usr/bin/env bash

source .build-scripts/sources/github-actions.sh

current_version=$(poetry version -s)
releases=$(curl -s https://api.github.com/repos/UWIT-IAM/uw-husky-directory/tags)
latest_release=$(curl -s https://api.github.com/repos/UWIT-IAM/uw-husky-directory/tags | jq '.[0].name')

set_ci_output version "${current_version}"
set_ci_output latest-release "${latest_release}"
if [[ "${current_version}" == "${latest_release}" ]]
then
  set_ci_output release-required false
else
  set_ci_output release-required true
fi
