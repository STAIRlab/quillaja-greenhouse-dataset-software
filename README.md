# Quillaja greenhouse dataset software

Portable reproduction and validation utilities for **Longitudinal greenhouse images and environmental records of Quillaja saponaria**. Software version: **1.0.1**. Creator and developer: **Fan Hu** (ORCID: 0000-0002-5336-0670). Contributor: **Khalid M. Mosalam** (ORCID: 0000-0003-2988-2361); roles: **Supervision; Project administration**. This repository contains the public software release v1.0.1.

MIT License, Copyright (c) 2026 The Regents of the University of California. See `LICENSE`. The separate dataset, metadata and documentation record uses CC BY 4.0; this software package does not contain the dataset images or environmental measurements.

## Environment

Use Python 3.11 or newer for the complete environment (the pinned NumPy 2.3.5 requires Python ≥3.11). Timestamp inference was tested with Python 3.12.14. The standard-library-only utilities also run on Python 3.10. Manifest validation, temporal completeness and byte-preserving packaging use the standard library. Timestamp inference, green-pixel-fraction computation and mask reproduction use the pinned packages in `requirements.txt`:

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

The 70-file Zenodo dataset directly deposits only two complete canonical monthly archives: `QUI_GH1_2023-05.tar.gz` and `QUI_GH2_2023-05.tar.gz`. The ten June–October camera/month archives are deposited as multipart byte streams. Reconstruct each required canonical archive according to the dataset README and `archive_parts.json`, then verify its byte size and SHA-256 against that reconstruction metadata before using it as a complete archive.

Selected `--archive` validation against the deposited `checksums__SHA256SUMS.txt` ledger directly supports the two May archives. For example:

```sh
python3 scripts/validate_public_release.py --dataset ../dataset --archive QUI_GH1_2023-05.tar.gz --out results/may_validation.json
```

This selected-archive command validates the manifest tables, that archive's hash and exact member list, canonical names, byte sizes and readable payloads. With `--source-root ../images`, each archived JPEG's SHA-256 is additionally compared to its extracted canonical source file.

The deposited checksum ledger lists the June–October parts, not their reconstructed canonical archive names. Consequently, version 1.0.1 does not support selecting a reconstructed June–October archive with `--archive`, even after successful reconstruction. Verify each reconstructed archive first using its recorded size and `archive_sha256` in `archive_parts.json`; do not add reconstructed archive entries to the deposited checksum ledger.

`--payloads` requires **all twelve complete canonical monthly archives** in `../dataset`. Starting from the 70-file deposit, reconstruct the ten June–October archives locally and verify them as described above before running this mode. Keep all 70 deposited files available in that directory as well: `--payloads` first checks the deposited-file ledger, then reads the twelve complete archive payloads. It does not reconstruct multipart files automatically and can take substantial time. No JPEG decoding/re-encoding is used. Reports state the scope; a selected archive is not a full-release test.

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

These tools preserve the published data model, the original timestamp inference core, and byte-preserving packaging of the selected released JPEGs. Version 1.0.1 additionally supports documented head masking and the fixed-region green-pixel fraction. `common.derive`, timestamp parsing and glyph recognition are reused from the research workflow; portable command interfaces accept public paths. This is a reproducibility subset, not the author's entire research workspace. Historical video extraction and workbook parsing are outside scope because those original sources are not deposited. Spatial reference positions and scene events are supplied observations, not regenerated annotations. No image enhancement, geometric calibration or biological estimation is performed. The green-pixel fraction is a colour-classified image index, not calibrated ground cover. Masking reproduces documented author-approved rectangles; it does not run a detector or infer new boxes.

## Masked-release validation (v1.0.1)

Released JPEG byte totals are checked against `package_plan.json` instead of a fixed original-byte constant. The 38,177-image scope, camera counts, canonical IDs, dimensions and archive memberships remain checked. `metadata__image_notes.csv` is validated for known IDs, note types, duplicate keys, nonempty descriptions, MCU geometry and timestamp protection. Updated detailed metadata retains `original_file_size_bytes` as extraction provenance; released `file_size_bytes` must agree with the public image manifest. Keep `package_plan.json` beside a public manifest used by any command.

You may store the twelve complete canonical archives separately from the 70-file flat deposit. This avoids placing reconstructed archives in the upload directory:

```sh
python3 scripts/validate_public_release.py --dataset ../dataset --archives-dir ../complete_archives --payloads --image-hashes-out results/jpeg_sha256.csv --out results/full_validation.json
```

This validates every deposited checksum, complete archive hash/size and payload member. The optional CSV records each observed JPEG SHA-256 for comparison with an independently frozen source ledger. It does not itself establish provenance without that independent reference. Existing selected `--archive` ledger limitations for June–October remain; use `--payloads` for all reconstructed archives.

## Apply documented head masks

Mask reproduction requires the original unmasked canonical JPEGs, which are author-held inputs and are not supplied by the masked deposit. A masked JPEG cannot recover those originals. `jpegtran` must be installed separately (libjpeg-turbo 3.2.0 was used for the release). The script creates only the affected copies, with no new padding, head-box inference or keep-area recomputation:

```sh
python3 scripts/apply_head_masks.py --dataset ../dataset --images-dir ../unmasked_images --output-dir results/masked_images
```

The actual xyxy wipe rectangles are read from `person_masked` rows in `metadata__image_notes.csv`. Grey DCT blocks are written using `jpegtran -copy none -optimize -wipe`; quantization and geometry are retained. Existing outputs are refused. The report records source/output hashes and the tool version. Use these verified copies alongside unchanged original JPEGs for an archive rebuild; the package manifest records released sizes.

## Green-pixel fraction

The fixed polygon and colour thresholds are in `resources/green_fraction_region.json`. The colour rule follows Patrignani and Ochsner (2015), [Canopeo](https://doi.org/10.2134/agronj15.0150). This command reproduces GH-1 daily medians over 15:00 to 18:00 on complete acquisition-window dates at half scale. It can read complete archives directly or use `--images-dir` for canonical extracted JPEGs:

```sh
python3 scripts/green_pixel_fraction.py --dataset ../dataset --archives-dir ../complete_archives --out-dir results/green_fraction
```

Outputs are per-frame values and source hashes, daily medians, and a summary including the detrended day-to-day noise. The strict 8-bit RGB rule is R/G<0.95, B/G<0.95 and 2G−R−B>20. Minute endpoints are inclusive despite second-level timestamp jitter; missing slots are not imputed. The region covers 71.6068% of the saved image. Uncorrected wide-angle geometry and growth toward the camera prevent interpretation as calibrated ground cover.

## Tests

```sh
python3 -B -m unittest discover -s tests -v
```

The tests cover changing package totals without weakening scope checks, note/geometry rejection, colour thresholds, the fixed polygon, window endpoints and lossless mask behavior. The DCT test is skipped only when `jpegtran` is unavailable. Version 1.0.0 remains an unchanged prior release.
