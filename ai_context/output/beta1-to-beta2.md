# 1.0.0-beta1 to 1.0.0-beta2

**98 credited issues**

This release (1.0.0-beta1 to 1.0.0-beta2) includes 98 credited issues. It includes 9 new features, 18 bug fixes, 23 other major contributions, 48 additional contributions.

_Generated 2026-07-04T18:06:13.559386+00:00_

## New Features (9)

* [#3556909](https://git.drupalcode.org/project/ai_context/-/work_items/3556909): [Discuss] Decouple AI Context from AI Agents
* [#3575590](https://git.drupalcode.org/project/ai_context/-/work_items/3575590): Add ai_agents_debugger debug and ai_agents_explorer explore operations and links in CCC
* [#3577428](https://git.drupalcode.org/project/ai_context/-/work_items/3577428): Update context item target entities for progressive enhancement
* [#3581533](https://git.drupalcode.org/project/ai_context/-/work_items/3581533): Do not link to agent edit form unless the user has access
* [#3582288](https://git.drupalcode.org/project/ai_context/-/work_items/3582288): SystemPromptSubscriber re-injects full context on every agent loop iteration
* [#3582920](https://git.drupalcode.org/project/ai_context/-/work_items/3582920): Add entity type and bundle context scope plugin
* [#3584838](https://git.drupalcode.org/project/ai_context/-/work_items/3584838): Add convenience API for non-agent programmatic context retrieval
* [#3585041](https://git.drupalcode.org/project/ai_context/-/work_items/3585041): Local tasks for scopes should be dynamically generated
* [#3586120](https://git.drupalcode.org/project/ai_context/-/work_items/3586120): Make subcontext feature optional

## Bug Fixes (18)

* [#3577512](https://git.drupalcode.org/project/ai_context/-/work_items/3577512): Duplicate Revisions tabs appear when editing an AI Context Item.
* [#3577745](https://git.drupalcode.org/project/ai_context/-/work_items/3577745): Context item revision comparison is missing some scope info
* [#3578114](https://git.drupalcode.org/project/ai_context/-/work_items/3578114): Update context scope plugin manage link/url/route functionality
* [#3578386](https://git.drupalcode.org/project/ai_context/-/work_items/3578386): Multiple entities can be set on the target entity reference autocomplete field but only 1 is saved
* [#3578657](https://git.drupalcode.org/project/ai_context/-/work_items/3578657): Drupal 10: Error on /admin/ai/context/items/add: scheduler_content_moderation_integration module conflict
* [#3579394](https://git.drupalcode.org/project/ai_context/-/work_items/3579394): CCC icon doesn't show in vanilla Drupal 10 and Drupal 11 install
* [#3579396](https://git.drupalcode.org/project/ai_context/-/work_items/3579396): CCC target entity types settings not working
* [#3579841](https://git.drupalcode.org/project/ai_context/-/work_items/3579841): Can't Apply Scheduler Patch
* [#3580400](https://git.drupalcode.org/project/ai_context/-/work_items/3580400): CCC mkdocs failing in CI pipeline
* [#3581498](https://git.drupalcode.org/project/ai_context/-/work_items/3581498): Required parameter '$logger_factory' missing in AiContextItemStorage
* [#3581501](https://git.drupalcode.org/project/ai_context/-/work_items/3581501): ai_context_install breaks existing config site installs (and probably recipes)
* [#3586139](https://git.drupalcode.org/project/ai_context/-/work_items/3586139): Add regular CCC contributors as GitLab reporter members
* [#3586143](https://git.drupalcode.org/project/ai_context/-/work_items/3586143): ai_context overview CSS references missing   external.svg asset via bad relative path
* [#3586158](https://git.drupalcode.org/project/ai_context/-/work_items/3586158): Fix custom path matching for site section scope
* [#3586159](https://git.drupalcode.org/project/ai_context/-/work_items/3586159): Require provider for conditional subcontext before RC1
* [#3586191](https://git.drupalcode.org/project/ai_context/-/work_items/3586191): Long context items are skipped instead of truncated when max token limit is reached
* [#3586223](https://git.drupalcode.org/project/ai_context/-/work_items/3586223): Fatal errors when uninstalling CCC
* [#3586227](https://git.drupalcode.org/project/ai_context/-/work_items/3586227): CCC navigation icon missing due to menu changes

## Other Major Contributions (23)

* [#3556881](https://git.drupalcode.org/project/ai_context/-/work_items/3556881): [Discuss] Finalize name for AI Context module (Context Control Center)
* [#3567570](https://git.drupalcode.org/project/ai_context/-/work_items/3567570): [Meta] Context Control Center MVP demo
* [#3569776](https://git.drupalcode.org/project/ai_context/-/work_items/3569776): Adopt AI Core shared UI library in CCC and escape data before rendering
* [#3573715](https://git.drupalcode.org/project/ai_context/-/work_items/3573715): Full UX review of CCC in prep for rc1
* [#3574136](https://git.drupalcode.org/project/ai_context/-/work_items/3574136): Go through Chicago CCC test cases and make sure they work
* [#3574359](https://git.drupalcode.org/project/ai_context/-/work_items/3574359): Refactor context selection logic
* [#3574445](https://git.drupalcode.org/project/ai_context/-/work_items/3574445): Add Drupal CMS 2.0 CCC install steps on the project page
* [#3574905](https://git.drupalcode.org/project/ai_context/-/work_items/3574905): CCC: Refactor to denormalize scope values and replace SQL LIKE on serialized scope
* [#3574906](https://git.drupalcode.org/project/ai_context/-/work_items/3574906): CCC: Refactor to move key form validations into entity-level validators / presave
* [#3574907](https://git.drupalcode.org/project/ai_context/-/work_items/3574907): CCC: Refactor to normalize and index ai_context_usage; make cron pruning batched
* [#3574908](https://git.drupalcode.org/project/ai_context/-/work_items/3574908): CCC: Refactor to convert entity HTML helpers to data-only methods and render arrays
* [#3576100](https://git.drupalcode.org/project/ai_context/-/work_items/3576100): [Discuss] CCC architecture audit decision log questions
* [#3576102](https://git.drupalcode.org/project/ai_context/-/work_items/3576102): Pre-beta security review in prep for CCC beta1
* [#3577427](https://git.drupalcode.org/project/ai_context/-/work_items/3577427): Update context item revision diff feature for progressive enhancement
* [#3577644](https://git.drupalcode.org/project/ai_context/-/work_items/3577644): CCC beta1 release planning
* [#3577670](https://git.drupalcode.org/project/ai_context/-/work_items/3577670): CCC Chicago planning
* [#3579354](https://git.drupalcode.org/project/ai_context/-/work_items/3579354): Generate CCC beta1 release notes with contributing organizations and individuals
* [#3585902](https://git.drupalcode.org/project/ai_context/-/work_items/3585902): CCC beta2 release planning
* [#3586142](https://git.drupalcode.org/project/ai_context/-/work_items/3586142): Configure GitLab metadata for CCC
* [#3586189](https://git.drupalcode.org/project/ai_context/-/work_items/3586189): Stabilize global context item ordering before RC1
* [#3586193](https://git.drupalcode.org/project/ai_context/-/work_items/3586193): Test CCC on Drupal CMS 2.1
* [#3586194](https://git.drupalcode.org/project/ai_context/-/work_items/3586194): [Discuss] Conditional subcontext logic
* [#3586202](https://git.drupalcode.org/project/ai_context/-/work_items/3586202): CCC beta2 codebase review

## Additional Contributions

* Plan: 9
* Task: 38
* Support: 1
* Discuss: 0

## Contributors

**People:** kepol (98), scottfalconer (22), aidanfoster (14), danrod (12), bbruno (9), emma-horrell (9), erichomanchuk (7), mglaman (5), akhilbabu (5), annmarysruthy (5), marcus_johansson (5), robloach (4), dstorozhuk (3), a.dmitriiev (2), kostiantyn (2), hestenet (2), svendecabooter (2), guptahemant (1), ajv009 (1), abhisekmazumdar (1), drumm (1), wouters_frederik (1), alexua (1), andypost (1), axioteo (1), b_sharpe (1), cmlara (1), darrenoh (1), jibran (1), joshua1234511 (1), jrockowitz (1), nexusnovaz (1), rajabnatshah (1), ronaldtebrake (1), smustgrave (1), ultimike (1), unqunq (1), awojcik1107 (1), hrishikesh-dalal (1), jessehs (1), michele.r (1), naveen.prakash.work (1), root_emarketing (1)

**Organizations:** itty bitty byte (98), salsa digital (98), acquia (27), foster interactive inc. (20), optasy (12), qed42 (11), 1xinternet (11), the university of edinburgh (9), freelygive (6), drupal ukraine community (5), itech4web (5), kalamuna (4), dropsolid (2), dynamate (2), sven decabooter (2), drupal association (2), morpht (1), open social (1), imagex (1), digitaltrotter (1), e-sepia web innovation (1), zoocha (1), the big blue house (1), webform module open collective (1), zivtech (1), axelerant (1), mobomo (1), dm13 security llc (1), skilld (1), drupaleasy (1), drupal forge (1), vardot (1)
