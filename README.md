# drupal-release-notes

Generate release notes and contributor reports for [ai_context](https://www.drupal.org/project/ai_context) (Context Control Center) from Drupal.org contribution records and GitLab issue metadata.

Reports are grouped by release date ranges, with credited issues listed by category, contributor counts for people and organizations, and markdown output ready to paste into Drupal.org release notes.

## Requirements

- Python 3.10+
- `requests`

```bash
python3 -m pip install -r requirements.txt
```

Optional: set `GITLAB_TOKEN` or `GITLAB_PRIVATE_TOKEN` for higher GitLab API rate limits.

## Quick start

```bash
# Generate all period reports (uses cached API data when available)
python3 report.py

# Output is written to output/*.md
```

After cloning this repo, cached data under `cache/` is reused so you do not need to refetch everything from Drupal.org and GitLab.

## Report periods

Period boundaries are loaded automatically from tagged releases on [drupal.org/project/ai_context/releases](https://www.drupal.org/project/ai_context/releases) via the Drupal.org API. Dev branches such as `1.0.x-dev` are ignored; only static tagged releases are used.

Each run prints the release versions found, for example:

```
Release boundaries from Drupal.org: 0.1.0-alpha1, 1.0.0-beta1, 1.0.0-beta2
```

For each consecutive pair of releases, the script creates a report period. The most recent release always gets an open-ended `{last}-to-now` period. Today that looks like:

| Slug | Period |
|------|--------|
| `pre-alpha1` | Inception → 0.1.0-alpha1 |
| `alpha1-to-beta1` | 0.1.0-alpha1 → 1.0.0-beta1 |
| `beta1-to-beta2` | 1.0.0-beta1 → 1.0.0-beta2 |
| `beta2-to-now` | 1.0.0-beta2 → now (incremental) |

When a new release is published (e.g. `1.0.0-beta3`), the next run automatically:

1. Adds a frozen `beta2-to-beta3` period (credits finalized between those release dates)
2. Opens a new current period `beta3-to-now`
3. Writes `output/beta2-to-beta3.md` and updates `output/beta3-to-now.md`

No script changes are required for new releases — only publish the release on Drupal.org, then re-run the report.

Issues are assigned to a period based on `field_last_status_change` from the contribution record (when credit was finalized).

Completed periods are cached in `cache/periods/` and only recomputed with `--rebuild-frozen`. The current `{last}-to-now` period is regenerated on every run.

## Output format

Each `output/{period}.md` file includes:

1. **Credited issue total** at the top
2. **Summary paragraph** (custom or auto-generated from counts)
3. **New Features** — `category::feature`
4. **Bug Fixes** — `category::bug`
5. **Other Major Contributions** — major/critical plan, task, support, or discuss issues
6. **Additional Contributions** — counts for Plan, Task, Support, Discuss (issues listed above are excluded from these counts)
7. **Contributors** — people and organizations with credit counts

People are sorted by credit count, then by their highest organization count on ties. Each organization gets at most one credit per issue.

Section totals are designed to match organization counts for Salsa Digital / Itty Bitty Byte when all credited work uses those org attributions.

## Common workflows

### Preparing a new release (e.g. beta3)

After the release is published on Drupal.org:

```bash
# Refresh credits and issue labels; script picks up the new release automatically
python3 report.py --refresh-records --refresh-issues

# Or only the current open period (slug changes to beta3-to-now after beta3 exists)
python3 report.py --period beta3-to-now --refresh-records --refresh-issues

# Optional: regenerate AI summary prompt for the new period
python3 report.py --period beta3-to-now --write-summary-prompts
```

### Full rebuild (rare)

```bash
python3 report.py --refresh-records --refresh-issues --rebuild-frozen
```

### One period only

```bash
python3 report.py --period alpha1-to-beta1
```

## AI-written summary paragraph

By default, a factual summary is generated from section counts. For prose suitable for Drupal.org:

1. Generate prompt files:

   ```bash
   python3 report.py --write-summary-prompts
   ```

2. Paste `summaries/{period}.prompt.md` into Cursor or another AI and ask for 1–2 paragraphs.

3. Save the result as `summaries/{period}.txt` (or `.md`).

4. Re-run the report — the custom summary replaces the auto-generated one.

Empty sections are omitted from prompt files.

## Manual fine-tuning

### Hide specific issues from lists

Add issue numbers to `exclude_from_lists.txt` (one per line, `#` for comments).

Hidden issues:

- Are removed from New Features, Bug Fixes, and Other Major bullet lists
- Stay in Additional Contributions category totals and contributor counts
- Remain in the major bucket for accounting (not double-counted as Task)

### Automatic exclusions

These are omitted from **Other Major Contributions** lists but still counted in **Additional Contributions**:

| Pattern | Examples |
|---------|----------|
| Sprint planning | `Sprint 3 CCC roadmap updates, sprint planning, and issue triage` |
| Sessions / meetings | `CCC Chicago session slides`, `CCC UX sync 27 May 2026` |
| Release creation | `Create CCC beta2 release` |
| QA tasks | `CCC beta1 QA` |

## Command-line options

```
--period SLUG             Period slug or 'all' (default). Slugs are derived from releases.
--refresh-records        Re-fetch contribution records from new.drupal.org
--refresh-issues         Re-fetch GitLab issue metadata
--rebuild-frozen         Recompute frozen period reports
--exclude-list PATH      Alternate exclusion list file (default: exclude_from_lists.txt)
--write-summary-prompts  Write summaries/{period}.prompt.md for AI-assisted summaries
```

## Data sources

| Data | Source |
|------|--------|
| Issue credits (people, orgs) | [new.drupal.org](https://new.drupal.org) JSON:API — `contribution_record` nodes |
| Issue category, priority, title | [git.drupalcode.org](https://git.drupalcode.org/project/ai_context) GitLab API (paginated, ~5 requests) |
| Release date boundaries | [drupal.org/project/ai_context/releases](https://www.drupal.org/project/ai_context/releases) via `api-d7` `project_release` nodes |

Per-issue credit lookup (for debugging):

```
https://new.drupal.org/contribution-record?source_link=ISSUE_URL&format=jsonapi
```

## Repository layout

```
report.py                 Main script
requirements.txt
exclude_from_lists.txt    Manual issue exclusions
cache/
  contribution_records.json Cached credited issues + contributor org attributions
  issues.json               Cached GitLab issue metadata
  periods/                  Frozen period report JSON
output/                   Generated markdown release notes
summaries/
  {period}.prompt.md        AI prompt input (optional to regenerate)
  {period}.txt              Custom summary paragraph (optional)
```

## Notes

- Only issues with at least one granted credit (`field_credit_this_contributor`) are included.
- ai_context issues live on GitLab; credits live on new.drupal.org (separate systems linked by issue URL).
- Be respectful of API rate limits. This tool caches aggressively and fetches GitLab issues in paginated batches rather than one request per issue.
