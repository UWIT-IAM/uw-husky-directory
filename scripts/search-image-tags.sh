DIRECTORY_REPO_URL='https://registry.hub.docker.com/v2/repositories/uwitiam/husky-directory/tags'

list_tags() {
  # From:
  # https://forums.docker.com/t/how-can-i-list-tags-for-a-repository/32577
  curl -s $DIRECTORY_REPO_URL | jq '."results"[]["name"]' | sed 's/"//g'
}

while (( $# ))
do
  case $1 in
    # --search foo, where foo is a grep-compatible pattern
    --search)
      shift
      PATTERN=$1
  esac
  shift
done

for tag in $(list_tags)
do
  if test -n "${PATTERN}"
  then
    # Check whether the tag matches the pattern, and echo it to the terminal if so.
    echo "${tag}" | grep "${PATTERN}" >/dev/null && echo "${tag}"
  else
    # If no pattern is being searched, echo every tag.
    echo "${tag}"
  fi
done
