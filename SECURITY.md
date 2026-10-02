# Security

Agent Skills execute through the permissions of their host agents. Review Skills before installing them into environments with credentials, production access, destructive tools, or regulated data.

## Runtime helper policy

The optional helpers shipped in `universal-project-governance/scripts/`:

- do not require network access;
- are read-only with respect to the target project except when `inspect_project.py` receives an explicit output path;
- skip symlinked files/directories during content scanning;
- conservatively exclude common secret-like filenames and private-key formats;
- exclude common dependency/build/cache/VCS directories;
- report heuristics as signals, never as proof of safe deletion.

The Skill contract itself requires evidence before destructive deletion and stronger safeguards for data retention/integrity.

## Reporting

Before public release, a private vulnerability-reporting channel should be enabled in GitHub Security settings. Do not publish secrets or exploit details in a public issue.
