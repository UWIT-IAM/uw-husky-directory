#!/usr/bin/env bash

function print_help {
   cat <<EOF
   Use: run-selenium-tests.sh [--debug --help]
   Options:
   -h, --help      Show this message and exit
   -g, --debug     Show commands as they are executing
EOF
}

uw_directory_url="${uw_directory_url}"
pytest_args="${pytest_args}"

parse_args() {
  while (( $# ))
  do
    case $1 in
      --help|-h)
        print_help
        exit 0
        ;;
      --debug|-g)
        DEBUG=1
        ;;
      --uw-directory-url|-u)
        shift
        uw_directory_url="$1"
        ;;
      --)
        shift
        pytest_args="$@"
        return
        ;;
      *)
        echo "Invalid Option: $1"
        print_help
        return 1
        ;;
    esac
    shift
  done
  test -z "${DEBUG}" || set -x
}

parse_args "$@" || exit $?
export DEBUG="${DEBUG}"

export pytest_args="${pytest_args}"
export uw_directory_url="${uw_directory_url}"

docker-compose -f docker/docker-compose.selenium.yml up \
  --exit-code-from test-runner
