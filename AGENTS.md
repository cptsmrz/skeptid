# Git Workflow Rules

## 1. General Rules

* Treat the current Git repository as the source of truth for version history.
* Never discard, overwrite, or revert the user's existing work without explicit permission.
* Never commit secrets, API keys, passwords, access tokens, `.env` files, or other sensitive data.

## 2. Normal Development

* Implement requested changes in the current working branch unless instructed otherwise.
* Summarize the files changed, important implementation decisions, and test results when practical.
* Do not commit or push automatically during general coding tasks—only when asked.

## 3. GitHub Publishing

### Streamlined Flow (Default)
* When explicitly asked to commit or push (e.g., "commit and push", "push this", or commands like `git add .`, `git commit`, `git push`), **execute the add, commit, and push directly**.
* Use the provided commit message (or generate a concise, descriptive conventional message if unspecified or partial).
* Keep friction low: do not block with questionnaires, modals, or multi-step interrogations for routine commits.

### When to "Go Deep" and Pause
Only stop for confirmation or investigate deeper when genuinely necessary:
1. **Secrets / Sensitive Data:** Potential API keys, passwords, tokens, or `.env` files detected in staged changes.
2. **Remote Divergence / Conflicts:** Non-fast-forward push, merge conflicts, or unexpected upstream changes requiring integration.
3. **Destructive Actions:** Any command that risks discarding uncommitted work or rewriting remote history.
4. **Fatal Errors:** Authentication failures or git network errors.

## 4. Safety Constraints

* Never use `git reset --hard`, `git clean -fd`, or destructive Git commands without explaining their impact and obtaining explicit permission.
* Never force-push (`--force` or `--force-with-lease`) without explicit instruction.
* Never bypass Git hooks, repository protections, or safety mechanisms.

## 5. Completion Reports

After committing or pushing, give a concise summary reporting:
* Files committed & commit hash
* Push status and destination branch
