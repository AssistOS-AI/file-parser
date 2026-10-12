# Source snapshot retention

The selected old snapshots were compacted on 2026-10-11 at the user's request. All logs, test results, manifests, receipts, configurations, scripts and historical hashes stay in their original directories. Only the exact paths listed in manifest.json are eligible for removal.

The archives retain exact source file bytes, modes, symlinks and empty directories, and original candidate TAR payload bytes. Each unique tree was extracted in an isolated temporary directory and compared with its per-file manifest before removal. Git HEAD, tree, raw commit object and refs are recorded; obsolete clone metadata and Git history are not archived. Canonical repositories are unchanged. File timestamps are in the first archived copy, but are not part of tree deduplication; extended filesystem attributes are not retained.

## Restore a source tree

Find its entry in manifest.json. Verify the archive SHA256 against the artifacts list. Create an empty directory at the entry's original workspace-relative path, then run /usr/bin/tar -xzpf ARCHIVE -C EMPTY_DIRECTORY. This restores source data without Git metadata. To obtain a Git checkout, separately clone the canonical repository and check out the recorded HEAD, then compare the source tree.

## Restore a candidate TAR

Find its payload.gz mapping. Run gzip -dc ARCHIVE > ORIGINAL_TAR_PATH using an absent output path. Verify SHA256 and size against originalSha256 and originalBytes. Its bytes match the historical manifest pins exactly; recorded hashes have not been rewritten.

The old files contain historical absolute paths, including links to retired /private/tmp scratch. Source restoration preserves those links as recorded. Before executing a restored copy, repair dependency links only in that separate restored copy and repeat applicable runtime checks. Old authorization artifacts are historical evidence, not renewed authorization to deploy or run tests.

The local container-image-builds/sources/ploinky build input must be restored or checked out at the selected build SHA before a local image build. GitHub workflows perform their own source checkout.

manifest.json maps every removed original path to its recovery archive; deletion-receipt.json records actual removals and observed allocated-space reduction.
