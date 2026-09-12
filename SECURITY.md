# Security policy

## Supported versions

We aim to support the latest release on [PyPI](https://pypi.org/project/testrisk/). Security fixes are applied to the current minor line when practical.

## Reporting a vulnerability

**Please do not open a public GitHub issue for undisclosed security problems.**

Instead, email **karlhillx@gmail.com** with:

- A short description of the issue
- Steps to reproduce (if possible)
- Affected testrisk version and environment (OS, Python version)

We will acknowledge receipt and work on a fix and release timeline.

## Scope notes

testrisk **reads local coverage artifacts, source files, and git diffs**. It does not execute your test suite or production code. Reports about “arbitrary code execution” because a malicious repo contains a `.coverage` file or Python source are generally out of scope unless they involve a bug in testrisk itself (for example unsafe subprocess arguments or path traversal outside the requested repo).
