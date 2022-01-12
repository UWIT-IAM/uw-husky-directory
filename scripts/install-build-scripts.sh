#!/usr/bin/env bash

export BUILD_SCRIPTS_DIR="./.build-scripts"
if ! [[ -f "${BUILD_SCRIPTS_DIR}/.VERSION" ]] || [[ "$1" =~ -f|--force ]]
then
  bash <(curl -Lsk https://uwiam.page.link/install-build-scripts)
fi
