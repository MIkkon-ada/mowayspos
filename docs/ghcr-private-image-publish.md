# Private GHCR image publishing gate

This repository provides a manual, fail-closed GitHub Actions gate for publishing the Moways production images to private GitHub Container Registry packages. The workflow can only be dispatched from the full commit SHA currently checked out on `main`; it has no automatic `push`, `pull_request`, scheduled, or chained trigger.

The private image repositories are:

- `ghcr.io/mikkon-ada/mowayspos-backend`
- `ghcr.io/mikkon-ada/mowayspos-frontend`
- `ghcr.io/mikkon-ada/mowayspos-postgres`

Backend and frontend images use only the full 40-character Git commit SHA as their immutable tag. PostgreSQL starts from the fixed multi-platform upstream reference `docker.io/library/postgres:16-alpine`. The current production CVM is Ubuntu 22.04 on x86_64, so this phase selects exactly one `linux/amd64` platform manifest from the immutable upstream index and pulls it by its platform manifest digest.

The upstream index digest is retained only for source traceability. The GHCR tag is `linux-amd64-sha256-<complete 64-character platform manifest digest>`, and overwrite prevention and post-push integrity verification both compare the GHCR manifest with that `linux/amd64` platform manifest digest. This is not a complete multi-architecture mirror. Supporting another architecture requires a separate design and security review rather than reusing this platform tag.

The gate refuses to overwrite an existing backend or frontend tag. An existing PostgreSQL platform tag is accepted only when its remote digest still matches the selected `linux/amd64` digest; otherwise the gate fails.

## Security and first-publish acceptance

The workflow builds or pulls all three images locally and completes secret scanning, fixable HIGH/CRITICAL vulnerability scanning, content checks, Docker history checks, and source-label checks before logging in to GHCR. Unfixed vulnerabilities are reported by policy but do not block this gate; any fixable HIGH or CRITICAL vulnerability does. A scan failure occurs before any image is pushed.

`GHCR_PUBLISH_TOKEN` is supplied only to the registry login action and the package visibility check. It is never passed as a Docker build argument, written to an image or repository file, or printed. GitHub Actions logs must be treated as public: the gate emits only image names, safe digests, sanitized counts, private visibility, and sanitized failure reasons. It does not upload image archives, file lists, Docker configuration, SBOMs, or complete scan reports.

Before the first manual publish, a human reviewer must confirm that:

1. the selected workflow run is for the reviewed `main` commit;
2. all repository checks have passed;
3. the three target package names are correct;
4. the package visibility verification reports `private` for every package;
5. no immutable tag already exists unless it is the matching PostgreSQL digest tag.

The publishing token should be rotated according to the repository security policy and immediately after suspected exposure. A later server deployment phase will create a separate read-only package token for the runtime host. This task does not create that token.

## Scope boundary

Running this workflow is a separate, explicit human action. Creating or merging the workflow does not publish an image. This configuration does not deploy to Tencent Cloud, access a CVM, modify DNS or Docker daemon settings, configure host Nginx, run Certbot, or provide any production database password, LLM key, Tencent credential, SSH credential, PAT, or other production secret.
