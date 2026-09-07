# CI Poppler Runtime Gate Design

## Goal

Make the GitHub production runtime gate provide the same Poppler capability as
the backend Docker image so scanned-PDF Vision fallback tests execute in CI.

## Design

- Install `poppler-utils` in the Ubuntu GitHub Actions runner before backend
  tests run.
- Keep the existing `pdftoppm` renderer and its bounded page/size protections.
- Do not replace renderer tests with mocks: CI must exercise the real binary.
- Do not alter application behavior, interfaces, or the Docker runtime image.

## Verification

- Confirm `pdftoppm` is available in the gate after dependency setup.
- Run the existing full backend pytest gate and require no unexpected failures.
