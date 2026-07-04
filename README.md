# drupal-release-notes

Generate release notes and contributor reports for Drupal contrib projects from Drupal.org contribution records and GitLab issue metadata.

Each project has its own directory (cache, output, summaries, config). The default project is [ai_context](https://www.drupal.org/project/ai_context) (Context Control Center).

Reports are grouped by release date ranges, with credited issues listed by category, contributor counts for people and organizations, and markdown output ready to paste into Drupal.org release notes.

## Requirements

- Python 3.10+
- `requests`

```bash
python3 -m pip install -r scripts/requirements.txt
```

### GitLab token (for credit audit comments)

Issue and merge request comments need a [git.drupalcode.org personal access token](https://git.drupalcode.org/-/user_settings/personal_access_tokens) with `read_api` scope.

Store it in your OS keychain (encrypted, not plaintext in the repo):

```bash
python3 scripts/credit_audit.py --store-gitlab-token
```

Your input is hidden. On macOS the token is stored in Keychain Access under service `issue-credit-report`. Remove it with `--clear-gitlab-token`.

## Quick start

```bash
# Generate all period reports for ai_context (uses cached API data when available)
python3 scripts/release_notes.py

# Output is written to ai_context/output/*.md
```

After cloning this repo, cached data under `{project}/cache/` is reused so you do not need to refetch everything from Drupal.org and GitLab.

Use `--project MACHINE_NAME` to target another project directory (see [Adding a project](#adding-a-project)).

## Adding a project

Create a directory named after the Drupal.org project machine name:

```bash
mkdir -p my_module/cache my_module/output my_module/summaries
```

Add `my_module/config.json`:

```json
{
  "machine_name": "my_module",
  "drupal_org_nid": 1234567
}
```

Find the project node ID (`drupal_org_nid`) on the project page URL, e.g. `https://www.drupal.org/project/my_module` → view source or API, or from `https://www.drupal.org/api-d7/node.json?type=project&field_project_machine_name=my_module`.

Optional per-project files:

- `my_module/exclude_from_lists.txt` — hide issues from release note bullet lists
- `my_module/ignore_uncredited_people.txt` — usernames not expected to receive credit

Then run with `--project my_module`:

```bash
python3 scripts/release_notes.py --project my_module
python3 scripts/credit_audit.py --project my_module
```

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
3. Writes `ai_context/output/beta2-to-beta3.md` and updates `ai_context/output/beta3-to-now.md`

No script changes are required for new releases — only publish the release on Drupal.org, then re-run the report.

Issues are assigned to a period based on `field_last_status_change` from the contribution record (when credit was finalized).

Completed periods are cached in `{project}/cache/periods/` and only recomputed with `--rebuild-frozen`. The current `{last}-to-now` period is regenerated on every run.

## Output format

Each `{project}/output/{period}.md` file includes:

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
python3 scripts/release_notes.py --refresh-records --refresh-issues

# Or only the current open period (slug changes to beta3-to-now after beta3 exists)
python3 scripts/release_notes.py --period beta3-to-now --refresh-records --refresh-issues

# Optional: regenerate AI summary prompt for the new period
python3 scripts/release_notes.py --period beta3-to-now --write-summary-prompts
```

### Full rebuild (rare)

```bash
python3 scripts/release_notes.py --refresh-records --refresh-issues --rebuild-frozen
```

### One period only

```bash
python3 scripts/release_notes.py --period alpha1-to-beta1
```

## Credit audit

Use `scripts/credit_audit.py` to find closed issues where credits may be incomplete:

- **No contribution record** — closed on GitLab, nothing on new.drupal.org yet
- **No credits granted** — record exists but nobody has “Credit this contributor” checked
- **Uncredited people** — listed on the record but not granted credit (often reviewers or people you decided not to credit)

Issues labeled `why::duplicate` or `why::wontFix` on GitLab are exempt (no record and/or no credits expected) and are excluded from `--review`.

Project managers who only add labels (not code) can be listed in `{project}/ignore_uncredited_people.txt`. If they are the **only** uncredited people on an issue, it is omitted from `--review`.

```bash
# Generate ai_context/output/credit-audit.md (uses cache after first run)
python3 scripts/credit_audit.py

# Step through each issue interactively
python3 scripts/credit_audit.py --review

# Refresh from Drupal.org and GitLab
python3 scripts/credit_audit.py --refresh

# Refresh one issue after editing credits on Drupal.org
python3 scripts/credit_audit.py --refresh-issue 3579841

# Re-fetch GitLab comments for uncredited people
python3 scripts/credit_audit.py --refresh-comments
```

For each uncredited person on a pending issue, the audit loads their GitLab **issue** comments and **merge request** comments (when a linked MR is found). Results are cached in `{project}/cache/issue_activity.json`.

Interactive prompts:

- **y** — Approve (OK as-is; won't show again)
- **n** — Deny / skip (still needs review next run)
- **p** — Approve only some uncredited people (when several are listed)
- **q** — Quit (progress saved)

After reviewing an issue manually, you can also approve from the command line:

```bash
# Whole issue reviewed
python3 scripts/credit_audit.py --approve 3586230

# Only one uncredited person is intentional
python3 scripts/credit_audit.py --approve 3545824:catia_penas

# Undo
python3 scripts/credit_audit.py --unapprove 3586230

# List saved approvals
python3 scripts/credit_audit.py --list-approvals
```

Approvals are stored in `{project}/cache/credit_approvals.json`.

## AI-written summary paragraph

By default, a factual summary is generated from section counts. For prose suitable for Drupal.org:

1. Generate prompt files:

   ```bash
   python3 scripts/release_notes.py --write-summary-prompts
   ```

2. Paste `{project}/summaries/{period}.prompt.md` into Cursor or another AI and ask for 1–2 paragraphs.

3. Save the result as `{project}/summaries/{period}.txt` (or `.md`).

4. Re-run the report — the custom summary replaces the auto-generated one.

Empty sections are omitted from prompt files.

## Manual fine-tuning

### Hide specific issues from lists

Add issue numbers to `{project}/exclude_from_lists.txt` (one per line, `#` for comments).

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
--project NAME           Drupal project machine name (default: ai_context)
--period SLUG            Period slug or 'all' (default). Slugs are derived from releases.
--refresh-records        Re-fetch contribution records from new.drupal.org
--refresh-issues         Re-fetch GitLab issue metadata
--rebuild-frozen         Recompute frozen period reports
--exclude-list PATH      Alternate exclusion list (default: {project}/exclude_from_lists.txt)
--write-summary-prompts  Write {project}/summaries/{period}.prompt.md for AI-assisted summaries
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
scripts/
  project.py              Per-project config and path helpers
  release_notes.py        Release credit reports
  credit_audit.py         Missing/partial credit audit + approvals
  gitlab_activity.py      GitLab comment lookup for credit audit
  requirements.txt        Python dependencies (requests, keyring)

ai_context/               Example project (Context Control Center)
  config.json             machine_name + drupal.org project node ID
  exclude_from_lists.txt  Manual issue exclusions
  ignore_uncredited_people.txt  PM usernames not expected to receive credit
  cache/
    contribution_records.json Cached credited issues + contributor org attributions
    credit_audit_records.json Full contributor lists for audit (credited + uncredited)
    credit_approvals.json     Issues and people you have reviewed
    issue_activity.json       Cached GitLab issue/MR comments for audit
    closed_issues.json        Closed GitLab issues for audit comparison
    issues.json               Cached GitLab issue metadata
    periods/                  Frozen period report JSON
  output/                   Generated markdown release notes
    credit-audit.md           Credit review report
  summaries/
    {period}.prompt.md        AI prompt input (optional to regenerate)
    {period}.txt              Custom summary paragraph (optional)
```

Add more projects as sibling directories (`my_module/`, etc.) with the same structure.

## Notes

- Only issues with at least one granted credit (`field_credit_this_contributor`) are included in release reports.
- GitLab issues and Drupal.org credits are separate systems linked by issue URL.
- Be respectful of API rate limits. This tool caches aggressively and fetches GitLab issues in paginated batches rather than one request per issue.
