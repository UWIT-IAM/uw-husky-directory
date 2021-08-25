#!/usr/bin/env bash

REPO_API_URL=https://api.github.com/repos/uwit-iam/uw-husky-directory

REPO_TAGS_URL="${REPO_API_URL}/tags"
REPO_RELEASE_URL="${REPO_API_URL}/release/latest"

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
    --configure-only)
      CONFIGURE_ONLY=1
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

function semver_timestamp {
  # Not really semver at all, but increments in a way that
  # is compatible and unique.
  echo $(date +%Y.%-m.%-d.%-H.%-M.%-S)
}


function version_image_tag {
  local version="$1"
  echo "gcr.io/uwit-mci-iam/husky-directory:$version"
}

function deploy_image_tag {
  local stage="$1"
  qualifier=$(semver_timestamp)
  if [[ -n "${RELEASE_CANDIDATE}" ]]
  then
    qualifier="$(whoami).${deploy_version}.${qualifier}"
  fi
  echo "gcr.io/uwit-mci-iam/husky-directory:deploy-${stage}.${qualifier}"
}

function get_version {
    local stage="$1"
    local url="https://directory.iam${stage}.s.uw.edu/health"
    local stage_status=$(curl -sk $url)
    local version=$(echo "$stage_status" | jq .version | sed 's|"||g')
    echo "$version"
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
      deploy_version=$(get_version dev)
      echo "No version supplied, promoting $deploy_version from dev to eval."
      ;;
    prod)
      if [[ -z "${rfc_number}" ]]
      then
        >&2 echo "--rfc-number/-r required when target is prod!"
        return 1
      fi
      deploy_version=$(get_version eval)
      echo "No version supplied, promoting $deploy_version from eval to prod."
      ;;
    *)
      echo "No promotion configured for cluster: ${target_cluster}"
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
    local cur_version=$(get_version $target_cluster)
    if [[ "$cur_version" == "$deploy_version" ]]
    then
      echo "Deployed version matches target of $deploy_version"
      return 0
    fi
    echo "Attempt #${attempts}: Deployed $target_cluster version is $cur_version, waiting for $deploy_version" [$(date)]""
    sleep 10
  done
}

function pull_version {
  test -z "${NO_PULL}" || return 0
  local version="$1"
  local image=$(version_image_tag $version)
  if ! docker pull $image
  then
    >&2 echo "Could not pull docker image $image"
    return 1
  fi
}

function deploy {
  gcloud auth configure-docker
  local version_tag=$(version_image_tag $deploy_version)
  local deploy_tag=$(deploy_image_tag $target_cluster)
  pull_version $version_tag
  docker build \
    -f docker/deployment.dockerfile \
    --no-cache \
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
    echo "Waiting for deployment to complete."
    wait_for_version_update
  else
    echo "Not pushing; dry-run only."
  fi
}

set -e
configure_deployment
if [[ -z "${CONFIGURE_ONLY}" ]]
then
  deploy
fi
