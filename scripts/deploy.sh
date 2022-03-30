#!/usr/bin/env bash

source ./scripts/globals.sh
source ./.build-scripts/sources/bash-helpers.sh

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

   --candidate           This allows you to deploy to dev and dev only, any tag
                         that is on your system.

   --no-pull             In combination with '--candidate', allows you to deploy an
                         image that has never been pushed.

   -t, --target-cluster  The cluster to deploy to. Choose from: dev, eval, prod.

   -r, --rfc-number      If deploying to prod, the RFC number is required.
                         You only need ot provide the number.
   -w, --wait-time-secs  The number of seconds to wait for the deployment to be ready.
                         Default is 600 (10 minutes).
   -x, --dry-run         Do not actually push the tag.

   --no-validation       Use this to skip validation; this will exit the script after
                         pushing the docker image, without waiting for an update to
                         occur or running any tests.

   --dev-promotion-strategy   By default, we deploy the latest github tag to dev;
                              however you can choose to deploy any of the following
                              when running manually:
                                  tag       [Default] The latest tag known to github,
                                            from: $REPO_TAGS_URL

                                  release   The latest release known to github,
                                            from: $REPO_RELEASES_URL

   -h, --help            Show this message and exit

   -g, --debug           Show commands as they are executing
EOF
}

WAIT_TIME_SECS=600
DEV_STRATEGY=tag

while (( $# ))
do
  case $1 in
    --candidate)
      RELEASE_CANDIDATE=1
      ;;
    --no-pull)
      NO_PULL=1
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
    --dev-promotion-strategy)
      shift
      DEV_STRATEGY="$1"
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
      ;;
    *)
      echo "Invalid Option: $1"
      print_help
      exit 1
      ;;
  esac
  shift
done

function version_image_tag {
  local version="$1"
  echo "${DOCKER_REPOSITORY}.app:${version}"
}

function deploy_image_tag {
  local stage="$1"
  local app_version="$2"
  qualifier=$(tag_timestamp).v${app_version}
  if [[ -n "${RELEASE_CANDIDATE}" ]]
  then
    qualifier="${qualifier}.${USER}"
  fi
  echo "${DOCKER_REPOSITORY}:deploy-${stage}.${qualifier}"
}

function get_latest_github_tag {
  case "${DEV_STRATEGY}" in
    tag)
      tags=$(curl -sk ${REPO_TAGS_URL})
      echo "$tags" | jq '.[0].name' | sed 's|"||g'
      ;;
    release)
      release=$(curl -sk ${REPO_RELEASES_URL})
      echo "$release" | jq .name | sed 'S|"||g'
      ;;
    *)
      >&2 echo "Invalid dev promotion strategy: ${DEV_STRATEGY}."
      >&2 echo "Choose from: tag, release"
      return 1
      ;;
  esac
}

function configure_deployment {
  # Cluster is always a required argument.
  if [[ -n "${RELEASE_CANDIDATE}" ]]
  then
    target_cluster=dev
  fi
  test -z "${target_cluster}" && echo "--target-cluster/-t must be supplied" && return 1
  test -n "${deploy_version}" && return 0
  # If no version was explicitly provided, we have to
  # determine the promotion version.
  case "${target_cluster}" in
    dev)
      echo "Determining deployment version for dev from latest github tag."
      deploy_version=$(get_latest_github_tag)
      echo "No version supplied, deploying latest tag ($deploy_version) to dev."
      ;;
    eval)
      deploy_version=$(get_instance_version dev)
      echo "No version supplied, promoting $deploy_version from dev to eval."
      ;;
    prod)
      if [[ -z "${rfc_number}" ]]
      then
        >&2 echo "--rfc-number/-r required when target is prod!"
        return 1
      fi
      deploy_version=$(get_instance_version eval)
      echo "No version supplied, promoting $deploy_version from eval to prod."
      ;;
    *)
      echo "No promotion configured for cluster: ${target_cluster}; you must supply
            a version number instead."
      return 1
      ;;
  esac
  if [[ -n "${GITHUB_REF}" ]]
  then
    echo "::set-output name=target-cluster::$target_cluster"
    echo "::set-output name=target-version::$deploy_version"
  fi
}

function wait_for_version_update {
  local attempts=0
  local pause_secs=10
  local max_attempts=$(( $WAIT_TIME_SECS / $pause_secs ))
  while [[ -n "1" ]]
  do
    attempts=$(( $attempts+1 ))
    if [[ "$attempts" -gt "$max_attempts" ]]
    then
      echo "Deployment did not complete within $WAIT_TIME_SECS seconds; aborting."
      return 1
    fi
    local cur_version=$(get_instance_version $target_cluster)
    if [[ "$cur_version" == "$deploy_version" ]]
    then
      echo "Deployed version matches target of $deploy_version"
      return 0
    fi
    echo "Attempt #${attempts}: Deployed $target_cluster version is $cur_version, waiting for $deploy_version" [$(date)]""
    sleep 10
  done
}

function get_image_app_version {
  local image_tag="${1}"
  docker run ${image_tag} env | grep 'HUSKY_DIRECTORY_VERSION' | cut -f2 -d= | sed 's| ||g'
}

function deploy {
  gcloud auth configure-docker gcr.io
  local version_tag=$(version_image_tag $deploy_version)
  if [[ -z "$(docker images -q ${version_tag})" ]] && ! docker pull "${version_tag}"
  then
    echo "Source image ${version_tag} does not exist locally or remotely."
    echo "You may be able to build from a git tag, if this version was already released."
    echo "Try: "
    echo "    git fetch && git checkout ${deploy_version} && ./scripts/pre-push.sh -v ${deploy_version}"
    return 1
  fi

  local app_version=$(get_image_app_version ${version_tag})
  local deploy_tag=$(deploy_image_tag $target_cluster ${app_version})

  docker build \
    -f docker/deployment.dockerfile \
    --build-arg IMAGE=$version_tag \
    --build-arg DEPLOYMENT_ID=$deploy_tag \
    -t $deploy_tag .

  echo "Tagged $deploy_version for deployment: $deploy_tag"
  if [[ -z "${DRY_RUN}" ]]
  then
    echo "Pushing tag $deploy_tag"
    docker push $deploy_tag
    if [[ -n "$GITHUB_REF" ]]
    then
      echo "::set-output name=deployed-tag::$deploy_tag"
    fi
    if [[ -z "${UNSAFE}" ]]
    then
      echo "Waiting for deployment to complete."
      wait_for_version_update
      local server_update_settle_time=30
      echo
      echo "Deployment succeeded for one pod;
            waiting ${server_update_settle_time}s for others to complete."
      sleep ${server_update_settle_time}
      echo "Settling period has ended. Running selenium tests."
      ./scripts/run-selenium-tests.sh -u "${target_cluster}"
    fi
  else
    echo "Not pushing; dry-run only."
  fi
}

set -e
configure_deployment
deploy
