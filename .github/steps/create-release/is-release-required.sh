#!/usr/bin/env bash
set -ex
source ./scripts/globals.sh
current_version=$(get_poetry_version)
latest_release=$(curl -s https://api.github.com/repos/UWIT-IAM/uw-husky-directory/releases | jq '.[0].tag_name')
latest_release=$(echo "${latest_release}" | sed 's|"||g')

set_ci_output version "${current_version}"
set_ci_output latest-release "${latest_release}"
if [[ "${current_version}" == "${latest_release}" && "${GITHUB_REF}" == "refs/heads/main" ]]
then
  echo "::set-output name=release-required::false"
else
  echo "::set-output name=release-required::true"
fi
