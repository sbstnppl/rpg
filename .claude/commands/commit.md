# Commit Command

Create a git commit following the project's conventional commit format.

## Instructions

1. Check git status to see what files have been changed/staged
2. Show a diff of the changes (both staged and unstaged)
3. Review recent commits to understand the commit message style
4. Analyze the changes and draft a commit message that:
   - Uses conventional commit format (feat:, fix:, refactor:, docs:, test:, chore:, etc.)
   - Focuses on the "why" rather than the "what"
   - Is concise (1-2 sentences in the subject line)
   - Follows this format:
     ```
     type(scope): brief description

     Optional longer description if needed.
     ```
5. Stage any relevant untracked files that should be included
6. Create the commit with the message
7. Show git status after commit to verify success

## Important Rules

- **DO NOT** commit files that likely contain secrets (.env, credentials.json, etc.)
- **WARN** the user if they request to commit sensitive files
- **NEVER** run additional commands beyond git operations
- **NEVER** use the TodoWrite or Task tools
- **DO NOT** push to remote unless explicitly asked
- If pre-commit hooks modify files, check authorship before amending
- Use HEREDOC for commit messages to ensure proper formatting

## Commit Types

- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring (no behavior change)
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks (deps, config, etc.)
- `perf:` - Performance improvements
- `style:` - Code style changes (formatting, etc.)
- `build:` - Build system changes
- `ci:` - CI/CD changes

## Example

For changes that add a new API endpoint for conversation search:

```
feat(api): add conversation search endpoint

Implements full-text search across conversation messages with
pagination and filtering by date range.
```
