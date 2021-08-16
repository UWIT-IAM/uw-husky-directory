# .github/steps

This directory houses scripts and resources used by workflow steps. 

Scripting individual steps makes it easier to maintain, test, and debug
workflows. Wherever is practical, strive to move
behavior into scripts, and out of actions yml files themselves.

## Structure

Each subdirectory in `steps` should match the name of a workflow, and any included 
scripts should match a declared step id in the workflow. This is just to make it 
easier to navigate. 

To share scripts between workflows, it's best to put them in a common `steps/shared` 
directory so that the intent is clear.

```
+ .github
| + steps
| | + <workflow-name>
| | | - <filename>
| | + shared
```

## Capabilities

These scripts are meant to be run via Github Actions, and therefore may rely on 
environment variables, etc. provided by Actions or the workflow.


## Constraints

- Scripts cannot contain github context syntax (e.g., `${{ foo }}`); any such
syntax will not be interpolated. 
