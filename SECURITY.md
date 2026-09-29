# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report them privately through GitHub:
**Security tab → Report a vulnerability** (private vulnerability reporting),
or go directly to https://github.com/kabir-sinha/socrix/security/advisories/new

Please include what you found, how to reproduce it, and the affected file or
commit. You can expect an acknowledgement within 7 days.

## Scope

SOCRIX is a Smart India Hackathon 2026 prototype. Only the latest commit on
`main` is supported; there are no maintained release branches.

## Handling data safely

- Never commit real Critical Sector Entity (CSE), employer or SOC data. Use the
  synthetic `socrix demo` data or the public Microsoft GUIDE dataset.
- Set your own `SOCRIX_PSEUDONYM_KEY` before ingesting anything real, and never
  commit it. The built-in default key is for the synthetic demo only.
- Everything under `data/` except `data/reference/` is git-ignored on purpose.
