# Docker Overview

We use docker to track, test, and deploy our builds. 

## Tagging Strategy

Images tagged with `commit-X` (where `X` is the first 10 characters of a commit hash)
refer to a development build against a specific git commit.

These build images, when attached to a pull request, will also be tagged with 
`pull-request-X`, where `X` is the PR number assigned by github. This will always 
reflect the latest build of the pull request; previous builds will still be 
accessible by their commit tag above.

Images tagged with `deploy-dev.X` (where X is the first 9 chars of the commit SHA) 
are images that were tagged for deployment 
to our [development environment](https://github.com/uwit-iam/gcp-k8/tree/master/dev/uw-directory).

Images tagged with a `deploy-eval.X` (where X is the first 9 chars of the commit SHA)
automatically deployed to our eval environment. 
Currently this requires a manual promotion that can be done like so:

```
# Get the currently deployed build id in dev
BUILD_ID=$(curl -k https://uw-directory.iamdev.s.uw.edu/health | jq '.build_id' | sed s/\"//g )
# Truncate it to just the first 10 digits
BUILD_ID=${BUILD_ID:0:10}
SOURCE=gcr.io/uwit-mci-iam/husky-directory:deploy-dev.$BUILD_ID
DEST=gcr.io/uwit-mci-iam/husky-directory:deploy-eval.$BUILD_ID
docker pull $SOURCE
docker tag $SOURCE $DEST
docker push $DEST
```

## Image Retention

This is a problem that still needs solving. See IAM-258.

## GCR Image Repository

The repository for this service is gcr.io/uwit-mci-iam/husky-directory. Access to 
this repository requires operator permissions on our google project. Team members 
can reach out on slack for access if they do not have it already.

### Github Actions access to gcr.io:

If the security token for Github Actions ever needs to be updated:

1. Create a new key for the `uw-directory-github-actions` service account. Download 
   the key. 
1. Base64 encode it. (`cat $KEY_FILE_NAME | base64`)
1. Update the `GCR_TOKEN` secret in the [github repository secrets] with the 
   base64-encoded value.

_This can only be done by a person who is an administrator of this repository, and 
has access to the project IAM configuration._

## Running images

See [Running the app](running-the-app.md).

## husky-directory-base 

The application image is built on the [base image](../docker/husky-directory-base.dockerfile).
Once per week, the base image is rebuilt by default, and tagged with `:edge`.

If you ever want to know what base image was used, you can get that information from 
the application image's 'HUSKY_DIRECTORY_BASE_VERSION' environment variable. 



## development-server dockerfile

The [development-server]
creates an application that is intended to be run for testing, validation, and 
user pre-release evaluation.


[development-server]: https://github.com/uwit-iam/uw-husky-directory/tree/main/docker/development-server.dockerfile 
[poetry-base]: https://gcr.io/uwit-mci-iam/poetry
[search-image-tags]: https://github.com/uwit-iam/uw-husky-directory/tree/main/scripts/search-image-tags.sh]
[commits]: commits.md
[gcr.io]: https://gcr.io/uwit-mci-iam/husky-directory
[github repository secrets]: https://github.com/UWIT-IAM/uw-husky-directory/settings/secrets/actions
