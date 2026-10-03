# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added `task.depends_on()` and topological sort
- Added `task.is_stale()` based on mtimes of task dependencies

### Changed

- Switched from poetry to uv, build backend is now `uv_build`. Install with
  `uv sync`, run with `uv run`.

### Removed

- Dropped the `graphlib` dependency and moved `pytest-cov` out of the runtime
  dependencies into the dev group.

<!-- ## [1.1.0] - 2021-08-24 -->
