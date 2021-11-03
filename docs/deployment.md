# Deployment

Deploying a new version of the directory simply requires that a new
docker image be tagged in the format of 

`deploy-<stage>.<deployment-id>`

`<stage>` refers to `dev`, `eval`, or `prod`.

`<deployment-id>` , can only be a  
dot-separated timestamp (2021.01.13.14.24.45 would represent
a deployment tagged on January 13, 2021, at 2:24:45 pm). 
For convenience, you should use the tag_timestamp utility in 
[common-build-scripts]()

Please see [release-process.md] for more information on the how, why, 
and what of tagging and versioning.

## Deploying manually

### ... via Github Actions

**This is only available to people who have write access to the Github repository**.

To deploy via Github Actions, simply visit the [workflow], then click `Run workflow`. 
Fill out the brief form using the guidance provided by [release-process.md]. Then 
click the next `Run workflow` button. All deployment operations will notify the
`#cloud-native-directory` slack channel.

**RFC Number** is required if deploying to `prod`. 
If no **version** is specified, a [promotion](#promotions) will occur instead.


### ... from your terminal

**This is only available to people who have write access to the GCR repository.**

Use `./scripts/deploy.sh -t <stage> -v <version> -r <rfc_number>` 

`-r, --rfc-number` is required if `-t`argeting `prod`.

If no `-v`ersion is specified, a [promotion](#promotions) will occur instead.

# Promotions

A promotion is simply a deployment that doesn't require a version input, because the 
version is sourced from the previous stage.

A promotion _to_ `dev` will deploy the latest tag on the repository.
A promotion _to_ `eval` will deploy the version to eval that is currently deployed to 
dev.
A promotion _to_ `prod` will deploy the version to prod that is currently deployed 
to eval.

When promoting to `eval` or `prod`, the previous stage's deployed version will be 
derived from that instance's `/health` endpoint, which includes the 
`version` information.


[release-process.md]: release-process.md
[workflow]: https://github.com/uwit-iam/uw-husky-directory/actions/workflows/deploy.yml
