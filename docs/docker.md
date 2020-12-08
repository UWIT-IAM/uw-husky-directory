# Docker Overview

We use docker to track, test, and deploy our builds. 

## Tagging Strategy

Images tagged with `commit-X` (where `X` is the first 10 characters of a commit hash)
refer to a development build against a specific git commit.

Images tagged with `deploy-dev.commit-X` are images that were tagged for deployment 
to our [development environment](https://github.com/uwit-iam/gcp-k8/tree/master/dev/uw-directory).

Images tagged with a [sem ver](https://www.semver.org) `X.Y.Z` will be automatically 
deployed to our eval environment. (Which is not currently configured.)

Images tagged with both `prod` and a released sem ver tag (i.e., when one of those 
sem ver tags is also tagged with `prod`), then it will also be deployed to prod. 
(The prod environment is not currently configured.)

## Searching tags

You can use the included [search-image-tags] script to look for tags. This lets you run 
any previously built and pushed image from any point in time using our tagging 
strategy above.

Some recipes:

```
# List all tags (sorted newest->oldest)
./scripts/search-image-tags.sh

# Limit output to 10 most recent pushes (just use a pager)
./scripts/search-image-tags.sh | head -n 10

# Search for tags that were deployed to dev
# The "search" argument can be a regex; it uses grep under the hood.
./scripts/search-image-tags.sh --search deploy-dev

# Search for tags associated with a specific commit
./scripts/search-image-tags.sh --search f115
```

*NOTE*: Only commits that triggered a built (or were specifically built and pushed
by a human) will have an associate image tag. With clean [commits], *most* 
github-visible commits should have an associated image tag; just don't expect this 
for *every* commit.


## Running images

Refer to docker documentation for advanced use cases.

You can run any published tag:

`docker run -it uwitiam/husky-directory:${TAG}`


# DockerHub Images

This project is open source, and so the images can live for free on DockerHub.



## development-server

The [development-server]
creates an application that is intended to be run for testing, validation, and 
user any pre-release evaluation.

On Dockerhub, you can find published development-server builds tagged as `commit-X`, 
where `X` is the commit hash associated with the build. 

See also: [husky-directory] docker repository.


## poetry-base

The [poetry-base] image is a relatively static image that shouldn't need updating 
very often. It is responsible for giving us a base platform with a properly configured 
python and poetry environment.

This should only be updated if we need to refresh or update python itself, or its
poetry installation:

```
docker build -f docker/poetry-base -t uwitiam/poetry-base .`
docker push -t uwitiam/poetry-base
```

Storing this layer separately speeds up our builds substantially, as this hefty
layer can then be cached.


[development-server]: https://github.com/uwit-iam/uw-husky-directory/tree/main/docker/development-server.dockerfile 
[poetry-base]: https://hub.docker.com/repository/docker/uwitiam/poetry
[husky-directory]: https://hub.docker.com/repository/docker/uwitiam/husky-directory
[search-image-tags]: https://github.com/uwit-iam/uw-husky-directory/tree/main/scripts/search-image-tags.sh]
[commits]: commits.md
