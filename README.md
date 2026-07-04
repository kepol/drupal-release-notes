# issue credit report

Tools for Drupal contrib release preparation: release notes, contributor credit audits, and pre-release status checks.

Each project has its own directory (`{project}/cache/`, `{project}/reports/`, etc.). The default project is [ai_context](https://www.drupal.org/project/ai_context) (Context Control Center).

| Script | Purpose |
|--------|---------|
| `scripts/release_notes.py` | Release credit reports grouped by release period |
| `scripts/credit_audit.py` | Find missing or incomplete credits; track reviewed issues |
| `scripts/release_prep.py` | Pre-release checklist for a GitLab milestone |

Reports are grouped by release date ranges, with credited issues listed by category, contributor counts for people and organizations, and markdown output ready to paste into Drupal.org release notes.

## Requirements

- Python 3.10+
- `requests` and `keyring` (see `scripts/requirements.txt`)

```bash
python3 -m pip install -r scripts/requirements.txt
```

All scripts accept `--project MACHINE_NAME` (default: `ai_context`). Paths below use `ai_context/` as the example.

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

Output:

- `ai_context/reports/{milestone}.md` — release notes
- `ai_context/reports/credit-audit.md` — credit review report

After cloning this repo, cached data under `{project}/cache/` is reused so you do not need to refetch everything from Drupal.org and GitLab.

Use `--project MACHINE_NAME` to target another project directory (see [Adding a project](#adding-a-project)).

## Adding a project

Create a directory named after the Drupal.org project machine name:

```bash
mkdir -p my_module/cache my_module/reports my_module/summaries
```

Add `my_module/config.json`:

```json
{
  "machine_name": "my_module",
  "drupal_org_nid": 1234567,
  "period_source": "releases",
  "milestone_close_grace_hours": 24
}
```

### Period source (`period_source`)

Controls how `release_prep.py` maps issue close dates to milestones:

| Value | Use when |
|-------|----------|
| `"releases"` (default) | No GitLab milestone dates, or you want windows derived from Drupal.org release tags |
| `"milestones"` | GitLab milestones have meaningful start/due dates you can extend (e.g. beta1 due date pushed out while traveling) |

With `"milestones"`, the tool reads each matching GitLab milestone's **start date** and **due date** (plus `milestone_close_grace_hours` after the due date). Adjust those dates on GitLab to finetune which issues belong to each release.

With `"releases"`, windows come from Drupal.org tag timestamps instead.

Optional filters when using `"milestones"`:

```json
{
  "period_source": "milestones",
  "milestone_exclude_titles": ["Future", "Enablement"],
  "milestone_include_pattern": "^\\d+\\.\\d+\\.\\d+(-(alpha|beta|rc)\\d*)?$"
}
```

`milestone_close_grace_hours` (default `24`) adds extra time after each boundary — after a **release tag** (`releases` mode) or after a milestone **due date** (`milestones` mode).

Release **notes** follow `period_source` when set to `"milestones"`: one report per GitLab milestone title (files like `reports/1.0.0-beta1.md`), and credited issues are included when **assigned to that milestone** on GitLab.

```bash
python3 scripts/release_notes.py --period "1.0.0-beta1" --rebuild-frozen
python3 scripts/credit_audit.py --refresh   # refresh milestone assignments in cache
```

With `"releases"` (default), release notes use Drupal.org tag windows and release-derived slugs (e.g. `beta2-to-now.md`).

Find the project node ID (`drupal_org_nid`) on the project page URL, e.g. `https://www.drupal.org/project/my_module` → view source or API, or from `https://www.drupal.org/api-d7/node.json?type=project&field_project_machine_name=my_module`.

Optional per-project files:

- `my_module/exclude_from_lists.txt` — hide issues from release note bullet lists
- `my_module/ignore_uncredited_people.txt` — usernames not expected to receive credit

Then run with `--project my_module`:

```bash
python3 scripts/release_prep.py --project my_module --milestone "1.0.0-beta1"
python3 scripts/release_notes.py --project my_module
python3 scripts/credit_audit.py --project my_module
```

## Report periods

Behavior depends on `period_source` in `{project}/config.json`.

### Milestones mode (`period_source: "milestones"`)

One report per matching GitLab milestone. **Filenames and `--period` use the milestone title** (e.g. `1.0.0-beta1`, `1.0.0-beta3`):

| File | Milestone |
|------|-----------|
| `reports/1.0.0-alpha.md` | `1.0.0-alpha` |
| `reports/1.0.0-beta1.md` | `1.0.0-beta1` |
| `reports/1.0.0-beta2.md` | `1.0.0-beta2` |
| `reports/1.0.0-beta3.md` | `1.0.0-beta3` (current) |

Credited issues are included when assigned to that milestone on GitLab. Milestone start/due dates (plus grace) define the release window for unassigned issues and for `release_prep.py` scoping.

When you add a new GitLab milestone, the next run picks it up automatically. No Drupal.org slug mapping.

### Releases mode (`period_source: "releases"`, default)

Period boundaries come from tagged releases on [drupal.org/project/ai_context/releases](https://www.drupal.org/project/ai_context/releases). Dev branches such as `1.0.x-dev` are ignored.

Each run prints the release versions found, for example:

```
Release boundaries from Drupal.org: 0.1.0-alpha1, 1.0.0-beta1, 1.0.0-beta2
```

For each consecutive pair of releases, the script creates a report period. The most recent release always gets an open-ended `{last}-to-now` period:

| Slug | Period |
|------|--------|
| `pre-alpha1` | Inception → 0.1.0-alpha1 |
| `alpha1-to-beta1` | 0.1.0-alpha1 → 1.0.0-beta1 |
| `beta1-to-beta2` | 1.0.0-beta1 → 1.0.0-beta2 |
| `beta2-to-now` | 1.0.0-beta2 → now (incremental) |

When a new release is published (e.g. `1.0.0-beta3`), the next run automatically adds frozen `beta2-to-beta3` and opens `beta3-to-now`.

Issues are placed by GitLab close date within each release tag window.

### Caching

Completed periods are cached in `{project}/cache/periods/` and only recomputed with `--rebuild-frozen`. The current (non-frozen) period is regenerated on every run.

## Output format

Each `{project}/reports/{milestone}.md` file includes:

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

Typical order before cutting a release:

```bash
# 1. Check milestone progress, credits, QA issue, release notes
python3 scripts/release_prep.py --milestone "1.0.0-beta3"

# 2. Review and resolve credit issues interactively
python3 scripts/credit_audit.py --review

# 3. Refresh release notes for the current milestone
python3 scripts/release_notes.py --period "1.0.0-beta3" --refresh-records --refresh-issues
```

After the release is **published** on Drupal.org:

```bash
# Refresh credits and issue labels
python3 scripts/release_notes.py --refresh-records --refresh-issues

# Or only the current milestone
python3 scripts/release_notes.py --period "1.0.0-beta3" --refresh-records --refresh-issues

# Optional: regenerate AI summary prompt
python3 scripts/release_notes.py --period "1.0.0-beta3" --write-summary-prompts
```

### Full rebuild (rare)

```bash
python3 scripts/release_notes.py --refresh-records --refresh-issues --rebuild-frozen
```

### One milestone only

```bash
python3 scripts/release_notes.py --period "1.0.0-beta1"
```

## Release status

`release_prep.py` prints a formatted pre-release checklist from cached audit data and live GitLab milestone queries:

```bash
python3 scripts/release_prep.py --milestone "1.0.0-beta3"
```

| Line | Meaning |
|------|---------|
| **Open in milestone** | Open issues still in the milestone (with link to milestone page) |
| **Credit audit pending** | In-scope issues needing credit review; includes `--review` command when > 0 |
| **QA issue** | Looks for a `CCC {release} QA` issue (e.g. `CCC beta3 QA`) |
| **Release notes** | Report for this GitLab milestone (e.g. `reports/1.0.0-beta3.md`) |
| **Duplicate d.o records** | In-scope issues with multiple Drupal.org nodes |
| **Missing contribution records** | In-scope closed issues with no record on new.drupal.org (action needed) |
| **No record expected** | In-scope issues with `why::duplicate`, `why::wontFix`, or `why::worksAsDesigned` — no record by design |
| **Wrong milestone** | In-scope issues where GitLab milestone is set but doesn't match close date |
| **Missing in milestone** | Issues **assigned on GitLab** to this milestone without a contribution record |

Sections marked **in scope** include issues assigned to the milestone on GitLab **or** closed within that release's time window. The window comes from `period_source` in `{project}/config.json` (GitLab milestone dates or Drupal.org release tags). The report header shows which source is active, e.g. `[milestones]` or `[releases]`.

Example output:

```
----------------------------------------
Release status: ai_context (1.0.0-beta3)
----------------------------------------

* Open in milestone: 7 of 86 — https://git.drupalcode.org/project/ai_context/-/milestones/5

* Credit audit pending: 2 — python3 scripts/credit_audit.py --project ai_context --review

* QA issue: opened (https://git.drupalcode.org/project/ai_context/-/work_items/3586296)

* Release notes: ai_context/reports/1.0.0-beta3.md (83 credited)

* Duplicate d.o records: 1
    #3586238: Fix PHPStan failures in CCC — https://new.drupal.org/node/11454931, https://new.drupal.org/node/11454932

* Missing contribution records: 0 (closed on GitLab, nothing on new.drupal.org)
    (none)

* No record expected (duplicate / won't fix): 4 (closed without a Drupal.org record by design)
    - #3586286: `hook_ai_context_scope_values_alter()` is ignored by scope forms and labels
    - #3586313: Syncing saves bypass all integrity constraints instead of only the global cap
    - #3586314: Item form discards user-entered scope when the subcontext feature is disabled
    - #3586316: Harden update 10011: empty-chunk guard and NULL-only backfill

* Wrong milestone: 1 (close date maps to a different release than '1.0.0-beta3')
    #3586149: Question about "Subcontext type = Conditional - included based on relevance" — closed 2026-05-03, '1.0.0-beta3' → '1.0.0-beta2' (https://git.drupalcode.org/project/ai_context/-/work_items/3586149)

* Missing in milestone: 0 (closed in '1.0.0-beta3' without a record)
    (none)
```

Run `python3 scripts/credit_audit.py --refresh` first if cache counts look stale.

### Backfill missing milestones

If GitLab milestones were not created for early releases (e.g. work started before the project moved to GitLab), list every closed issue grouped by the milestone it should have:

```bash
# All releases (alpha1, beta1, beta2, beta3, …)
python3 scripts/release_prep.py --list-by-milestone --write-output

# One release only
python3 scripts/release_prep.py --list-by-milestone --milestone "1.0.0-beta1"
python3 scripts/release_prep.py --list-by-milestone --milestone "1.0.0-beta2"
```

Each line includes the issue number, title, close date, **current** GitLab milestone (often `(none)`), and URL. Output is also written to `{project}/reports/milestone-assignments.md` with `--write-output`.

Create the missing milestones on GitLab, then assign issues from the list.

## Credit audit

Use `scripts/credit_audit.py` to find closed issues where credits may be incomplete:

- **No contribution record** — closed on GitLab, nothing on new.drupal.org yet
- **No credits granted** — record exists but nobody has “Credit this contributor” checked
- **Uncredited people** — listed on the record but not granted credit (often reviewers or people you decided not to credit)

Issues labeled `why::duplicate`, `why::wontFix`, or `why::worksAsDesigned` on GitLab are exempt (no record and/or no credits expected) and are excluded from `--review` and from release-notes gap warnings.

Project managers who only add labels (not code) can be listed in `{project}/ignore_uncredited_people.txt`. If they are the **only** uncredited people on an issue, it is omitted from `--review`.

```bash
# Generate ai_context/reports/credit-audit.md (uses cache after first run)
python3 scripts/credit_audit.py

# Step through each issue interactively
python3 scripts/credit_audit.py --review

# Refresh all records and closed GitLab issues from the API
python3 scripts/credit_audit.py --refresh

# Refresh one issue after editing credits on Drupal.org (faster than --refresh)
python3 scripts/credit_audit.py --refresh-issue 3579841

# Re-fetch GitLab comments for uncredited people
python3 scripts/credit_audit.py --refresh-comments
```

For each uncredited person on a pending issue, the audit loads their GitLab **issue** comments and **merge request** comments (when a linked MR is found). Results are cached in `{project}/cache/issue_activity.json`.

The terminal summary also lists **closed issues without contribution records** and **duplicate Drupal.org records** (same issue, multiple nodes).

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

Add `--project ai_context` to any of the above when not using the default project.

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

### `release_notes.py`

```
--project NAME           Drupal project machine name (default: ai_context)
--period SLUG            Period slug or 'all' (default). Slugs derived from releases.
--refresh-records        Re-fetch contribution records from new.drupal.org
--refresh-issues         Re-fetch GitLab issue metadata
--rebuild-frozen         Recompute frozen period reports
--exclude-list PATH      Alternate exclusion list (default: {project}/exclude_from_lists.txt)
--write-summary-prompts  Write {project}/summaries/{period}.prompt.md for AI summaries
```

### `credit_audit.py`

```
--project NAME           Drupal project machine name (default: ai_context)
--review                 Step through pending issues interactively
--refresh                Re-fetch all contribution records and closed GitLab issues
--refresh-issue IID      Re-fetch one issue's records (and its GitLab comments)
--refresh-comments       Re-fetch GitLab issue/MR comments for uncredited people
--approve TARGET         Approve issue (IID) or person (IID:username)
--unapprove TARGET       Remove an approval
--list-approvals         Print saved approvals
--ignore-list PATH       Alternate ignore list for PM usernames
--store-gitlab-token     Save GitLab token to OS keychain
--clear-gitlab-token     Remove GitLab token from keychain
```

### `release_prep.py`

```
--project NAME           Drupal project machine name (default: ai_context)
--milestone TITLE        GitLab milestone title (required for status report)
--list-by-milestone      List closed issues grouped by suggested milestone
--write-output           With --list-by-milestone, write milestone-assignments.md
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
  release_prep.py         Pre-release milestone status summary
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
  reports/                  Generated markdown reports (release notes, credit audit)
    credit-audit.md           Credit review report
  summaries/
    {period}.prompt.md        AI prompt input (optional to regenerate)
    {period}.txt              Custom summary paragraph (optional)
```

Add more projects as sibling directories (`my_module/`, etc.) with the same structure.

## Notes

- Only issues with at least one granted credit (`field_credit_this_contributor`) are included in release reports.
- GitLab issues and Drupal.org credits are separate systems linked by issue URL.
- Per-record fetches use `resourceVersion=rel:latest-version` on new.drupal.org so contributor data reflects the latest revision.
- If Drupal.org shows credits in the UI but `--refresh-issue` still reports someone as uncredited, new.drupal.org may be serving stale API data — try again later or use `--approve` to mark reviewed locally.
- **Wrong milestone** compares GitLab assignment to the suggested milestone from `period_source` (milestone dates or release tags + grace). Release-day issues like [Create CCC beta2 release](https://git.drupalcode.org/project/ai_context/-/work_items/3585920) stay on that milestone when the due date or grace covers their close time.
- Be respectful of API rate limits. This tool caches aggressively and fetches GitLab issues in paginated batches rather than one request per issue.
