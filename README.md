# Quillaja greenhouse dataset software

Portable reproduction and validation utilities for **Longitudinal greenhouse images and environmental records of Quillaja saponaria**. Software version: **1.0.0**. Creator and developer: **Fan Hu** (ORCID: 0000-0002-5336-0670). Contributor: **Khalid M. Mosalam** (ORCID: 0000-0003-2988-2361); roles: **Supervision; Project administration**. This is a separate local software release candidate; the repository URL will be supplied when available. No remote publication is implied.

MIT License, Copyright (c) 2026 The Regents of the University of California. See `LICENSE`. The separate dataset, metadata and documentation record uses CC BY 4.0; this software package does not contain the dataset images or environmental measurements.

## Environment

Use Python 3.11 or newer for the complete environment (the pinned NumPy 2.3.5 requires Python ≥3.11). Timestamp inference was tested with Python 3.12.14. The standard-library-only utilities also run on Python 3.10. Manifest validation, temporal completeness and byte-preserving packaging use the standard library. Timestamp inference additionally uses the pinned packages in `requirements.txt`:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Commands below assume the downloaded flat dataset files are in `../dataset`, extracted canonical JPEGs in `../images`, and new results in `./results`. Outputs are created exclusively; existing files are never overwritten. Commands operate read-only on dataset inputs. Use a fresh output name when repeating a command.

## Manifest construction and validation

```sh
python3 scripts/public_metadata.py --dataset ../dataset --out results/public_images.csv
python3 scripts/temporal_completeness.py --dataset ../dataset --out results/completeness.json
python3 scripts/validate_public_release.py --dataset ../dataset --metadata-only --out results/metadata_validation.json
python3 scripts/validate_public_release.py --dataset ../dataset --out results/download_validation.json
```

The first command deterministically derives the public image manifest from the detailed image metadata and requires an exact match with the supplied public manifest. It does not reconstruct or revise scientific metadata from unavailable raw workbooks or review records. The temporal command reproduces the documented nearest-600-s slot calculation without changing timestamps or filling gaps. Metadata-only validation checks all public table relationships; normal download validation additionally verifies every ledger hash (requiring all listed files).

## Archive validation

The 69-file Zenodo dataset directly deposits only two complete canonical monthly archives: `QUI_GH1_2023-05.tar.gz` and `QUI_GH2_2023-05.tar.gz`. The ten June–October camera/month archives are deposited as multipart byte streams. Reconstruct each required canonical archive according to the dataset README and `archive_parts.json`, then verify its byte size and SHA-256 against that reconstruction metadata before using it as a complete archive.

Selected `--archive` validation against the deposited `checksums__SHA256SUMS.txt` ledger directly supports the two May archives. For example:

```sh
python3 scripts/validate_public_release.py --dataset ../dataset --archive QUI_GH1_2023-05.tar.gz --out results/may_validation.json
```

This selected-archive command validates the manifest tables, that archive's hash and exact member list, canonical names, byte sizes and readable payloads. With `--source-root ../images`, each archived JPEG's SHA-256 is additionally compared to its extracted canonical source file.

The deposited checksum ledger lists the June–October parts, not their reconstructed canonical archive names. Consequently, version 1.0.0 does not support selecting a reconstructed June–October archive with `--archive`, even after successful reconstruction. Verify each reconstructed archive first using its recorded size and `archive_sha256` in `archive_parts.json`; do not add reconstructed archive entries to the deposited checksum ledger.

`--payloads` requires **all twelve complete canonical monthly archives** in `../dataset`. Starting from the 69-file deposit, reconstruct the ten June–October archives locally and verify them as described above before running this mode. Keep all 69 deposited files available in that directory as well: `--payloads` first checks the deposited-file ledger, then reads the twelve complete archive payloads. It does not reconstruct multipart files automatically and can take substantial time. No JPEG decoding/re-encoding is used. Reports state the scope; a selected archive is not a full-release test.

## Rebuild a monthly archive

```sh
python3 scripts/build_release.py --manifest ../dataset/manifest__public_images.csv --images-dir ../images --output-dir results/rebuilt --camera GH-1 --month 2023-05 --dry-run
python3 scripts/build_release.py --manifest ../dataset/manifest__public_images.csv --images-dir ../images --output-dir results/rebuilt --camera GH-1 --month 2023-05 --build
```

The builder writes one monthly archive from canonical extracted JPEGs, without making another uncompressed image tree. For provenance reconstruction, `--raw-source-root` may be supplied instead of `--images-dir`; it must point to a user-provided historical source tree matching `original_relative_path`. No workstation path is embedded. The builder rejects missing files, duplicate source identities, byte-size changes and existing outputs. It records per-member source digests and the archive digest in sidecars for local verification. Sidecars are not automatic dataset deposit files. Tar metadata and gzip metadata are normalized; identical compressed bytes require the same Python/zlib behavior as well as the same inputs. Image payload bytes are invariant across compression versions.

## Timestamp inference

```sh
python3 scripts/extract_timestamps.py --manifest ../dataset/manifest__public_images.csv --images-dir ../images --release-id QUI_GH1_20230530_0001 --out results/timestamp_check.csv
```

Repeat `--release-id` for an explicit set, or use `--all` for full inference when desired. The fixed-font parser, glyph score calculation, crop and saved model are retained from the original extraction workflow. `resources/timestamp_ocr_model.json` includes fixed templates and source-relative calibration provenance; no retraining occurs. Outputs compare inferred text/times to the supplied metadata but never update accepted timestamps. Scores/margins are image contrast measures, not correctness probabilities. Missing/invalid text is reported, never repaired. The fixed crop requires original 2560 × 1440 pixels. Clock values remain timezone-unresolved; no independent clock synchronization is inferred.

## Scope and provenance

These tools preserve the published data model, source-preserving packaging rules and original timestamp inference core. `common.derive`, timestamp parsing and glyph recognition are reused from the research workflow; portable command interfaces accept public paths. This is a reproducibility subset, not the author's entire research workspace. Historical video extraction and workbook parsing are outside scope because those original sources are not deposited. Spatial reference positions and scene events are supplied observations, not regenerated annotations. No image enhancement, segmentation, geometric calibration or biological estimation is performed.
