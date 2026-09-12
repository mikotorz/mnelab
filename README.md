# MNELAB

![](https://raw.githubusercontent.com/cbrnr/mnelab/main/mnelab/images/mnelab_logo.png)

MNELAB is a graphical user interface for [MNE-Python](https://mne.tools/stable/index.html), the most popular Python package for EEG/MEG analysis.


## 🤖 AI Notice

Most of the changes on top of upstream in this fork are written with AI coding assistance (Claude Code). Review any code here before relying on it, and treat fork-specific features as unaudited until you've checked them yourself.


## Fork Notice

This is [mikotorz](https://github.com/mikotorz)'s **personal, unofficial fork** of the official [MNELAB project](https://github.com/cbrnr/mnelab). It is not affiliated with, endorsed by, or supported by the MNELAB maintainers.

- **Personal use.** Maintained for personal experimentation on a best-effort basis — no guarantees of correctness, stability, or support.
- **Use at your own risk.** Back up your data, and independently verify any results before relying on them for real research, clinical, or production use.
- If you need the officially maintained version, use [cbrnr/mnelab](https://github.com/cbrnr/mnelab) instead.
- `main` is a pure mirror of upstream; all fork-specific development happens on `M-dev`.


## What's Added/Changed in This Fork

Compared to upstream, this fork adds:

- **Save/Open Project** — save the entire session (every open dataset, its montage/events/ICA, and the command history) to a single file, with autosave and crash recovery.
- **Pipeline** — chain multiple preprocessing steps (montage, bad channels, rename, filter, resample, crop, events from annotations, ICA) into a single run.
- **Crop Data: From Event Range** — crop to the first/last occurrence of selected events, with adjustable padding.

...plus fixes to the above. Full details, including individual PRs, are in [CHANGELOG.fork.md](CHANGELOG.fork.md).


## Running This Fork

Fork-specific features only exist in this source tree — they aren't published as a package or installer, so `uvx mnelab` or the standalone installers below will get you upstream MNELAB, not this fork. To run this fork instead:

```bash
git clone https://github.com/mikotorz/mnelab.git
cd mnelab
uv sync --all-groups --all-extras
uv run mnelab
```


## Everything Else

This README covers only what's specific to this fork. For the full feature list, installation options (standalone installers, AUR, `uvx`), documentation, contributing guide, and citation info, see the upstream project:

**➡️ [cbrnr/mnelab](https://github.com/cbrnr/mnelab)**
