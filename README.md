# issue credit report

Tools for Drupal contrib release preparation: release notes, contributor credit audits, and pre-release status checks.

Each project has its own directory (`{project}/cache/`, `{project}/reports/`, etc.). The default project is [ai_context](https://www.drupal.org/project/ai_context) (Context Control Center), configured for **GitLab milestone**–based releases.

| Script | Purpose |
|--------|---------|
| `scripts/release_notes.py` | Release credit reports per milestone or release period |
| `scripts/credit_audit.py` | Find missing or incomplete credits; track reviewed issues |
| `scripts/release_prep.py` | Pre-release checklist for a GitLab milestone |
| `scripts/combined_milestone_report.py` | Merge multiple milestone reports; compare to Drupal.org |

## AI usage

This repo code has been vibe coded with Cursor Composer 2.5.
Your mileage may vary. PRs are welcome.

## Requirements

- Python 3.10+
- `requests` and `keyring` (see `scripts/requirements.txt`)

```bash
python3 -m pip install -r scripts/requirements.txt
```

All scripts accept `--project MACHINE_NAME` (default: `ai_context`).

### GitLab token (for credit audit comments)

Issue and merge request comments need a [git.drupalcode.org personal access token](https://git.drupalcode.org/-/user_settings/personal_access_tokens) with **`read_api`** scope. **Guest** role is enough for public issue/MR comments; use **Reporter** only if you hit permission errors.

Store the token in your OS keychain (encrypted, not plaintext in the repo):

```bash
python3 scripts/credit_audit.py --store-gitlab-token
```

Your input is hidden. On macOS the token is stored in Keychain Access under service `issue-credit-report`. Remove it with `--clear-gitlab-token`.

## Quick start

```bash
# Pre-release status for a GitLab milestone
python3 scripts/release_prep.py --milestone "1.0.0-beta3"

# Generate release notes (uses cached API data when available)
python3 scripts/release_notes.py

# Credit audit report
python3 scripts/credit_audit.py
```

Generated reports:

- `ai_context/reports/release-notes-{milestone}.html` — release notes (HTML for Drupal.org paste)
- `ai_context/reports/credit-audit.html` — credit review report
- `ai_context/reports/contributors-all-releases.html` — running totals of all credited people and organizations
- `ai_context/reports/release-status-{milestone}.txt` — release prep checklist (written by `release_prep.py` and `--refresh-all`)
- `ai_context/summaries/{milestone}.prompt.md` — AI summary input (regenerated with release notes)

Cached data under `{project}/cache/` is reused so you do not need to refetch everything from Drupal.org and GitLab on every run.

**Refresh everything** (contribution records, GitLab issues, profile aliases, all milestone caches, all reports, credit audit, release prep for the current milestone):

```bash
python3 scripts/release_notes.py --refresh-all
```

Also regenerates `milestone-assignments.html` and `milestone-closed-on-future.html` on every release notes run.

## How releases are scoped

Behavior is controlled by `period_source` in `{project}/config.json`.

### Milestones mode (`period_source: "milestones"`) — ai_context default

One report per matching GitLab milestone. **Filenames and `--period` use the milestone title**, e.g. `reports/release-notes-1.0.0-beta2.html` for milestone `1.0.0-beta2`.

- **Release notes** include credited issues **assigned to that milestone** on GitLab.
- **Release prep** scopes issues assigned to the milestone or closed within its date window.
- Milestone **start/due dates** (plus `milestone_close_grace_hours`, default 24h after due date) define the window. Adjust dates on GitLab to finetune scope.
- A new GitLab milestone is picked up on the next run — no manual slug mapping.

`ai_context/config.json`:

```json
{
  "machine_name": "ai_context",
  "drupal_org_nid": 3546505,
  "period_source": "milestones",
  "milestone_exclude_titles": ["Future"],
  "milestone_close_grace_hours": 24
}
```

Optional milestone filters:

```json
{
  "milestone_exclude_titles": ["Future", "Enablement"],
  "milestone_include_pattern": "^\\d+\\.\\d+\\.\\d+(-(alpha|beta|rc)\\d*)?$"
}
```

### Releases mode (`period_source: "releases"`)

For projects without GitLab milestone dates. Period boundaries come from Drupal.org release tags; issues are placed by GitLab close date within each tag window. Report files use release-derived keys, e.g. `reports/release-notes-beta2-to-now.html`. Pass `--period beta2-to-now` (or `all`).

## Common workflows

### Preparing a new release (e.g. beta4)

```bash
# 1. Check milestone progress, credits, QA issue, release notes
python3 scripts/release_prep.py --milestone "1.0.0-beta4"

# 2. Review and resolve credit issues interactively
python3 scripts/credit_audit.py --review

# 3. Refresh release notes for the current milestone
python3 scripts/release_notes.py --period "1.0.0-beta4" --refresh-records --refresh-issues
```

After publishing on Drupal.org:

```bash
python3 scripts/release_notes.py --refresh-records --refresh-issues
```

### Full refresh (re-fetch all API data and rebuild all reports)

```bash
python3 scripts/release_notes.py --refresh-all
```

This also runs `release_prep.py` for the current GitLab milestone (console status summary, `release-status-{milestone}.txt`, and `milestone-closed-on-future.html`).

This re-fetches contribution records, GitLab issue metadata, and Drupal.org profile URL aliases; rebuilds all frozen milestone caches; regenerates every release-notes HTML file and summary prompt; then refreshes the credit audit cache, GitLab comments, and `credit-audit.html`.

To refresh only one milestone's HTML output (shared caches still update when combined with refresh flags):

```bash
python3 scripts/release_notes.py --period "1.0.0-beta4" --refresh-all
```

### Backfill missing milestones

If GitLab milestones were not created for early releases:

```bash
python3 scripts/release_prep.py --list-by-milestone --write-output
python3 scripts/release_prep.py --list-by-milestone --milestone "1.0.0-beta1"
```

Writes `{project}/reports/milestone-assignments.html` with `--write-output`, or automatically when generating release notes.

### Combined milestone reports

To merge several milestones into one release-notes file (e.g. for a Drupal.org release spanning multiple milestones):

```bash
python3 scripts/combined_milestone_report.py \
  --milestones "1.0.0-alpha" "1.0.0-beta1" \
  --slug "alpha-through-beta1" \
  --title "1.0.0-alpha through 1.0.0-beta1" \
  --drupal-release "1.0.0-beta1"
```

Writes `release-notes-{slug}.html` and `compare-drupalorg-{slug}.html`. Requires frozen period caches for each milestone (`--rebuild-frozen` or `--refresh-all` first).

## Release status (`release_prep.py`)

```bash
python3 scripts/release_prep.py --milestone "1.0.0-beta3"
```

Writes `{project}/reports/release-status-{milestone}.txt` with the same checklist shown on the console.

| Line | Meaning |
|------|---------|
| **Open in milestone** | Open issues still in the milestone |
| **Credit audit pending** | In-scope issues needing credit review |
| **QA issue** | Looks for `CCC {release} QA` (e.g. `CCC beta3 QA`) |
| **Release notes** | Path and credited count for this milestone |
| **Duplicate d.o records** | Multiple Drupal.org nodes for one issue |
| **Missing contribution records** | Closed in scope with no record on new.drupal.org |
| **No record expected** | `why::duplicate`, `why::wontFix`, or `why::worksAsDesigned` |
| **Wrong milestone** | Assigned milestone does not match close date / window |
| **Closed on future milestone** | Closed but assigned to a milestone after the current release (see below) |
| **Missing in milestone** | Assigned to milestone without a contribution record |

Example:

```
* Release notes: ai_context/reports/release-notes-1.0.0-beta3.html (83 credited) — milestone has 86
    3 closed in milestone not in release notes (duplicate / won't fix / works as designed):
    #3586286: … — won't fix (why::wontFix) — …
```

Run `python3 scripts/release_notes.py --refresh-all` (or `python3 scripts/credit_audit.py --refresh`) if cache counts look stale.

### Closed on future milestone

Release notes and beta3 prep only include issues **assigned to that milestone on GitLab**. A closed issue on `1.0.0-beta4` will not appear in beta3 data even if it closed during the beta3 window.

`release_prep.py` flags closed issues assigned to any milestone **after the current release** (next GitLab milestone after the latest Drupal.org tag). Reassign them on GitLab, then refresh:

```bash
python3 scripts/release_notes.py --refresh-all
```

Or run release prep alone for the current milestone:

```bash
python3 scripts/release_prep.py --milestone "1.0.0-beta3"
```

`milestone-closed-on-future.html` is also regenerated whenever release notes are generated.

## Release notes output

Each `{project}/reports/release-notes-{milestone}.html` file is HTML ready to paste into Drupal.org release notes. It includes:

1. **Changes since** — link to the previous Drupal.org release and a GitLab compare URL (when a prior tagged release exists)
2. **Milestone title** and **credited issue total**
3. **Summary paragraph** (custom or auto-generated)
4. **Contributors** — people and organizations with credit counts; names link to Drupal.org profile URLs (`/u/…`, `/org-slug`)
5. **New Features** — `category::feature`
6. **Bug Fixes** — `category::bug`
7. **Other Major Issues** — major/critical plan, task, or support (non-feature/non-bug)
8. **Additional Code Issues** — credited issues with a related merge request not listed above
9. **Additional Non-Code Contributions** — everything else, by category count (Plan, Task, Support)

Only issues with at least one granted credit on Drupal.org are included.

**Running contributor totals** — `{project}/reports/contributors-all-releases.html` aggregates people and organizations across all milestone reports (each issue counted once). Regenerated whenever release notes are generated. People and organizations linked to names in `scripts/ai-initiative-partners.md` are marked with `(*)`.

Completed milestones are cached in `{project}/cache/periods/{milestone}.json` and only recomputed with `--rebuild-frozen` (included in `--refresh-all`). The current milestone is regenerated on every run.

### AI-written summary paragraph

Each run writes `{project}/summaries/{milestone}.prompt.md` alongside the HTML report.

1. Paste `summaries/1.0.0-beta4.prompt.md` into an AI; ask for 1–2 paragraphs.
2. Save as `summaries/1.0.0-beta4.txt` (or `.md`).
3. Re-run the report — custom summary replaces the auto-generated one.

### Manual fine-tuning

**Hide issues from lists** — add IIDs to `{project}/exclude_from_lists.txt`. Hidden issues stay in contributor counts and additional section totals.

**Automatic exclusions from Other Major lists** — sprint planning, sessions/meetings, release-creation tasks, QA tasks (still counted in Additional Non-Code Contributions or Additional Code Issues when applicable).

**Merge request detection** — GitLab related-MR lookup is cached on each credited issue (`has_merge_request` in `{project}/cache/issues.json`). Issues labeled `what::code` count as code issues when MR metadata is not yet cached.

## Credit audit

Finds closed issues where credits may be incomplete:

- **No contribution record** — closed on GitLab, nothing on new.drupal.org
- **No credits granted** — record exists but nobody credited
- **Uncredited people** — on the record but not granted credit

Issues with `why::duplicate`, `why::wontFix`, or `why::worksAsDesigned` are exempt.

```bash
python3 scripts/credit_audit.py                    # write credit-audit.html
python3 scripts/credit_audit.py --review           # interactive review
python3 scripts/credit_audit.py --refresh          # refresh all caches
python3 scripts/credit_audit.py --refresh-issue 3579841
python3 scripts/credit_audit.py --approve 3586230
python3 scripts/credit_audit.py --approve 3545824:catia_penas
```

Project managers who only add labels can be listed in `{project}/ignore_uncredited_people.txt`.

Interactive prompts: **y** approve, **n** skip, **p** approve some people, **q** quit.

Approvals stored in `{project}/cache/credit_approvals.json`.

## Adding a project

```bash
mkdir -p my_module/cache my_module/reports my_module/summaries
```

`my_module/config.json`:

```json
{
  "machine_name": "my_module",
  "drupal_org_nid": 1234567,
  "period_source": "milestones",
  "milestone_close_grace_hours": 24
}
```

Find `drupal_org_nid` from the project page or `https://www.drupal.org/api-d7/node.json?type=project&field_project_machine_name=my_module`.

Optional files: `exclude_from_lists.txt`, `ignore_uncredited_people.txt`.

```bash
python3 scripts/release_prep.py --project my_module --milestone "1.0.0-beta1"
python3 scripts/release_notes.py --project my_module
python3 scripts/credit_audit.py --project my_module
```

## Command-line options

### `release_notes.py`

```
--project NAME           Project machine name (default: ai_context)
--period TITLE           Milestone title or 'all' (default: all)
--refresh-all            Full refresh: records, issues, aliases, all periods,
                         all reports, summary prompts, credit audit
--refresh-records        Re-fetch contribution records from new.drupal.org
--refresh-issues         Re-fetch GitLab issue metadata
--refresh-aliases        Re-fetch Drupal.org profile URL aliases (api-d7)
--rebuild-frozen         Recompute frozen milestone period caches
--exclude-list PATH      Alternate exclusion list
```

### `credit_audit.py`

```
--project NAME           Project machine name
--review                 Interactive review
--refresh                Re-fetch records and closed GitLab issues
--refresh-issue IID      Re-fetch one issue
--refresh-comments       Re-fetch GitLab comments for uncredited people
--approve TARGET         Approve issue (IID) or person (IID:username)
--unapprove TARGET       Remove approval
--list-approvals         Print saved approvals
--store-gitlab-token     Save GitLab token to OS keychain
--clear-gitlab-token     Remove token from keychain
```

### `combined_milestone_report.py`

```
--project NAME           Project machine name
--milestones TITLE ...   Milestone titles to merge (in order)
--slug SLUG              Filename slug (default: alpha-through-beta1)
--title TITLE            Report heading
--drupal-release VER     Drupal.org release label for comparison section
```

### `release_prep.py`

```
--project NAME           Project machine name
--milestone TITLE        GitLab milestone title (required for status report)
--list-by-milestone      List closed issues grouped by suggested milestone
--write-output           Write reports/milestone-assignments.html
```

## Data sources

| Data | Source |
|------|--------|
| Issue credits | [new.drupal.org](https://new.drupal.org) JSON:API — `contribution_record` nodes |
| Issue labels, close dates, milestones | [git.drupalcode.org](https://git.drupalcode.org/project/ai_context) GitLab API |
| Release tag dates | [drupal.org releases](https://www.drupal.org/project/ai_context/releases) (releases mode; compare links in milestones mode) |
| Profile URLs | [drupal.org api-d7](https://www.drupal.org/api-d7/user/{uid}.json) — canonical `/u/…` and org slug URLs |

Per-issue credit lookup:

```
https://new.drupal.org/contribution-record?source_link=ISSUE_URL&format=jsonapi
```

## Repository layout

```
scripts/
  project.py                  Per-project config and path helpers
  html_report.py              HTML helpers for Drupal.org-compatible output
  period_context.py           Milestone windows and period building
  release_prep.py             Pre-release milestone status
  release_notes.py            Release credit reports
  credit_audit.py             Credit audit + approvals
  combined_milestone_report.py  Merge milestones; Drupal.org comparison
  gitlab_activity.py          GitLab comment lookup

ai_context/
  config.json
  cache/
    periods/                  Frozen report JSON per milestone
    contribution_records.json
    credit_audit_records.json
    closed_issues.json
    issues.json
    profile_aliases.json      Cached Drupal.org profile URL aliases
    credit_approvals.json
  reports/
    release-notes-{milestone}.html
    contributors-all-releases.html
    credit-audit.html
    milestone-assignments.html
    milestone-closed-on-future.html
    release-status-{milestone}.txt
    compare-drupalorg-*.html  (from combined_milestone_report.py)
  summaries/
    {milestone}.prompt.md     Regenerated with release notes
    {milestone}.txt           Optional AI-written summary (used in report)
```

## Notes

- GitLab issues and Drupal.org credits are separate systems linked by issue URL.
- **Wrong milestone** compares GitLab assignment to the suggested milestone from close date and `period_source` windows.
- Be respectful of API rate limits — the tool caches aggressively and paginates GitLab requests.
