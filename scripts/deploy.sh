#!/usr/bin/env bash

source ./scripts/globals.sh
build_script="$(poetry run fingerprinter -o build-script) -p"

REPO_API_URL=https://api.github.com/repos/uwit-iam/uw-husky-directory

REPO_TAGS_URL="${REPO_API_URL}/tags"
REPO_RELEASE_URL="${REPO_API_URL}/release/latest"
# Explicitly clear the local DRY_RUN variable if it is set by the environment
# So that we don't have to try and guess what the environment is doing with it.
# For the purposes of this script, dry run can be set by using `-x` or` --dry-run`,
# and then within this script only tested for value presence.
DRY_RUN=


function print_help {
   cat <<EOF
   Use: deploy.sh [--debug --help]
   For more, see docs/deployment.md
   Options:
   -v, --version         The version to deploy. If not provided, a promotion will take
                         place, instead (eval promotes from dev, prod promotes from
                         eval).

   --live                Build and deploy the current code base to dev and dev only.
                         Deployment id will contain your username.

   -t, --target-cluster  The cluster to deploy to. Choose from: dev, eval, prod.

   -r, --rfc-number      If deploying to prod, the RFC number is required.
                         You only need ot provide the number.
   -w, --wait-time-secs  The number of seconds to wait for the deployment to be ready.
                         Default is 600 (10 minutes).
   -x, --dry-run         Do not actually push the tag.

   --no-validation       Use this to skip validation; this will exit the script after
                         pushing the docker image, without waiting for an update to
                         occur or running any tests.

   -h, --help            Show this message and exit

   -g, --debug           Show commands as they are executing
EOF
}

WAIT_TIME_SECS=600

while (( $# ))
do
  case $1 in
    --live)
      deploy_live=1
      ;;
    --version|-v)
      shift
      deploy_version="$1"
      ;;
    --target-cluster|-t)
      shift
      target_cluster="$1"
      ;;
    --rfc-number|-r)
      shift
      rfc_number="$1"
      ;;
    --wait-time-secs|-w)
      shift
      WAIT_TIME_SECS=$1
      ;;
    --no-validation)
      shift
      UNSAFE=1
      ;;
    --dry-run|-x)
      DRY_RUN=1
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    --debug|-g)
      set -x
      DEBUG=1
      ;;
    *)
      echo "Invalid Option: $1"
      print_help
      exit 1
      ;;
  esac
  shift
done

function configure_deployment {
  # Cluster is always a required argument.
  if [[ -n "${deploy_live}" ]]
  then
    target_cluster=dev
    deploy_version="$(poetry version -s).local.$(whoami)"
    echo "Building version ${deploy_version} for release"
    $build_script -p --release $deploy_version
  fi
  if [[ -z "${target_cluster}" ]]
  then
    >&2 echo "--target-cluster/-t must be supplied"
    return 1
  fi
  if [[ "${target_cluster}" == 'prod' ]] && [[ -z "${rfc_number}" ]]
  then
    >&2 echo "--rfc-number/-r required when target is prod!"
    return 1
  fi

  # If no version was explicitly provided, we have to
  # determine the promotion version.
  if [[ -z "${deploy_version}" ]]
  then
    deploy_version=$(get_promotion_version ${target_cluster})
  fi
  if [[ -n "${GITHUB_REF}" ]]
  then
    echo "target-cluster=$target_cluster" >> $GITHUB_OUTPUT
    echo "target-version=$deploy_version" >> $GITHUB_OUTPUT
  fi
}

function wait_for_deployment {
  local attempts=0
  local pause_secs=10
  local max_attempts=$(( $WAIT_TIME_SECS / $pause_secs ))
  local origin_id=$(get_instance_deployment_id $target_cluster)

  while [[ -n "1" ]]
  do
    attempts=$(( $attempts+1 ))
    if [[ "$attempts" -gt "$max_attempts" ]]
    then
      echo "Deployment did not complete within $WAIT_TIME_SECS seconds; aborting."
      return 1
    fi
    local cur_id=$(get_instance_deployment_id $target_cluster)
    if [[ "$origin_id" != "${cur_id}" ]]
    then
      echo "Deployment ID has been updated to: ${cur_id}"
      return 0
    fi
    echo "Attempt #${attempts}: Deployed $target_cluster deployment ID has not changed from ${origin_id}"
    sleep 10
  done
  if ! $(echo "${cur_id}" | grep "${deploy_version}")
  then
    echo "Version mismatch! Expected to find version ${deploy_version} in deployment id ${cur_id}"
    return 1
  fi
}

set -e
configure_deployment

set -x
$build_script \
  --deploy ${target_cluster} \
  -dversion ${deploy_version} \
  --build-arg HUSKY_DIRECTORY_VERSION=${deploy_version} \
  $(test -z "${DRY_RUN}" || echo "-ddry") \
  $(test -z "${DEBUG}" || echo "-g")
set +x

if [[ -z "${UNSAFE}" ]] && [[ -z "${DRY_RUN}" ]]
then
  wait_for_deployment
fi
