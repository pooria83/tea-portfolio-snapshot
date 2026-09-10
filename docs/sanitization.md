# Sanitization and verification

## Scope and provenance

Five default-branch snapshots are pinned in [snapshot-manifest.json](snapshot-manifest.json), with source commit IDs, original blob IDs, final SHA-256 hashes, exclusions, and sanitization reasons. Git object contents were read from local source repositories and matched to GitHub default-branch manifests. Working-tree changes and original `.git` histories were not copied.

The destination `pooria83/tea-portfolio-snapshot` was verified private with write permission before any destination content was created. Only this destination is authorized for remote writes. Source repositories were used read-only.

## Sensitive material handled

The API source contained `certs/origin.key`, certificate files, Cloudflare tunnel credential material, and `cookies.txt`. All were excluded wholesale before staging; actual contents are not reproduced here. Mobile environment and keystore files, web certificate material, and every `.env`/`.env.*` file (including examples) were also excluded. Sensitive-file detection does not assert that the contained credentials are currently active.

Credential-bearing sample connection strings were replaced with redacted placeholders. Credential defaults in Compose were changed to explicit local-review configuration requirements. Deployment hostnames and operational IP addresses were replaced with reserved example addresses. Development seed account passwords/contact details were sanitized. Golden-dataset development catalog identifiers were removed while retaining all 166 queries and locale fields.

Local tooling instructions/hooks, organization project automation, operational runbooks, binary assets/fonts/images, notebook files with potential output/configuration, signing material, and irrelevant generated artifacts were excluded. Lockfiles, source, migrations, schemas, tests, and selected technical documentation remain. The manifest gives the exact path-level list; no source file was deleted or edited.

## What remains intentionally

Variable names such as `API_KEY`, code that validates credentials, `${...}` secret references, empty configuration defaults, and obvious synthetic test credentials are necessary engineering context. Their presence is not evidence that a live credential was copied. No actual `.env`, key file, cookie file, credential JSON, or production database dump is included.

## Execution limitations

This repository is self-contained for source review, not a turnkey runnable deployment. Original module commands can reference omitted environment files, TLS files, native assets/fonts, signing files, or operational documentation. Those exclusions are deliberate. Production hostname replacements use reserved example values. Some sanitized sample URLs are illustrative placeholders and must be replaced before configuration validation or startup.

The original application's source and tests have not been redesigned. A local execution attempt would require isolated databases/model services, independently supplied test-only configuration, and appropriate dependency installation. Never use a production database for the API suite: its test fixture creates and drops schema objects. No services or source setup scripts were run for this migration.

## Validation performed

- Pinned GitHub source commit manifests and original Git blob hashes for retained source reads.
- Inspected excluded credential/key/cookie paths and scanned retained UTF-8 content for private-key markers, known provider-token formats, JWT literals, credential-bearing URLs, literal credentials, deployment identities, and high-entropy string candidates.
- Repeated final scans after documentation and sanitization; verified prohibited paths are absent and source-file hashes match the final manifest.
- Parsed retained Python source with the available Python interpreter and parsed JSON files, retaining source language/runtime requirements in their original manifests.
- Executed focused checks against the actual extracted `_metric_item` implementation: top-10 cutoff, averaging, missed relevant items, and exclusion of unjudged queries. This checks metric behavior without connecting to application services; it is not the full API test suite.
- Did not execute full application test suites, model inference, browser/native builds, deployment, or live retrieval evaluation. No successful coverage or performance claim is made.

The review is a best-effort secret/sensitive-data inspection, not a guarantee against every possible confidential string or vulnerability. Final publication verification is recorded in the completion report with the destination commit.
