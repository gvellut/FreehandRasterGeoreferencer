#!/usr/bin/env bash

set -euo pipefail

last_release_delete() {
  local repo_dir
  local repository
  local release_tag
  local confirmation

  repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  cd -- "$repo_dir"

  repository="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"

  # Select the newest release by creation date, including drafts and prereleases.
  release_tag="$(gh release list --repo "$repository" --order desc --limit 1 \
    --json tagName --jq '.[0].tagName // empty')"
  if [ -z "$release_tag" ]; then
    echo "No releases found for $repository. Nothing to delete."
    return 0
  fi

  # Show the exact release, date, and age directly, without opening a pager.
  printf 'Repository: %s\n' "$repository"
  GH_PAGER=cat gh release view --repo "$repository" \
    --json tagName,createdAt,publishedAt,isDraft,url \
    --template 'Release: {{.tagName}}
Created: {{timefmt "2006-01-02 15:04:05 MST" .createdAt}} ({{timeago .createdAt}})
{{if .publishedAt}}Published: {{timefmt "2006-01-02 15:04:05 MST" .publishedAt}} ({{timeago .publishedAt}})
{{end}}{{if .isDraft}}Status: draft
{{end}}{{.url}}
' -- "$release_tag"

  printf '\nThis deletes the GitHub release, its assets, and its remote and local tags.\n'
  # Require an explicit yes; empty input or EOF cancels deletion.
  read -r -p "Delete release '$release_tag' and its tags? [y/N] " confirmation || confirmation=""
  case "$confirmation" in
    [yY]|[yY][eE][sS])
      ;;
    *)
      echo "Cancelled."
      return 0
      ;;
  esac

  # Delete the remote release and tag only after the explicit confirmation above.
  gh release delete --repo "$repository" --cleanup-tag --yes -- "$release_tag"

  # The deploy wrapper also checks local tags, so remove the matching local tag.
  if git show-ref --verify --quiet "refs/tags/$release_tag"; then
    git tag --delete -- "$release_tag"
  fi

  echo "Deleted GitHub release and tag '$release_tag'."
  echo "To retry, commit and push any release fixes to master, then run ./deploy.sh."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  last_release_delete "$@"
fi
