# Summary prompt: 1.0.0-beta1 to 1.0.0-beta2

Write 1–2 paragraphs summarizing this release for Drupal.org release notes.
Focus on user-facing value, major themes, and stability improvements.
Do not list every issue; synthesize the work below.

Period: 1.0.0-beta1 to 1.0.0-beta2
Credited issues in this report: 98

## New Features
- #3556909: [Discuss] Decouple AI Context from AI Agents
- #3575590: Add ai_agents_debugger debug and ai_agents_explorer explore operations and links in CCC
- #3577428: Update context item target entities for progressive enhancement
- #3581533: Do not link to agent edit form unless the user has access
- #3582288: SystemPromptSubscriber re-injects full context on every agent loop iteration
- #3582920: Add entity type and bundle context scope plugin
- #3584838: Add convenience API for non-agent programmatic context retrieval
- #3585041: Local tasks for scopes should be dynamically generated
- #3586120: Make subcontext feature optional

## Bug Fixes
- #3577512: Duplicate Revisions tabs appear when editing an AI Context Item.
- #3577745: Context item revision comparison is missing some scope info
- #3578114: Update context scope plugin manage link/url/route functionality
- #3578386: Multiple entities can be set on the target entity reference autocomplete field but only 1 is saved
- #3578657: Drupal 10: Error on /admin/ai/context/items/add: scheduler_content_moderation_integration module conflict
- #3579394: CCC icon doesn't show in vanilla Drupal 10 and Drupal 11 install
- #3579396: CCC target entity types settings not working
- #3579841: Can't Apply Scheduler Patch
- #3580400: CCC mkdocs failing in CI pipeline
- #3581498: Required parameter '$logger_factory' missing in AiContextItemStorage
- #3581501: ai_context_install breaks existing config site installs (and probably recipes)
- #3586139: Add regular CCC contributors as GitLab reporter members
- #3586143: ai_context overview CSS references missing   external.svg asset via bad relative path
- #3586158: Fix custom path matching for site section scope
- #3586159: Require provider for conditional subcontext before RC1
- #3586191: Long context items are skipped instead of truncated when max token limit is reached
- #3586223: Fatal errors when uninstalling CCC
- #3586227: CCC navigation icon missing due to menu changes

## Other Major Contributions
- #3556881: [Discuss] Finalize name for AI Context module (Context Control Center)
- #3567570: [Meta] Context Control Center MVP demo
- #3569776: Adopt AI Core shared UI library in CCC and escape data before rendering
- #3573715: Full UX review of CCC in prep for rc1
- #3574136: Go through Chicago CCC test cases and make sure they work
- #3574359: Refactor context selection logic
- #3574445: Add Drupal CMS 2.0 CCC install steps on the project page
- #3574905: CCC: Refactor to denormalize scope values and replace SQL LIKE on serialized scope
- #3574906: CCC: Refactor to move key form validations into entity-level validators / presave
- #3574907: CCC: Refactor to normalize and index ai_context_usage; make cron pruning batched
- #3574908: CCC: Refactor to convert entity HTML helpers to data-only methods and render arrays
- #3576100: [Discuss] CCC architecture audit decision log questions
- #3576102: Pre-beta security review in prep for CCC beta1
- #3577427: Update context item revision diff feature for progressive enhancement
- #3577644: CCC beta1 release planning
- #3577670: CCC Chicago planning
- #3579354: Generate CCC beta1 release notes with contributing organizations and individuals
- #3585902: CCC beta2 release planning
- #3586142: Configure GitLab metadata for CCC
- #3586189: Stabilize global context item ordering before RC1
- #3586193: Test CCC on Drupal CMS 2.1
- #3586194: [Discuss] Conditional subcontext logic
- #3586202: CCC beta2 codebase review

## Additional Contributions (titles only)
- #3547037: Add AI CCC documentation for beta1
- #3547038: Update AI CCC project page for beta1
- #3549849: Update CCC readme in prep for beta1
- #3571354: Create CCC example module that adds scope plugin and extends existing plugins
- #3574904: CCC: Refactor to remove N+1 patterns: batch children & term loads
- #3574910: CCC: Refactor to harden function-call plugin / runtime surface (GetAiRelevantContext)
- #3576092: [Discuss] Subcontext scope vs parent scope
- #3576094: Fix local ./lint.sh stylelint script errors for CCC
- #3577379: Sprint 5 CCC roadmap updates, sprint planning, and issue triage
- #3577425: [Discuss] Possible styling updates for context listing
- #3577426: Redo context item duplicate feature without ECA
- #3577656: Remove zero badge when context has no subcontext
- #3577658: CCC beta1 video
- #3577661: CCC Chicago session slides
- #3577664: CCC Chicago keynote slides
- #3577667: Create CCC beta1 release
- #3577669: CCC beta1 QA
- #3579234: Add context scope plugin target entities manage link
- #3579344: Create CONTRIBUTORS.md for CCC
- #3579372: Test error: "The node_make_sticky_action plugin does not exist" when running CCC tests locally
- #3582494: Analyze CCC roadmap notes against issue queue
- #3582504: Analyze CCC features and roadmap against context engineering best practices
- #3582536: Sprint 6 CCC roadmap updates, sprint planning, and issue triage
- #3582544: Fix PHPStan errors in CCC after 2.1.45 release
- #3582562: Increase gitlab ci timeout for CCC
- #3583319: Drupal Developer Days CCC contribution planning
- #3585850: Sprint 8 CCC roadmap updates, sprint planning, and issue triage
- #3585917: CCC beta testing at Drupal Dev Days (DDD) 2026
- #3586090: Remove Scheduler content moderation integration CCC patch once a new release is available
- #3586091: Review CCC todo comments for action items
- #3586108: Address todos in scope form rendering and persistence tests
- #3586109: Address todos in CCC taxonomy entity type dependency in kernel tests
- #3586110: Address todos in CCC empty scope / subscription handling tests
- #3586111: Address todos in CCC subscription update logic and scope visibility in tests
- #3586138: Still getting GitLab CI timeouts for CCC
- #3586140: Design Improved Context Items List View
- #3586141: Design for the Context Item single entity view (manual/markdown/text/static)
- #3586146: Normalize token/item limit naming — eliminate `tokenBudget` and align on `maxTokens`/`maxItems`
- #3586147: Clean up CCC inconsistencies and DX issues before rc1 (part 1)
- #3586149: Question about "Subcontext type = Conditional - included based on relevance"
- #3586152: Test CCC using DrupalForge DrupalCon Chicago Driesnote template
- #3586156: CCC beta2 QA
- #3586183: Sprint 9 CCC roadmap updates, sprint planning, and issue triage
- #3586184: Add `AiContextSelectorInterface` before RC1
- #3586185: Document subcontext entity validation rules for RC1
- #3586186: Set default usage record retention to 90 days
- #3586195: (Discuss) Logic for multiple context scope items being handled separately
- #3586224: Design for the Context Item single entity view (connected/remote/dynamic)

---

Save the finished summary to: summaries/beta1-to-beta2.txt

