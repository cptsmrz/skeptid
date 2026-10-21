# Git Workflow Rules

## 1. General Rules

* Treat the current Git repository as the source of truth for version history.
* Before making changes, inspect `git status` and understand the current branch.
* Never discard, overwrite, or revert the user's existing work without explicit permission.
* Never commit secrets, API keys, passwords, access tokens, `.env` files, or other sensitive data.

## 2. Normal Development

* Implement requested changes in the current working branch unless instructed otherwise.
* After implementation, run relevant tests or validation commands when practical.
* Summarize the files changed, important implementation decisions, and test results.
* Do not create a commit or push changes automatically.

## 3. GitHub Publishing

Only commit or push when I explicitly ask you to do so.

Examples of explicit instructions:

* "Commit these changes."
* "Push this implementation to GitHub."
* "Commit and push the completed feature."

Before committing:

1. Run `git status`.
2. Review the changes using `git diff`.
3. Inspect staged changes using `git diff --cached` when applicable.
4. Check for accidental changes, unrelated files, secrets, and generated artifacts.
5. Stage only the intended files.
6. Create a descriptive commit message.
7. Report the resulting commit hash.

Before pushing:

1. Confirm the intended remote and branch.
2. Check whether the remote branch has changes that need to be integrated.
3. Never force-push, rewrite shared history, or overwrite remote changes without my explicit permission.
4. Push only after verifying that the changes are appropriate to publish.
5. Report the push result.

## 4. Safety

* Never use `git reset --hard`, `git clean -fd`, or destructive Git commands without explaining their impact and obtaining my explicit permission.
* Never bypass Git hooks, repository protections, or authentication safeguards.
* If a merge conflict, unexpected remote change, authentication error, or potentially destructive action occurs, stop and explain the situation.
* Ask for confirmation before publishing if the target branch, intended files, or consequences are unclear.

## 5. Completion Reports

After completing a task, clearly distinguish between:

* Changes made locally
* Changes committed locally
* Changes pushed to GitHub

Never claim that changes have been pushed unless the push command succeeds.
