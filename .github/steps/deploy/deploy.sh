#!/usr/bin/env bash

args="-t ${target_cluster} "

test -n "${target_version}" && args+="--version ${target_version} "
test -n "${rfc_number}" && args+="-r ${rfc_number} "
test "${DRY_RUN}" = 'true' && args+="-x "
command="./scripts/deploy.sh $args"
echo $command
eval $command
