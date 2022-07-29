HUSKY_DIRECTORY_VERSION=${HUSKY_DIRECTORY_VERSION:-$(poetry version -s)}
$(poetry run fingerprinter -o build-script) -p \
  --build-arg HUSKY_DIRECTORY_VERSION=${HUSKY_DIRECTORY_VERSION} \
  $@
