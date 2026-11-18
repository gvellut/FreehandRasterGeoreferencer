#!/usr/bin/env bash

set -euo pipefail

deploy() {
  local repo_dir
  local version
  local version_tag
  local current_branch
  local workflow_watcher
  local skip_watch=false

  # Allow deployment on machines without the local workflow watcher.
  if [ "${1:-}" = "--nowatch" ]; then
    skip_watch=true
    shift
  fi

  repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  cd -- "$repo_dir"

  version="$(uv version --short)"
  version_tag="v${version}"
  workflow_watcher="$HOME/bin/_deploy/watch_workflow.sh"

  if [ "$skip_watch" = false ] && [ ! -x "$workflow_watcher" ]; then
    echo "Error: Workflow watcher is not executable: $workflow_watcher" >&2
    return 1
  fi

  # Require a clean working tree before tagging a release.
  if [ -n "$(git status --porcelain)" ]; then
    echo "Error: The working tree contains uncommitted or untracked files." >&2
    echo "Sync the version with 'uv run task sync-version', review and commit the release files, then push master. See the Deploy steps in README.md." >&2
    return 1
  fi

  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$current_branch" != "master" ]; then
    echo "Error: Deployments must be tagged from master. Current branch: $current_branch" >&2
    echo "Merge the release changes into master before running ./deploy.sh again." >&2
    return 1
  fi

  git fetch origin master:refs/remotes/origin/master --tags

  if [ "$(git rev-parse master)" != "$(git rev-parse origin/master)" ]; then
    echo "Error: Local and remote master are not the same." >&2
    echo "Push pending release commits or update local master so both point to the release commit, then retry ./deploy.sh." >&2
    return 1
  fi

  # A version can only be released once; existing tags must not be moved.
  if git show-ref --verify --quiet "refs/tags/$version_tag"; then
    echo "Error: Tag '$version_tag' already exists." >&2
    echo "Set a new version in pyproject.toml, update the changelog, run 'uv run task sync-version', then commit and push master before deploying." >&2
    return 1
  fi

  git tag -a "$version_tag" -m "Release $version_tag"
  git push origin "refs/tags/$version_tag"
  echo "Tag '$version_tag' pushed" >&2

  # Reuse the generic watcher, forwarding its optional polling arguments.
  if [ "$skip_watch" = false ]; then
    "$workflow_watcher" "$version_tag" "$@"
  fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  deploy "$@"
fi
