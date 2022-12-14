#!/usr/bin/env bash

source ./scripts/globals.sh

function print_help {
   cat <<EOF
   Use: get-deployed-version.sh --stage <STAGE> [--debug --help]
   Options:
   -s, --stage     dev/eval/prod, or a developer instance short name.
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}


target_stage=

function parse_args {
  while (( $# ))
  do
    case $1 in
      --stage|-s)
        shift
        target_stage="$1"
        ;;
      --help|-h)
        print_help
        exit 0
        ;;
      --debug|-g)
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

  test -z "${DEBUG}" || set -x
  export DEBUG="${DEBUG}"

  if [[ -z "${target_stage}" ]]
  then
    echo "No target stage provided. Cannot continue."
    return 1
  fi
}


function get_stage_version {
  local stage=$1
  local url=$(get_stage_url $stage)
  local version=$(curl -Ssl ${url}/status | grep version | cut -f2 -d: | sed 's| ||g')
  echo "${version}"
}

function main {
  parse_args "$@" || return 1
  echo $(get_stage_version $target_stage)
}

set -e
main "$@"
