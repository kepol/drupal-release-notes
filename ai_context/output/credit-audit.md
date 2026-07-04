# Credit audit

Closed ai_context issues that may need credit review on [new.drupal.org](https://new.drupal.org).

**2 issues need review** · **9 exempt (duplicate / won't fix)** · **74 ignored (PM labels only)** · **38 issues approved**

_Generated 2026-07-04T20:51:58.938038+00:00_

## How to approve

After reviewing an issue on Drupal.org, mark it so it won't appear again:

```bash
# Interactive review (step through each issue)
python3 scripts/credit_audit.py --project ai_context --review

# Whole issue reviewed (no record, no credits, or all uncredited people OK)
python3 scripts/credit_audit.py --project ai_context --approve 3586230

# Only one listed-but-uncredited person is OK
python3 scripts/credit_audit.py --project ai_context --approve 3586230:danrod

# Undo
python3 scripts/credit_audit.py --project ai_context --unapprove 3586230
python3 scripts/credit_audit.py --project ai_context --unapprove 3586230:danrod
```

Approvals are stored in `ai_context/cache/credit_approvals.json`.

## Duplicate contribution records (1)

Multiple published records point at the same GitLab issue. The audit merges credits across them, preferring records that have credits granted. Consider deleting stale duplicates on Drupal.org.

* [#3586238](https://git.drupalcode.org/project/ai_context/-/work_items/3586238): Fix PHPStan failures in CCC — [node/11454931](https://new.drupal.org/node/11454931), [node/11454932](https://new.drupal.org/node/11454932)

## No contribution record (0)

_None._

## Contribution record with no credits granted (0)

_None._

## People listed but not credited (2)

* [#3579841](https://git.drupalcode.org/project/ai_context/-/work_items/3579841): Can't Apply Scheduler Patch
  * Contribution record: [node/11446290](https://new.drupal.org/node/11446290)
  * Credited: kepol, marcus_johansson, robloach
  * Uncredited: rajabnatshah
  * `rajabnatshah` activity:
    Issue comments by `rajabnatshah`:
    - [2026-05-10 15:29:58] Thank you so much for working on the CCC module, it is so important. Hopping for a new tag release. as the patch is not longer needed.
    - [2026-05-10 15:41:59] Thanks @kepol managing with ``` "composer-patches": { "ignore-dependency-patches": ["drupal/ai_context"] }, ``` Trying to manage a wiled card one in projects not to add a static one like ``` "compose…
    - [2026-05-10 15:53:50] I confirm the issue still remain on Uninstall
    - [2026-05-10 15:59:53] I talked with Adam about having something like `drupal/drupal_cms_patches` or `drupal/cmspatches` Much like the [drupal/webpatches](http://drupal.org/project/webpatches) with a bit of UI listing for…
    Merge request comments by `rajabnatshah`: no linked MR found
  * Approve `rajabnatshah`: `python3 scripts/credit_audit.py --project ai_context --approve 3579841:rajabnatshah`
  * Approve issue: `python3 scripts/credit_audit.py --project ai_context --approve 3579841`

* [#3586207](https://git.drupalcode.org/project/ai_context/-/work_items/3586207): Conditional Subcontext Provider Calls
  * Contribution record: [node/11466693](https://new.drupal.org/node/11466693)
  * Credited: abhisekmazumdar, ahmad-khalil-imagex, kepol, mglaman
  * Uncredited: aidanfoster
  * `aidanfoster` activity:
    Issue comments by `aidanfoster`:
    - [2026-06-24 17:46:47] Emma and I met and suggest: If context sub-item is created but the setting are changed to disable them we think they should: 1. Any agent calling the parent context ignores them. 2. They should appea…
    Merge request comments by `aidanfoster`: no linked MR found
  * Approve `aidanfoster`: `python3 scripts/credit_audit.py --project ai_context --approve 3586207:aidanfoster`
  * Approve issue: `python3 scripts/credit_audit.py --project ai_context --approve 3586207`

## No credits expected — duplicate / won't fix (9)

GitLab labels `why::duplicate` or `why::wontFix`. These issues do not need a contribution record or granted credits.

* [#3547042](https://git.drupalcode.org/project/ai_context/-/work_items/3547042): Update AI CCC project page
  * GitLab label: `why::duplicate` (duplicate)
  * Contribution record: [node/11424635](https://new.drupal.org/node/11424635)

* [#3570934](https://git.drupalcode.org/project/ai_context/-/work_items/3570934): Add content type context scope for MVP
  * GitLab label: `why::wontFix` (won't fix)
  * Contribution record: [node/11440303](https://new.drupal.org/node/11440303)

* [#3586190](https://git.drupalcode.org/project/ai_context/-/work_items/3586190): Allow AI Context provider/model setting to be explicitly unset
  * GitLab label: `why::wontFix` (won't fix)
  * Contribution record: [node/11454558](https://new.drupal.org/node/11454558)

* [#3586205](https://git.drupalcode.org/project/ai_context/-/work_items/3586205): Avoid recreating scope plugins during selection
  * GitLab label: `why::duplicate` (duplicate)
  * Contribution record: [node/11454536](https://new.drupal.org/node/11454536)

* [#3586286](https://git.drupalcode.org/project/ai_context/-/work_items/3586286): `hook_ai_context_scope_values_alter()` is ignored by scope forms and labels
  * GitLab label: `why::duplicate` (duplicate)

* [#3586312](https://git.drupalcode.org/project/ai_context/-/work_items/3586312): Unset inherit_parent_scope silently wipes stored scope on save (data loss)
  * GitLab label: `why::duplicate` (duplicate)
  * Contribution record: [node/11468778](https://new.drupal.org/node/11468778)

* [#3586313](https://git.drupalcode.org/project/ai_context/-/work_items/3586313): Syncing saves bypass all integrity constraints instead of only the global cap
  * GitLab label: `why::duplicate` (duplicate)

* [#3586314](https://git.drupalcode.org/project/ai_context/-/work_items/3586314): Item form discards user-entered scope when the subcontext feature is disabled
  * GitLab label: `why::duplicate` (duplicate)

* [#3586316](https://git.drupalcode.org/project/ai_context/-/work_items/3586316): Harden update 10011: empty-chunk guard and NULL-only backfill
  * GitLab label: `why::duplicate` (duplicate)

## Ignored uncredited — project managers (74)

The only listed-but-uncredited people are in `ignore_uncredited_people.txt` (PMs who add labels, not code).

* [#3547034](https://git.drupalcode.org/project/ai_context/-/work_items/3547034): [Spike] Research URL support for CCC
  * Credited: aidanfoster, ajv009, kepol, robloach, unqunq, webbywe
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11424627](https://new.drupal.org/node/11424627)

* [#3547037](https://git.drupalcode.org/project/ai_context/-/work_items/3547037): Add AI CCC documentation for beta1
  * Credited: danrod, kepol, robloach
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11424630](https://new.drupal.org/node/11424630)

* [#3547038](https://git.drupalcode.org/project/ai_context/-/work_items/3547038): Update AI CCC project page for beta1
  * Credited: danrod, erichomanchuk, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11424631](https://new.drupal.org/node/11424631)

* [#3549849](https://git.drupalcode.org/project/ai_context/-/work_items/3549849): Update CCC readme in prep for beta1
  * Credited: guptahemant, kepol, naveen.prakash.work
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11426492](https://new.drupal.org/node/11426492)

* [#3556881](https://git.drupalcode.org/project/ai_context/-/work_items/3556881): [Discuss] Finalize name for AI Context module (Context Control Center)
  * Credited: aidanfoster, danrod, emma-horrell, jibran, kepol, robloach, ronaldtebrake, scottfalconer, wouters_frederik
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11431121](https://new.drupal.org/node/11431121)

* [#3556908](https://git.drupalcode.org/project/ai_context/-/work_items/3556908): Do not hardcode English language prompts in CCC
  * Credited: breidert, horvan, kepol, kumarimedha09, marcus_johansson, svendecabooter
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11431135](https://new.drupal.org/node/11431135)

* [#3556909](https://git.drupalcode.org/project/ai_context/-/work_items/3556909): [Discuss] Decouple AI Context from AI Agents
  * Credited: kepol, marcus_johansson
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11431136](https://new.drupal.org/node/11431136)

* [#3564667](https://git.drupalcode.org/project/ai_context/-/work_items/3564667): Add a composer.json to CCC
  * Credited: kepol, marcus_johansson, shamir.vs, sujal_31
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11436040](https://new.drupal.org/node/11436040)

* [#3566852](https://git.drupalcode.org/project/ai_context/-/work_items/3566852): Add CCC overview page
  * Credited: bbruno, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11437557](https://new.drupal.org/node/11437557)

* [#3566858](https://git.drupalcode.org/project/ai_context/-/work_items/3566858): Update context items page with description and link when there are empty results
  * Credited: bbruno, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11437562](https://new.drupal.org/node/11437562)

* [#3566861](https://git.drupalcode.org/project/ai_context/-/work_items/3566861): Update CCC general settings page descriptions
  * Credited: bbruno, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11437565](https://new.drupal.org/node/11437565)

* [#3566862](https://git.drupalcode.org/project/ai_context/-/work_items/3566862): Update context items settings page descriptions
  * Credited: bbruno, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11437566](https://new.drupal.org/node/11437566)

* [#3566863](https://git.drupalcode.org/project/ai_context/-/work_items/3566863): Update CCC agents settings page description and table
  * Credited: bbruno, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11437567](https://new.drupal.org/node/11437567)

* [#3566865](https://git.drupalcode.org/project/ai_context/-/work_items/3566865): Update context item edit form field descriptions
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11437569](https://new.drupal.org/node/11437569)

* [#3566866](https://git.drupalcode.org/project/ai_context/-/work_items/3566866): Update agent context edit form description, help text, and table
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11437570](https://new.drupal.org/node/11437570)

* [#3567791](https://git.drupalcode.org/project/ai_context/-/work_items/3567791): [Spike] CCC MCP server integration PoC
  * Credited: abhisekmazumdar, kepol, nikro
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11438236](https://new.drupal.org/node/11438236)

* [#3569776](https://git.drupalcode.org/project/ai_context/-/work_items/3569776): Adopt AI Core shared UI library in CCC and escape data before rendering
  * Credited: aidanfoster, b_sharpe, bbruno, erichomanchuk, kepol
  * Ignored (not expected to credit): arianraeesi, rakhimandhania
  * Contribution record: [node/11439560](https://new.drupal.org/node/11439560)

* [#3572891](https://git.drupalcode.org/project/ai_context/-/work_items/3572891): Create docs for Cursor and Claude code quality for CCC
  * Credited: dstorozhuk, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11441564](https://new.drupal.org/node/11441564)

* [#3573715](https://git.drupalcode.org/project/ai_context/-/work_items/3573715): Full UX review of CCC in prep for rc1
  * Credited: aidanfoster, bbruno, emma-horrell, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442054](https://new.drupal.org/node/11442054)

* [#3574136](https://git.drupalcode.org/project/ai_context/-/work_items/3574136): Go through Chicago CCC test cases and make sure they work
  * Credited: aidanfoster, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442377](https://new.drupal.org/node/11442377)

* [#3574420](https://git.drupalcode.org/project/ai_context/-/work_items/3574420): Add Drupal CMS 2.0 support to CCC
  * Credited: axioteo, divyamdotfoo, hrishikesh-dalal, kepol, kostiantyn
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442549](https://new.drupal.org/node/11442549)

* [#3574445](https://git.drupalcode.org/project/ai_context/-/work_items/3574445): Add Drupal CMS 2.0 CCC install steps on the project page
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442566](https://new.drupal.org/node/11442566)

* [#3574905](https://git.drupalcode.org/project/ai_context/-/work_items/3574905): CCC: Refactor to denormalize scope values and replace SQL LIKE on serialized scope
  * Credited: abhisekmazumdar, kepol, scottfalconer
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442880](https://new.drupal.org/node/11442880)

* [#3574906](https://git.drupalcode.org/project/ai_context/-/work_items/3574906): CCC: Refactor to move key form validations into entity-level validators / presave
  * Credited: danrod, kepol, scottfalconer, svendecabooter
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442881](https://new.drupal.org/node/11442881)

* [#3574907](https://git.drupalcode.org/project/ai_context/-/work_items/3574907): CCC: Refactor to normalize and index ai_context_usage; make cron pruning batched
  * Credited: kepol, scottfalconer
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442882](https://new.drupal.org/node/11442882)

* [#3574910](https://git.drupalcode.org/project/ai_context/-/work_items/3574910): CCC: Refactor to harden function-call plugin / runtime surface (GetAiRelevantContext)
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11442885](https://new.drupal.org/node/11442885)

* [#3575590](https://git.drupalcode.org/project/ai_context/-/work_items/3575590): Add ai_agents_debugger debug and ai_agents_explorer explore operations and links in CCC
  * Credited: axioteo, kepol, scottfalconer, unqunq
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11443348](https://new.drupal.org/node/11443348)

* [#3576093](https://git.drupalcode.org/project/ai_context/-/work_items/3576093): Fix eslint errors in GitLab UI even when pipeline is green
  * Credited: kepol, kieran.cott
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11443755](https://new.drupal.org/node/11443755)

* [#3576100](https://git.drupalcode.org/project/ai_context/-/work_items/3576100): [Discuss] CCC architecture audit decision log questions
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11443761](https://new.drupal.org/node/11443761)

* [#3576102](https://git.drupalcode.org/project/ai_context/-/work_items/3576102): Pre-beta security review in prep for CCC beta1
  * Credited: erichomanchuk, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11443762](https://new.drupal.org/node/11443762)

* [#3577379](https://git.drupalcode.org/project/ai_context/-/work_items/3577379): Sprint 5 CCC roadmap updates, sprint planning, and issue triage
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444732](https://new.drupal.org/node/11444732)

* [#3577398](https://git.drupalcode.org/project/ai_context/-/work_items/3577398): Update CCC readme for new mdxeditor location
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444748](https://new.drupal.org/node/11444748)

* [#3577425](https://git.drupalcode.org/project/ai_context/-/work_items/3577425): [Discuss] Possible styling updates for context listing
  * Credited: aidanfoster, bbruno, emma-horrell, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444768](https://new.drupal.org/node/11444768)

* [#3577426](https://git.drupalcode.org/project/ai_context/-/work_items/3577426): Redo context item duplicate feature without ECA
  * Credited: kepol, kostiantyn, scottfalconer
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444769](https://new.drupal.org/node/11444769)

* [#3577427](https://git.drupalcode.org/project/ai_context/-/work_items/3577427): Update context item revision diff feature for progressive enhancement
  * Credited: a.dmitriiev, danrod, dstorozhuk, erichomanchuk, kepol, scottfalconer
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444770](https://new.drupal.org/node/11444770)

* [#3577428](https://git.drupalcode.org/project/ai_context/-/work_items/3577428): Update context item target entities for progressive enhancement
  * Credited: annmarysruthy, danrod, kepol, kostiantyn, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444771](https://new.drupal.org/node/11444771)

* [#3577512](https://git.drupalcode.org/project/ai_context/-/work_items/3577512): Duplicate Revisions tabs appear when editing an AI Context Item.
  * Credited: annmarysruthy, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444830](https://new.drupal.org/node/11444830)

* [#3577644](https://git.drupalcode.org/project/ai_context/-/work_items/3577644): CCC beta1 release planning
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444907](https://new.drupal.org/node/11444907)

* [#3577656](https://git.drupalcode.org/project/ai_context/-/work_items/3577656): Remove zero badge when context has no subcontext
  * Credited: bbruno, kepol, nexusnovaz
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444918](https://new.drupal.org/node/11444918)

* [#3577657](https://git.drupalcode.org/project/ai_context/-/work_items/3577657): CCC beta blog post
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444919](https://new.drupal.org/node/11444919)

* [#3577658](https://git.drupalcode.org/project/ai_context/-/work_items/3577658): CCC beta1 video
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444920](https://new.drupal.org/node/11444920)

* [#3577661](https://git.drupalcode.org/project/ai_context/-/work_items/3577661): CCC Chicago session slides
  * Credited: aidanfoster, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444922](https://new.drupal.org/node/11444922)

* [#3577664](https://git.drupalcode.org/project/ai_context/-/work_items/3577664): CCC Chicago keynote slides
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444924](https://new.drupal.org/node/11444924)

* [#3577667](https://git.drupalcode.org/project/ai_context/-/work_items/3577667): Create CCC beta1 release
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444926](https://new.drupal.org/node/11444926)

* [#3577669](https://git.drupalcode.org/project/ai_context/-/work_items/3577669): CCC beta1 QA
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444927](https://new.drupal.org/node/11444927)

* [#3577670](https://git.drupalcode.org/project/ai_context/-/work_items/3577670): CCC Chicago planning
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11444928](https://new.drupal.org/node/11444928)

* [#3578114](https://git.drupalcode.org/project/ai_context/-/work_items/3578114): Update context scope plugin manage link/url/route functionality
  * Credited: danrod, erichomanchuk, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11445189](https://new.drupal.org/node/11445189)

* [#3578386](https://git.drupalcode.org/project/ai_context/-/work_items/3578386): Multiple entities can be set on the target entity reference autocomplete field but only 1 is saved
  * Credited: annmarysruthy, erichomanchuk, kepol, scottfalconer
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11445363](https://new.drupal.org/node/11445363)

* [#3578657](https://git.drupalcode.org/project/ai_context/-/work_items/3578657): Drupal 10: Error on /admin/ai/context/items/add: scheduler_content_moderation_integration module conflict
  * Credited: annmarysruthy, dstorozhuk, kepol, scottfalconer
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11445570](https://new.drupal.org/node/11445570)

* [#3579344](https://git.drupalcode.org/project/ai_context/-/work_items/3579344): Create CONTRIBUTORS.md for CCC
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11445962](https://new.drupal.org/node/11445962)

* [#3579394](https://git.drupalcode.org/project/ai_context/-/work_items/3579394): CCC icon doesn't show in vanilla Drupal 10 and Drupal 11 install
  * Credited: bbruno, kepol, svendecabooter
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11445994](https://new.drupal.org/node/11445994)

* [#3579396](https://git.drupalcode.org/project/ai_context/-/work_items/3579396): CCC target entity types settings not working
  * Credited: annmarysruthy, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11445995](https://new.drupal.org/node/11445995)

* [#3580910](https://git.drupalcode.org/project/ai_context/-/work_items/3580910): Improve config validation and use #config_target for settings form
  * Credited: abhisekmazumdar, kepol, mglaman, svendecabooter
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11446936](https://new.drupal.org/node/11446936)

* [#3584775](https://git.drupalcode.org/project/ai_context/-/work_items/3584775): Remove AiContextItemType
  * Credited: kepol, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11449473](https://new.drupal.org/node/11449473)

* [#3586116](https://git.drupalcode.org/project/ai_context/-/work_items/3586116): Update context listing to not use target column
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11450408](https://new.drupal.org/node/11450408)

* [#3586127](https://git.drupalcode.org/project/ai_context/-/work_items/3586127): Update context listing to show workflow state
  * Credited: kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11450416](https://new.drupal.org/node/11450416)

* [#3586155](https://git.drupalcode.org/project/ai_context/-/work_items/3586155): Create GitLab issue and merge request templates for ai_context project
  * Credited: kepol, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11466339](https://new.drupal.org/node/11466339)

* [#3586169](https://git.drupalcode.org/project/ai_context/-/work_items/3586169): [Discuss] Selection extension points and diagnostics for context selection
  * Credited: kepol, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11455040](https://new.drupal.org/node/11455040)

* [#3586170](https://git.drupalcode.org/project/ai_context/-/work_items/3586170): [Discuss] Structured context content format and authoring model
  * Credited: kepol, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11459797](https://new.drupal.org/node/11459797)

* [#3586192](https://git.drupalcode.org/project/ai_context/-/work_items/3586192): Clean up CCC inconsistencies and DX issues before rc1 (part 2)
  * Credited: ahmad-khalil-imagex, jucs7, kepol, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11459794](https://new.drupal.org/node/11459794)

* [#3586196](https://git.drupalcode.org/project/ai_context/-/work_items/3586196): [Discuss] Context scope matching semantics: additive OR, filters, and UX clarity
  * Credited: aidanfoster, emma-horrell, kepol
  * Ignored (not expected to credit): rakhimandhania, vidit-anjaria
  * Contribution record: [node/11466433](https://new.drupal.org/node/11466433)

* [#3586198](https://git.drupalcode.org/project/ai_context/-/work_items/3586198): [Discuss] Associating adhoc vocabularies (freetagging) with context items
  * Credited: aidanfoster, emma-horrell, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11454919](https://new.drupal.org/node/11454919)

* [#3586203](https://git.drupalcode.org/project/ai_context/-/work_items/3586203): Pre-rc1 CCC docs updates
  * Credited: kepol, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11454557](https://new.drupal.org/node/11454557)

* [#3586208](https://git.drupalcode.org/project/ai_context/-/work_items/3586208): CCC Non-Agent `match_all` Convenience API
  * Credited: abhisekmazumdar, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11459796](https://new.drupal.org/node/11459796)

* [#3586209](https://git.drupalcode.org/project/ai_context/-/work_items/3586209): CCC Usage Tracking Query/Save Pattern
  * Credited: abhisekmazumdar, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11466797](https://new.drupal.org/node/11466797)

* [#3586210](https://git.drupalcode.org/project/ai_context/-/work_items/3586210): Update use case context scope defaults
  * Credited: aidanfoster, emma-horrell, kepol, mglaman
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11454404](https://new.drupal.org/node/11454404)

* [#3586211](https://git.drupalcode.org/project/ai_context/-/work_items/3586211): Update CCC overview page with hide option and new wording
  * Credited: aidanfoster, bbruno, emma-horrell, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11452454](https://new.drupal.org/node/11452454)

* [#3586212](https://git.drupalcode.org/project/ai_context/-/work_items/3586212): Update max context items in general settings
  * Credited: ahmad-khalil-imagex, aidanfoster, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11452452](https://new.drupal.org/node/11452452)

* [#3586214](https://git.drupalcode.org/project/ai_context/-/work_items/3586214): Hide additional context scope options if global is selected
  * Credited: aidanfoster, emma-horrell, jucs7, kepol
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11452451](https://new.drupal.org/node/11452451)

* [#3586228](https://git.drupalcode.org/project/ai_context/-/work_items/3586228): Create list of modules and configuration steps for how to integrate CCC with Document Loader MDXEditor submodule
  * Credited: ahmad-khader, aidanfoster, emma-horrell, kepol, robloach
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11454420](https://new.drupal.org/node/11454420)

* [#3586229](https://git.drupalcode.org/project/ai_context/-/work_items/3586229): CCC optional feature suggestions in UI
  * Credited: ahmad-khalil-imagex, aidanfoster, kepol, robloach
  * Ignored (not expected to credit): rakhimandhania
  * Contribution record: [node/11454917](https://new.drupal.org/node/11454917)

* [#3586259](https://git.drupalcode.org/project/ai_context/-/work_items/3586259): Fix phpstan error in AiContextSubcontextToggleTrait
  * Credited: kepol
  * Ignored (not expected to credit): vidit-anjaria
  * Contribution record: [node/11459798](https://new.drupal.org/node/11459798)

* [#3586261](https://git.drupalcode.org/project/ai_context/-/work_items/3586261): Clean up bundleless context item follow-ups
  * Credited: kepol, kieran.cott
  * Ignored (not expected to credit): vidit-anjaria
  * Contribution record: [node/11468032](https://new.drupal.org/node/11468032)

* [#3586280](https://git.drupalcode.org/project/ai_context/-/work_items/3586280): Add #[RunTestsInSeparateProcesses] attribute to all kernel test classes
  * Credited: ahmad-khader, jucs7, kepol
  * Ignored (not expected to credit): vidit-anjaria
  * Contribution record: [node/11467991](https://new.drupal.org/node/11467991)

## Approved (38)

_These closed issues were marked reviewed. Use `--unapprove` to restore them to the audit._

* [#3545824](https://git.drupalcode.org/project/ai_context/-/work_items/3545824): Create demo Context Control Center for Vienna 2025
* [#3547892](https://git.drupalcode.org/project/ai_context/-/work_items/3547892): CCC Function Call should load ContextDefinitionNormalizer via Dependency Injection
* [#3549081](https://git.drupalcode.org/project/ai_context/-/work_items/3549081): Group AI Context menu items
* [#3549082](https://git.drupalcode.org/project/ai_context/-/work_items/3549082): Within the Context Pools UI, link the Context for the forms to see the details of each context
* [#3550034](https://git.drupalcode.org/project/ai_context/-/work_items/3550034): Add AI context item usage data and page
* [#3550892](https://git.drupalcode.org/project/ai_context/-/work_items/3550892): Show description instead of id in the AI Contexts listing page
* [#3550895](https://git.drupalcode.org/project/ai_context/-/work_items/3550895): CCC tags should be required
* [#3552972](https://git.drupalcode.org/project/ai_context/-/work_items/3552972): Wrong dependency definition in info.yml causes composer to not install
* [#3554277](https://git.drupalcode.org/project/ai_context/-/work_items/3554277): ai_context_ai_function_call_info_alter does not work with contexts only set via "always_include"
* [#3557719](https://git.drupalcode.org/project/ai_context/-/work_items/3557719): [Spike] Research AI Context categories
* [#3558583](https://git.drupalcode.org/project/ai_context/-/work_items/3558583): AI Context UX meeting 18 Nov 2025
* [#3558814](https://git.drupalcode.org/project/ai_context/-/work_items/3558814): [Spike] CCC 1.0 brainstorming
* [#3563043](https://git.drupalcode.org/project/ai_context/-/work_items/3563043): Add toolbar icon to CCC top level menu item
* [#3563089](https://git.drupalcode.org/project/ai_context/-/work_items/3563089): Add revision comparison diff support for context item revisions
* [#3563127](https://git.drupalcode.org/project/ai_context/-/work_items/3563127): Add created date to context item entity
* [#3563975](https://git.drupalcode.org/project/ai_context/-/work_items/3563975): Something in CCC is causing node form to not show some fields
* [#3564706](https://git.drupalcode.org/project/ai_context/-/work_items/3564706): [Meta] Context Scope feature
* [#3564714](https://git.drupalcode.org/project/ai_context/-/work_items/3564714): Allow context scoped to entities in CCC
* [#3567571](https://git.drupalcode.org/project/ai_context/-/work_items/3567571): CCC MVP Demo: Create draft FinDrop context
* [#3568673](https://git.drupalcode.org/project/ai_context/-/work_items/3568673): Add context scope base code and use case context scope plugin
* … and 18 more
