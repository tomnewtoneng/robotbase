# Publishing Robotbase

The steps to get `pip install robotbase` working for a stranger and to publish the shared
runtime image. These need the owner's accounts/tokens, so they're documented rather than
automated.

## 1. PyPI package

The package is build-ready (`pyproject.toml`; templates ship as package data). Verify and
publish from a clean checkout with the venv active:

```bash
pip install build twine
rm -rf dist && python -m build            # builds sdist + wheel into dist/
twine check dist/*                        # metadata/readme sanity check

# One-time: create a PyPI account + an API token (https://pypi.org/manage/account/token/)
# Recommended: test on TestPyPI first
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ robotbase   # smoke test in a fresh venv

# Then the real thing
twine upload dist/*                        # prompts for the token (user __token__)
```

Bump `version` in `pyproject.toml` for each release (semver); tag the commit
(`git tag v0.1.0 && git push --tags`). The wheel bundles all three templates and the sim
adapters — confirm with `python -c "import zipfile,glob; print(len([n for n in
zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist() if '/templates/' in n]))"` (should be
> 0).

Optional extras: `pip install robotbase[sim-mujoco]` for the MuJoCo backend.

## 2. The shared runtime Docker image

Generated projects build `robotbase-runtime:latest` locally on first `robotbase up` (~3.6 GB,
a few minutes). Publishing a prebuilt image lets users **pull** instead of build.

```bash
# Build from any template's Dockerfile (they're identical)
docker build -t <registry>/robotbase-runtime:<tag> \
  robotbase/templates/differential-drive
docker tag <registry>/robotbase-runtime:<tag> <registry>/robotbase-runtime:latest

# One-time: log in to a public registry (Docker Hub or GHCR)
docker login                               # or: echo $TOKEN | docker login ghcr.io -u <user> --password-stdin
docker push <registry>/robotbase-runtime:<tag>
docker push <registry>/robotbase-runtime:latest
```

Then point the templates' `compose.yaml` `image:` at `<registry>/robotbase-runtime` (keep a
local `build:` fallback) so a fresh `robotbase up` pulls the published image. Rebuild/push
whenever the Dockerfile changes (e.g. a new apt layer).

## 3. Release checklist

- `pytest` green; `robotbase create` + `robotbase up` + `robotbase test` work from a fresh
  clone.
- `version` bumped; `ROADMAP.md`/`README.md` status current.
- `python -m build` + `twine check` clean.
- Tag pushed; PyPI upload done; runtime image pushed.
- (Human) record/refresh the demo GIF for the README.
