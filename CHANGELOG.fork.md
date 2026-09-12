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
- Add Save/Open Project (a single Zstandard-compressed `.mnelabproj` file capturing every open dataset, montage, events, ICA, and the session's command history), with an unsaved-changes prompt on quit and periodic autosave with crash recovery on next launch ([#8](https://github.com/mikotorz/mnelab/pull/8) by [mikotorz](https://github.com/mikotorz))
- Add a Pipeline action to chain multiple preprocessing steps (Apply Montage, Mark Bad Channels, Filter, Resample, Crop, Events from Annotations, Run ICA) into a single run ([#2](https://github.com/mikotorz/mnelab/pull/2) by [mikotorz](https://github.com/mikotorz))
- Add Rename Channels as a Pipeline step ([#3](https://github.com/mikotorz/mnelab/pull/3) by [mikotorz](https://github.com/mikotorz))
- Add a "From Event Range" mode to Crop Data that crops to the first/last occurrence of a selected event type (or all events), with adjustable padding before/after ([#7](https://github.com/mikotorz/mnelab/pull/7) by [mikotorz](https://github.com/mikotorz))
- Add Interpolate Bad Channels, Change Reference, Remove Line Noise, Create Epochs, and Drop Bad Epochs as Pipeline steps, so a raw-to-epochs preprocessing pipeline can be built and run end to end ([#9](https://github.com/mikotorz/mnelab/pull/9) by [mikotorz](https://github.com/mikotorz))
- Add multi-stage support to the Pipeline dialog (a tabbed "+ Add Stage" UI), so steps that only make sense after an earlier transition, such as Drop Bad Epochs after Create Epochs, are offered once that transition is queued ([#11](https://github.com/mikotorz/mnelab/pull/11) by [mikotorz](https://github.com/mikotorz))
- Add Save/Load Preset to the Pipeline dialog, so a configured multi-stage pipeline can be saved to a `.json` file and reused on future datasets, with unsupported or no-longer-applicable steps skipped and reported instead of failing the whole load ([#12](https://github.com/mikotorz/mnelab/pull/12) by [mikotorz](https://github.com/mikotorz))
- Add an optional Decimate setting to Run ICA (and the Pipeline's Run ICA step) that fits on only every Nth sample, cutting calculation time at the cost of using less data; unchecked by default ([#13](https://github.com/mikotorz/mnelab/pull/13) by [mikotorz](https://github.com/mikotorz))
- Recolor the dev-build notice to purple with fork attribution, add the fork's own repository link to the About dialog, and introduce a fork build counter (`__fork_version__`) shown there ([#14](https://github.com/mikotorz/mnelab/pull/14) by [mikotorz](https://github.com/mikotorz))

### 🔧 Fixed
- Fix Run ICA's "Number of Components" defaulting to the total channel count instead of the count of good (non-bad) data channels actually used to fit, which raised `ica.n_components (N) cannot be greater than len(picks) (M)` whenever any channels were marked bad ([#13](https://github.com/mikotorz/mnelab/pull/13) by [mikotorz](https://github.com/mikotorz))
- Fix Run ICA and Plot ERDS maps hanging indefinitely on the "Calculating..." dialog with no CPU/RAM activity when the background calculation raised an exception, instead of surfacing the error ([#13](https://github.com/mikotorz/mnelab/pull/13) by [mikotorz](https://github.com/mikotorz))
- Fix Pipeline steps (Apply Montage, Mark Bad Channels, Rename Channels, Run ICA) validating and configuring against the original dataset instead of the state produced by earlier queued steps, which broke natural step orders like Rename Channels → Apply Montage or Filter Data → Run ICA ([#5](https://github.com/mikotorz/mnelab/pull/5) by [mikotorz](https://github.com/mikotorz))
- Allow removing characters from both the beginning and end of channel names in a single Rename Channels action instead of requiring it to be run twice ([#6](https://github.com/mikotorz/mnelab/pull/6) by [mikotorz](https://github.com/mikotorz))
- Allow combining frequency (lowpass/highpass/bandpass) and notch filtering into a single Filter Data action instead of requiring it to be run twice ([#6](https://github.com/mikotorz/mnelab/pull/6) by [mikotorz](https://github.com/mikotorz))
