---
name: apk-acquisition
description: Download APK/XAPK packages for a target with `rea download` (the bundled `apkd` Go downloader). Use when you need to obtain an app's package before decompiling or analysing it, choose a download source, or handle split/XAPK bundles. First step of the static pipeline.
---

# APK acquisition with `rea download`

Fetches the target package into `workspaces/<package>/apks/` using the bundled `apkd` downloader.

## Commands

```bash
rea download <package>                    # e.g. rea download com.target.app
rea download -l <play-store-or-direct-url>
rea download <package> -s <source>        # apkpure | rustore | nashstore
rea download --targets config/targets.txt # batch
```

- Defaults to a sensible provider; pass `-s` when a package lives on a specific store (RuStore,
  NashStore) or the default source 404s. A failed pinned source retries with all sources, and apkd falls back across sources on download errors.
- Split APKs / XAPK bundles come down as a set under `apks/`; `rea decode` merges them.

## When to use

- Before `rea decode` (bytecode) or `rea native` (`.so`) on a target you do not yet have locally.
- To grab a specific version or a store-specific build.

## Notes

- Downloading distributes nothing and touches no device — it is purely acquisition.
- If a download fails, check the source (`-s`), then whether the package name/URL is correct
  (`rea target list`).
- Prefer `rea pipeline <package>` when you want acquire → decode → native in one shot.

Full reference: `docs/downloading_targets.md`. See also `apkdgo-help.txt`.
