#!/usr/bin/env bash
set -ex
source ./scripts/globals.sh
current_version=$(get_poetry_version)
latest_release=$(curl -s https://api.github.com/repos/UWIT-IAM/uw-husky-directory/releases | jq '.[0].tag_name')
latest_release=$(echo "${latest_release}" | sed 's|"||g')

echo "::set-output name=version::${current_version}"
echo "::set-output name=latest-release::${latest_release}"
if [[ "${current_version}" == "${latest_release}" && "${GITHUB_REF}" == "refs/heads/main" ]]
then
  echo "::set-output name=release-required::false"
else
  echo "::set-output name=release-required::true"
fi
