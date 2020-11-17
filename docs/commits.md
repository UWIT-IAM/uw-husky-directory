# Making Meaningful Commits

When submitting or merging pull requests, **avoid** submitting timelines like this:

```
- Fix another typo
- More fedback
- Feedback from PR
- Fix typo
- Fix bug
- Fix small bug
- Add new feature to do a thing
```

Instead, submit a timeline like this:

```
- Add new feature to do a thing (EDS-1234)
```

Notice that i also added `(EDS-1234)` -- please do this. The Github repo is 
set up to autolink to EDS-prefixed Jiras if they are included in any pull request or
commit message.

In short, don't let intermediary commits bleed into the `main` timeline unless they really must be recoverable
in the future, or to properly express a large, complex change:

```
- Fix a couple of bugs with the new feature because it didn't play nicely with existing code
- Add new feature to do a thing
```

*Your box, your rules*.

Commit however you like when you're operating on your developer machine. Just curate, proof, and prepare your commit
before submitting it for pull request.

# Preparing your code for pull request

## Rebase from `main`

First, make sure your `main` branch is up to date, and then rebase your change on top of it. This ensures a linear 
timeline.

```
git switch main
git pull --rebase
git switch -
git rebase main
```

Resolve any merge conflicts.

## Reset to `main`

Next, issue a soft reset back to `main`. This will unstage all your changes without losing them, allowing you the chance
to choose which changes to lump together into which commit.

```
git reset main
```

## Proofread your changes

Before committing, you can use [Github Desktop]() to view changes almost exactly how they'll appear to your code 
reviewers within the Github pull request UI. This can be helpful as a new lens to view your code and catch 
unintended changes, leftover todos, or junky comments. This will save you a revision.

## Add and commit

Use `git status`, `git add`, and `git commit` to prepare something delightful. If you mess up, don't fret, use 
`git reset` and start again. 

## Pull request revisions

Unless a revision from a pull request is significant enough to warrant its own commit, simply use `git commit --amend` 
to incorporate feedback from pull requests. You will need to issue a force push in order to update your 
remote feature branch: `git push -f`.