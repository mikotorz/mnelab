# Fork Changelog

This file tracks changes specific to the
[mikotorz/mnelab](https://github.com/mikotorz/mnelab) fork that are **not** part of the
upstream [cbrnr/mnelab](https://github.com/cbrnr/mnelab) project.

`CHANGELOG.md` mirrors upstream and should only change when pulling in upstream updates,
so it stays conflict-free to merge. Record all fork-only work here instead, following the
same format and style as `CHANGELOG.md`, but with PR links pointing to this fork
(`mikotorz/mnelab`).

## [UNRELEASED]
### ✨ Added
- Add a Pipeline action to chain multiple preprocessing steps (Apply Montage, Mark Bad Channels, Filter, Resample, Crop, Events from Annotations, Run ICA) into a single run ([#2](https://github.com/mikotorz/mnelab/pull/2) by [mikotorz](https://github.com/mikotorz))
- Add Rename Channels as a Pipeline step ([#3](https://github.com/mikotorz/mnelab/pull/3) by [mikotorz](https://github.com/mikotorz))
