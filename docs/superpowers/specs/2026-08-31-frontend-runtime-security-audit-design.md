# Frontend runtime security audit remediation

## Goal

Remove the two fixable high-severity OpenSSL findings reported by the private-image audit for the frontend runtime image, without publishing an image.

## Scope

- Keep the existing Node build stage and Nginx Alpine runtime image.
- Upgrade Alpine packages in the final runtime stage during the Docker build.
- Preserve the existing Nginx configuration, image entrypoint, and published port.

## Out of scope

- Changing the application source, dependency lockfile, or backend image.
- Publishing GHCR images.
- Replacing the Nginx distribution or changing deployment topology.

## Verification

1. Build the frontend image through the existing GitHub Actions audit workflow.
2. Confirm no secret findings and no fixable HIGH or CRITICAL vulnerabilities.
3. Confirm the workflow remains in audit mode, so no image push steps run.
