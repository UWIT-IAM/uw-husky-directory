#!/usr/bin/env bash
set -ex
source ./scripts/globals.sh
current_version=$(get_poetry_version)
latest_release=$(curl -s https://api.github.com/repos/UWIT-IAM/uw-husky-directory/releases | jq '.[0].tag_name')
latest_release=$(echo "${latest_release}" | sed 's|"||g')

echo "version=${current_version}" >> $GITHUB_OUTPUT
echo "latest-release=${latest_release}" >> $GITHUB_OUTPUT
if [[ "${current_version}" == "${latest_release}" && "${GITHUB_REF}" == "refs/heads/main" ]]
then
  echo "release-required=false" >> $GITHUB_OUTPUT
else
  echo "release-required=true" >> $GITHUB_OUTPUT
fi
