#!/usr/bin/env bash
# Generates the sha256 fingerprint of the current
# dependency image based on the declared lock files.
source ./scripts/globals.sh
source ./.build-scripts/sources/fingerprints.sh

function print_help {
   cat <<EOF
   Use: get-snapshot-fingerprint.sh --profile <profile> [--debug --help]

   Example:
        ./scripts/get-snapshot-fingerprint.sh -p source

   Options:
   -p, --profile   One of: [d]ependency, [s]ource, [a]ggregate
                   "--profile dependency" will emit the SHA256 hash for the
                     files that contain dependency and build information.
                   "--profile source" will emit the SHA256 hash for the source code
                   "--profile aggregate" will emit the aggregated fingerprint for
                     both the source and the dependency locks.
   -h, --help      Show this message and exit
EOF
}

while (( $# ))
do
  case $1 in
    --profile|-p)
      shift
      input_profile="$1"
      ;;

    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "Invalid Option: $1"
      print_help
      exit 1
      ;;
  esac
  shift
done

get_dependency_fingerprint() {
    lock_files=(
      pyproject.toml
      poetry.lock
      ./docker/husky-directory.dockerfile
    )
    echo $(calculate_paths_fingerprint ${lock_files[@]})
}

get_source_fingerprint() {
    echo "$(calculate_glob_fingerprint husky_directory)"
}

case "${input_profile}" in
  s|source)
    get_source_fingerprint
    ;;
  d|dep|dependency|dependencies)
    get_dependency_fingerprint
    ;;
  a|agg|aggregate)
    echo "$(calculate_string_fingerprint $(get_dependency_fingerprint):$(get_source_fingerprint))"
    ;;
  *)
    echo "${input_profile} is not a valid profile"
    exit 1
esac
