# Application-images-only security release design

## Goal

Allow the private GHCR release gate to publish only the Moways backend and
frontend images after their security findings are remediated. PostgreSQL is
outside this release and deployment scope.

## Scope boundary

- Do not connect to a CVM, database, or Docker daemon outside GitHub Actions.
- Do not run Alembic, initialize a schema, recreate PostgreSQL, pull a
  PostgreSQL image for deployment, or change a PostgreSQL volume.
- Do not add a PostgreSQL CVE allowlist or weaken the existing fail-closed
  policy.
- The release workflow publishes only the two application packages:
  `mowayspos-backend` and `mowayspos-frontend`.

## Design

### Backend remediation

The backend image will update its operating-system packages during its normal
image build, then install the project requirements. This consumes the Debian
security updates for the `util-linux` findings without adding a package source
or changing application startup.

The pinned `pypdf` and `cryptography` requirements will be raised to the
lowest versions that the security scanner reports as fixed. Their existing
imports and public configuration are unchanged.

### GHCR workflow

The publish workflow will retain the main-branch, full-SHA, local build,
secret-scan, vulnerability-scan, content-check, immutable-tag, and
private-visibility gates for backend and frontend images.

It will remove PostgreSQL-specific source resolution, gosu identity and
reachability checks, PostgreSQL scanning, PostgreSQL tag creation, PostgreSQL
pushes, and PostgreSQL package acceptance checks. This is a scope reduction,
not a security exception: PostgreSQL is no longer an artifact produced by this
application-release workflow.

### Documentation

The GHCR publishing guide will name only the two application packages and
state that the workflow cannot change a database. The CVM guide will gain a
clearly separated existing-database application-update procedure that pulls
and recreates only backend and frontend services; it explicitly excludes
`postgres` and Alembic.

## Validation

1. Add regression checks that enforce the two-image workflow contract and
   forbid PostgreSQL deployment commands in the existing-database update
   procedure.
2. Run the focused regression checks before and after the implementation.
3. Build the backend image locally and run the relevant backend tests.
4. Dispatch an `audit` on the merged main commit. It must report zero secret
   findings and zero fixable HIGH/CRITICAL findings for backend and frontend,
   with no PostgreSQL release stage.

## Rollback

This change does not deploy anything. A future image publish remains explicit
and immutable. Reverting the merge commit restores the prior three-image
workflow; it does not affect an existing database or its data.
