#!/usr/bin/env bash

source ./.build-scripts/sources/slack.sh
ACTOR=${GITHUB_ACTOR}
SLACK_CHANNEL='#cloud-native-directory'

github_workspace=${GITHUB_WORKSPACE:-.}
step_scripts=${github_workspace}/.github/steps/deploy

function print_help {
   cat <<EOF
   Use: get_slack_notification.sh [--debug --help]
   Options:
   -b, --block      The notification block to get. (default: canvas)
   -v, --version    The version being deployed (e.g., 1.2.3)
   -s, --stage      The stage being deployed to (e.g., dev)
   -q, --qualifier  An optional qualifier for the deployment (e.g., 'DRY-RUN', 'RFC-1234')
                    REQUIRED if deploying to prod.
   -a, --actor      An optional actor for the deployment; REQUIRED if deploying to prod.
                    (e.g., '@husky')
   -c, --channel    The slack channel to send notifications to
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

BLOCK=canvas

while (( $# ))
do
  case $1 in
    --block|-b)
      shift
      BLOCK="$1"
      ;;
    --version|-v)
      shift
      VERSION="$1"
      ;;
    --stage|-s)
      shift
      STAGE="$1"
      ;;
    --actor|-a)
      shift
      ACTOR="$1"
      ;;
    --qualifier|-q)
      shift
      QUALIFIER="$1"
      ;;
    --channel|-c)
      shift
      SLACK_CHANNEL="$1"
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

function replace_template {
  echo "$1" | sed "s|\${{ $2 }}|$3|g"
}

function build_canvas {
  # The echo/cat construct reduces the output to a single
  # line, making it easier to pass around and work with.
  template="$(echo $(cat ${step_scripts}/canvas.json))"
  template=$(replace_template "$template" stage $STAGE)
  template=$(replace_template "$template" version $VERSION)
  template=$(replace_template "$template" qualifier $QUALIFIER)
  template=$(replace_template "$template" slack_channel $SLACK_CHANNEL)
  echo "$template"
}

function build_context_artifact {
  actor_link=$(slack_link "https://github.com/$ACTOR" "@${ACTOR}")
  execution_link=$(slack_link "https://github.com/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}" execution)
  echo "Triggered by ${GITHUB_EVENT_NAME} from $actor_link ($execution_link) on $(date)"
}

function_name="build_${BLOCK}"
$function_name
