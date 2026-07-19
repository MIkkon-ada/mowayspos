# Private GHCR image publishing gate

This repository provides a manual, fail-closed GitHub Actions gate for publishing the Moways production images to private GitHub Container Registry packages. The workflow can only be dispatched from the full commit SHA currently checked out on `main`; it has no automatic `push`, `pull_request`, scheduled, or chained trigger.

The private image repositories are:

- `ghcr.io/mikkon-ada/mowayspos-backend`
- `ghcr.io/mikkon-ada/mowayspos-frontend`
- `ghcr.io/mikkon-ada/mowayspos-postgres`

## Manual operation modes

`audit` is the default workflow-dispatch operation. It builds or pulls the three local images, runs all secret and fixable HIGH/CRITICAL vulnerability scans, inspects image contents and Docker history, and cleans up its temporary files and images. Audit mode never logs in to GHCR, checks remote tags, retags images for GHCR, pushes images, calls package visibility APIs, or creates a package.

`publish` must be selected explicitly. It performs the same complete local audit first and retains the existing fail-closed publishing sequence: only a clean audit may proceed to GHCR login, immutable-tag checks, retagging, pushing, remote digest verification, and private-package visibility verification.

When fixable HIGH/CRITICAL findings block either mode, the log emits only the vulnerability ID, package name, installed version, fixed version, and severity, together with the image name, for each sorted, de-duplicated record. It does not print vulnerability descriptions, references, or secret contents, and secret scanning remains count-only. Backend and frontend retain zero exceptions: any fixable HIGH or CRITICAL finding fails the workflow. PostgreSQL remains fail closed except for the exact reviewed gosu evidence described below.

The first publish run, `29679562418`, stopped before GHCR login and image pushing because it found one backend and 15 PostgreSQL fixable HIGH/CRITICAL vulnerabilities. The frontend count was zero, all three secret counts were zero, and no GHCR package was created. The next permitted diagnostic action is a separately reviewed audit run to obtain the sanitized list. A publish operation is allowed only after a remediation is designed independently and a later audit succeeds; these counts are historical observations, not a permanent baseline.

The reviewed audit `29680927347` identified the backend finding as CVE-2026-53539 in python-multipart 0.0.29. The backend dependency is now pinned to python-multipart 0.0.30, the published fixed version, without changing any other dependency. The same audit identified 15 fixable Go standard-library findings in the unchanged PostgreSQL 16 Alpine image. Those records originate from the gosu 1.19 binary built with go1.24.6 for linux/amd64, not from the Moways application.

After pulling the immutable PostgreSQL platform image, the gate copies `/usr/local/bin/gosu` directly from that local image and verifies its reviewed SHA256, version, Go build version, and platform. It then installs govulncheck v1.6.0 with a pinned Go 1.26.5 toolchain and scans that exact extracted executable in `binary` mode. The Go vulnerability database must cover all 15 reviewed CVE aliases (`15/15`), and any finding whose first trace frame contains a function is treated as symbol-reachable, de-duplicated, reported with safe fields only, and rejected.

A clear gosu binary reachability result does not authorize publishing by itself or suppress Trivy output. Trivy still scans the full PostgreSQL image, logs every sanitized finding, and feeds the complete de-duplicated result into the final enforcement step. There is no VEX, no allowlist file, and no ignorefile or general PostgreSQL bypass, and there is no change to the PostgreSQL image, digest selection, immutable tag, secret checks, content checks, or private-package verification.

Audit run `29682399341` failed because the report consumer incorrectly parsed govulncheck streaming JSON one physical line at a time. Govulncheck itself successfully generated the report; the consumer now uses `json.JSONDecoder().raw_decode` to decode each consecutive top-level JSON Message while preserving fail-closed handling for empty, malformed, non-object, or trailing-garbage input. This parser correction does not change gosu identity or reachability rules, the Trivy gate, or any publishing condition, and it is not evidence that vulnerabilities are clear or that publishing is allowed.

## Reviewed gosu exception

Audit run `29683559066` is the human-reviewed evidence for one narrowly bounded exception. It verified gosu 1.19, built with go1.24.6 for linux/amd64, with SHA256 `52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0`. The Go vulnerability database covered all 15 reviewed aliases (`15/15`), binary-mode symbol reachability reported zero findings, and image content and Docker history checks passed.

The exception applies only when PostgreSQL has exactly the 15 reviewed CVE records from that gosu Go standard library, every record has package `stdlib`, and every installed version is exactly `v1.24.6`. PostgreSQL secret findings must remain zero. The original 15 Trivy records and `postgres_fixable_high_critical=15` remain visible, while the gate additionally reports 15 reviewed findings, zero unreviewed findings, and a true reviewed-exception decision.

Any added CVE, missing CVE, duplicate record that changes the de-duplicated record set, package-name change, installed-version change, nonzero secret count, missing scan result, or failed preceding identity, binary-reachability, content, or history step blocks both audit and publish again. This is not a PostgreSQL-wide ignore rule. Any upstream gosu identity or scanner-result change requires a new human security review before the exact predicate may be changed.

Backend and frontend images use only the full 40-character Git commit SHA as their immutable tag. PostgreSQL starts from the fixed multi-platform upstream reference `docker.io/library/postgres:16-alpine`. The current production CVM is Ubuntu 22.04 on x86_64, so this phase selects exactly one `linux/amd64` platform manifest from the immutable upstream index and pulls it by its platform manifest digest.

The upstream index digest is retained only for source traceability. The GHCR tag remains `linux-amd64-sha256-<complete 64-character upstream platform manifest digest>` and therefore records the exact audited source of the copied `linux/amd64` content. This is not a complete multi-architecture mirror. Supporting another architecture requires a separate design and security review rather than reusing this platform tag.

Publish run `29684678470` passed every local security gate, logged in to GHCR, confirmed immutable-tag availability, and successfully pushed the backend, frontend, and PostgreSQL images. It then failed during remote PostgreSQL digest verification because it incorrectly required the GHCR top-level registry manifest digest to equal the Docker Hub source manifest digest. A registry can represent the same single-platform image content with a different top-level manifest media type, annotations, or manifest digest.

Cross-registry PostgreSQL integrity is therefore verified by strict content equivalence rather than top-level digest identity. Both source and remote documents must be valid schema-version-2 single-platform image manifests. Their config digest and size must match exactly, and every ordered layer descriptor must have the same digest and size. A changed config, changed layer, reordered layer, missing layer, added layer, malformed document, or manifest index fails closed. Top-level media type and annotations may differ because they do not change the referenced image content. The workflow records the upstream source manifest digest and the actual GHCR remote manifest digest separately, together with the common config digest and layer count, without printing either complete manifest JSON.

The gate still refuses to overwrite an existing backend or frontend tag. It never deletes or overwrites the PostgreSQL tag created by the failed first publish. If that PostgreSQL tag already exists, the gate retrieves both manifests and reuses the existing tag only after the same strict config-and-ordered-layer comparison succeeds; otherwise it fails closed. If the tag does not exist, it may be pushed once and is subjected to the same content-equivalence verification afterward.

## Security and first-publish acceptance

The workflow builds or pulls all three images locally and completes secret scanning, fixable HIGH/CRITICAL vulnerability scanning, content checks, Docker history checks, and source-label checks before logging in to GHCR. Unfixed vulnerabilities are reported by policy but do not block this gate. Fixable HIGH/CRITICAL findings remain blocking except for the exact reviewed gosu predicate above; any mismatch or scan failure occurs before any image is pushed.

`GHCR_PUBLISH_TOKEN` is supplied only to the registry login action and the package acceptance checks. Those checks use GitHub's authenticated-user `/user/packages/container/<package>` endpoint and authenticated-user versions endpoint. For each backend, frontend, and PostgreSQL package, the gate requires the exact package name, container package type, case-insensitive owner `mikkon-ada`, private visibility, the expected immutable target tag, and the absence of `latest`, `main`, and `production` tags. Existing older full-SHA versions are allowed and are not deleted. The token is never passed as a Docker build argument, written to an image or repository file, or printed. GitHub Actions logs must be treated as public: the gate emits only image names, safe digests, sanitized counts, private visibility, and sanitized failure reasons. It does not upload image archives, file lists, Docker configuration, SBOMs, complete manifests, or complete scan reports.

Before the first manual publish, a human reviewer must confirm that:

1. the selected workflow run is for the reviewed `main` commit;
2. all repository checks have passed;
3. the three target package names are correct;
4. the package visibility verification reports `private` for every package;
5. no immutable tag already exists unless it is the matching PostgreSQL digest tag.

The publishing token should be rotated according to the repository security policy and immediately after suspected exposure. A later server deployment phase will create a separate read-only package token for the runtime host. This task does not create that token.

## Scope boundary

Running this workflow is a separate, explicit human action. Creating or merging the workflow does not publish an image. This configuration does not deploy to Tencent Cloud, access a CVM, modify DNS or Docker daemon settings, configure host Nginx, run Certbot, or provide any production database password, LLM key, Tencent credential, SSH credential, PAT, or other production secret.
