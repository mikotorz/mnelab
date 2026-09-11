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

### 🔧 Fixed
- Fix Pipeline steps (Apply Montage, Mark Bad Channels, Rename Channels, Run ICA) validating and configuring against the original dataset instead of the state produced by earlier queued steps, which broke natural step orders like Rename Channels → Apply Montage or Filter Data → Run ICA ([#5](https://github.com/mikotorz/mnelab/pull/5) by [mikotorz](https://github.com/mikotorz))
- Allow removing characters from both the beginning and end of channel names in a single Rename Channels action instead of requiring it to be run twice ([#6](https://github.com/mikotorz/mnelab/pull/6) by [mikotorz](https://github.com/mikotorz))
- Allow combining frequency (lowpass/highpass/bandpass) and notch filtering into a single Filter Data action instead of requiring it to be run twice ([#6](https://github.com/mikotorz/mnelab/pull/6) by [mikotorz](https://github.com/mikotorz))
