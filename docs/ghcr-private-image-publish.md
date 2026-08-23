# Private GHCR application-image publishing gate

This manual GitHub Actions workflow releases only two application images:

- `ghcr.io/mikkon-ada/mowayspos-backend`
- `ghcr.io/mikkon-ada/mowayspos-frontend`

It can be dispatched only from `main` at a complete 40-character commit SHA.

## Operation modes

`audit` builds both local images and runs secret, fixable HIGH/CRITICAL vulnerability, content, and Docker-history checks. Audit mode does not log in to GHCR, create a package, inspect remote tags, or push an image.

`publish` repeats the complete audit. Only a clean audit can log in, verify absent immutable tags, push the two SHA-tagged images, verify their remote digests, and require private package visibility. Mutable `latest`, `main`, and `production` tags are rejected.

Any secret finding or fixable HIGH/CRITICAL vulnerability in either image fails both modes. The workflow prints only sanitized finding metadata and never uploads scan reports.

## Database boundary

The workflow does not publish, pull, recreate, or migrate PostgreSQL. It has no PostgreSQL package, image, scanner exception, CVM connection, schema command, or database credential.

Publishing images is not deployment. A CVM application update and any database operation are separate explicit actions.
