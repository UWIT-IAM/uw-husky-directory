# Release Process

This product is released in three stages: `dev`, `eval`, and `prod`.

Additionally, all releases are versioned using [semver]. This process is
mostly automated, but you should keep reading to understand the strategy
and options available.

## versioning

A new version should be created any time a change is _accepted into the `main` branch_.
In this way, every merge into this branch will be explicitly versioned, and will 
therefore be available for deployments and as a rollback point.

When you open a pull request (PR), your PR checks will fail until you supply
a **semver-guidance label**. You can add this label directly from the 
Github UI, as long as you have the correct permissions. If you don't, then your 
PR reviewer can add this guidance for you.

You should supply guidance using the following rhetoric:

- `no-bump` if the change under review does not alter ANY functionality (i.e., only
  changes documentation).
- `patch` if the change under review: fixes a bug, updates configuration, or 
improves stability/performance without directly changing the user experience.
- `minor` if the change under review: adds a new feature, directly changes the user 
experience in any way.
- `major` if the change under review: dramatically shifts the user experience (e.g., 
a front-end redesign), turns off long-standing features, or otherwise departs from 
the flow and experience users are used to.

Each new version update to the `pyproject.toml` file (made using `poetry version 
$NEW_VERSION`) should also correspond to an annotated git tag (e.g., `git tag -a 
$NEW_VERSION && git push $NEW_VERSION`).

This means that every change to the semver in `pyproject.toml` should be the HEAD of 
a new tag matching that version.

## docker tagging

In addition to versioning the code and tagging the repo, this package makes liberal 
use of docker tags to show the path of a change through time.

- When a change is built by an automated process, the commit SHA is used to tag the 
image (`husky-directory:commit-ABCDE1234`).
- When a pull request is opened on a change, the PR number is used to create an 
additional tag (`husky-directory:pull-request-123`).
- When a change is accepted, and a new version is created, the image is tagged
with the new version number (`husky-directory:2.3.4`).
- When a change is deployed, a new image layer is created on top of the release 
  that is tagged with the deployment id: (`husky-directory:deploy-dev.2021.9.1.11.39)`. 
  The new layer is necessary because Flux (v1) uses _timestamps_ for non-semver
  deployment automation, so we must necessarily create a new layer that has an updated
  timestamp.

In this way, you can review the docker repository to see the complete history of a 
change. 

For instance, if you saw that an image had the all the above tags, you would know
that pull request 123 was opened for commit ABCDE1234. When the pull request was 
accepted, it generated the 2.3.4 version of the application, which was then deployed
to dev on September 1, 2021, at 11:39 am. Once the change is released to eval and prod,
you would also see additional `deploy-eval` and `deploy-prod` tags, respectively.

The use case for the `deploy-dev.<timestamp>` tag is to allow us to _roll back to 
any previous version at any time._ Relying only on the semver for a deployment
makes it hard to roll an instance back, because flux (our automated deployment tool)
only deploys progressively. 

By triggering our deployments on the `deploy-<stage>.<timestamp>` pattern, flux will
always deploy the latest deploy _timestamp_, no matter which version it's attached 
to. Additionally, any rollback deployments will be evident in the tagging history
for a given image.


## Stages

This section talks only about how and when deployments occur. To find out about
deploying manually, read [deployment.md](deployment.md).

### Releasing to dev

Releases to dev should occur whenever a new version is created. 

Releases to dev are done **AUTOMATICALLY** any time a change is accepted into 
the `main` branch. If there are any problems, you may deploy to dev manually.

### Releasing to eval

Releases to eval should occur at least a week prior to any desired release to prod. 
However, in an ideal world, eval would be kept up to date with dev in real time. 
Currently there is no automation, so this must be done manually.

### Releasing to prod

Releases to prod must have an RFC that includes a communications plan. Because this is 
a publicly available product, we should take care to avoid any downtime, and provide 
adequate communications if any downtime is required. 



[semver]: https://www.semver.org
