# Logs in to gcr using the GCR_TOKEN environment variable, which
# must be a base64-encoded secret json key, set from a github secret.

set -e

echo "${GCR_TOKEN}" | base64 -d |
  docker login --username _json_key --password-stdin https://gcr.io
