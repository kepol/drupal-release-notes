# 1.0.0-alpha through 1.0.0-beta1

**144 credited issues**

This release (1.0.0-alpha through 1.0.0-beta1) includes 144 credited issues. It includes 36 new features, 22 bug fixes, 31 other major contributions, 55 additional contributions.

_Generated 2026-07-05T00:15:30.323038+00:00_

## New Features (36)

* [#3547033](https://git.drupalcode.org/project/ai_context/-/work_items/3547033): AI CCC markdown editor integration
* [#3547034](https://git.drupalcode.org/project/ai_context/-/work_items/3547034): [Spike] Research URL support for CCC
* [#3547035](https://git.drupalcode.org/project/ai_context/-/work_items/3547035): [Spike] Research PDF upload support for CCC
* [#3547050](https://git.drupalcode.org/project/ai_context/-/work_items/3547050): Add text filtering on AI CCC context agents page
* [#3549082](https://git.drupalcode.org/project/ai_context/-/work_items/3549082): Within the Context Pools UI, link the Context for the forms to see the details of each context
* [#3550034](https://git.drupalcode.org/project/ai_context/-/work_items/3550034): Add AI context item usage data and page
* [#3555225](https://git.drupalcode.org/project/ai_context/-/work_items/3555225): Add a single global context, making Vienna Driesnote AI demos much simpler
* [#3556909](https://git.drupalcode.org/project/ai_context/-/work_items/3556909): [Discuss] Decouple AI Context from AI Agents
* [#3559384](https://git.drupalcode.org/project/ai_context/-/work_items/3559384): Add multilingual support to CCC
* [#3563049](https://git.drupalcode.org/project/ai_context/-/work_items/3563049): Add draft support to CCC
* [#3563052](https://git.drupalcode.org/project/ai_context/-/work_items/3563052): Add revision support to CCC
* [#3563089](https://git.drupalcode.org/project/ai_context/-/work_items/3563089): Add revision comparison diff support for context item revisions
* [#3563357](https://git.drupalcode.org/project/ai_context/-/work_items/3563357): Add duplicate context item feature like Drupal CMS has for nodes
* [#3563360](https://git.drupalcode.org/project/ai_context/-/work_items/3563360): Add scheduling options for context items like nodes
* [#3563361](https://git.drupalcode.org/project/ai_context/-/work_items/3563361): Add moderation workflow support for context items like nodes
* [#3563362](https://git.drupalcode.org/project/ai_context/-/work_items/3563362): Add toolbar dropdown menu for context items like nodes
* [#3563365](https://git.drupalcode.org/project/ai_context/-/work_items/3563365): Add tagify styling to taxonomy fields for CCC
* [#3563371](https://git.drupalcode.org/project/ai_context/-/work_items/3563371): Switch context items page to use a view
* [#3564653](https://git.drupalcode.org/project/ai_context/-/work_items/3564653): Create CCC moderation workflow and scheduling local tasks
* [#3564706](https://git.drupalcode.org/project/ai_context/-/work_items/3564706): [Meta] Context Scope feature
* [#3564714](https://git.drupalcode.org/project/ai_context/-/work_items/3564714): Allow context scoped to entities in CCC
* [#3566852](https://git.drupalcode.org/project/ai_context/-/work_items/3566852): Add CCC overview page
* [#3567791](https://git.drupalcode.org/project/ai_context/-/work_items/3567791): [Spike] CCC MCP server integration PoC
* [#3568673](https://git.drupalcode.org/project/ai_context/-/work_items/3568673): Add context scope base code and use case context scope plugin
* [#3568674](https://git.drupalcode.org/project/ai_context/-/work_items/3568674): Switch context tags to be a context scope plugin
* [#3568676](https://git.drupalcode.org/project/ai_context/-/work_items/3568676): Add site section context scope for MVP
* [#3568677](https://git.drupalcode.org/project/ai_context/-/work_items/3568677): Allow agents to subscribe to context scope
* [#3569311](https://git.drupalcode.org/project/ai_context/-/work_items/3569311): [Meta] Subcontext feature in CCC
* [#3569313](https://git.drupalcode.org/project/ai_context/-/work_items/3569313): Create design for context list UI to include subcontext
* [#3570933](https://git.drupalcode.org/project/ai_context/-/work_items/3570933): Add language context scope for MVP
* [#3570940](https://git.drupalcode.org/project/ai_context/-/work_items/3570940): Convert global option to context scope plugin
* [#3571788](https://git.drupalcode.org/project/ai_context/-/work_items/3571788): Update subcontext feature to specify required vs conditional selection
* [#3571909](https://git.drupalcode.org/project/ai_context/-/work_items/3571909): Update context selection logic to handle subcontext
* [#3572160](https://git.drupalcode.org/project/ai_context/-/work_items/3572160): Switch target entities to be a context scope plugin
* [#3575590](https://git.drupalcode.org/project/ai_context/-/work_items/3575590): Add ai_agents_debugger debug and ai_agents_explorer explore operations and links in CCC
* [#3575595](https://git.drupalcode.org/project/ai_context/-/work_items/3575595): Format context item markdown on view page

## Bug Fixes (22)

* [#3547892](https://git.drupalcode.org/project/ai_context/-/work_items/3547892): CCC Function Call should load ContextDefinitionNormalizer via Dependency Injection
* [#3549748](https://git.drupalcode.org/project/ai_context/-/work_items/3549748): The max tokens calculation is hardcoded + use tokenizer for AI CCC
* [#3549752](https://git.drupalcode.org/project/ai_context/-/work_items/3549752): The selector service does not use the maxOverride at all for AI CCC
* [#3550895](https://git.drupalcode.org/project/ai_context/-/work_items/3550895): CCC tags should be required
* [#3552972](https://git.drupalcode.org/project/ai_context/-/work_items/3552972): Wrong dependency definition in info.yml causes composer to not install
* [#3554221](https://git.drupalcode.org/project/ai_context/-/work_items/3554221): Setting context pools acts differently between agent form and context pool form
* [#3554277](https://git.drupalcode.org/project/ai_context/-/work_items/3554277): ai_context_ai_function_call_info_alter does not work with contexts only set via "always_include"
* [#3554616](https://git.drupalcode.org/project/ai_context/-/work_items/3554616): Setting AI contexts has no effect on some agents
* [#3568115](https://git.drupalcode.org/project/ai_context/-/work_items/3568115): New context items do not default to published when setting is chosen
* [#3568177](https://git.drupalcode.org/project/ai_context/-/work_items/3568177): Error when reinstalling after creating CCC taxonomy terms
* [#3571006](https://git.drupalcode.org/project/ai_context/-/work_items/3571006): Clean up CCC install process and composer.json file
* [#3571188](https://git.drupalcode.org/project/ai_context/-/work_items/3571188): Error on installation: The state 'draft' already exists in workflow
* [#3571195](https://git.drupalcode.org/project/ai_context/-/work_items/3571195): Schema errors from scheduler after installing CCC
* [#3571392](https://git.drupalcode.org/project/ai_context/-/work_items/3571392): Toolbar menu issue in Drupal 11.3 when CCC installed
* [#3577512](https://git.drupalcode.org/project/ai_context/-/work_items/3577512): Duplicate Revisions tabs appear when editing an AI Context Item.
* [#3577745](https://git.drupalcode.org/project/ai_context/-/work_items/3577745): Context item revision comparison is missing some scope info
* [#3578114](https://git.drupalcode.org/project/ai_context/-/work_items/3578114): Update context scope plugin manage link/url/route functionality
* [#3578386](https://git.drupalcode.org/project/ai_context/-/work_items/3578386): Multiple entities can be set on the target entity reference autocomplete field but only 1 is saved
* [#3578657](https://git.drupalcode.org/project/ai_context/-/work_items/3578657): Drupal 10: Error on /admin/ai/context/items/add: scheduler_content_moderation_integration module conflict
* [#3579394](https://git.drupalcode.org/project/ai_context/-/work_items/3579394): CCC icon doesn't show in vanilla Drupal 10 and Drupal 11 install
* [#3579396](https://git.drupalcode.org/project/ai_context/-/work_items/3579396): CCC target entity types settings not working
* [#3579841](https://git.drupalcode.org/project/ai_context/-/work_items/3579841): Can't Apply Scheduler Patch

## Other Major Contributions (31)

* [#3545824](https://git.drupalcode.org/project/ai_context/-/work_items/3545824): Create demo Context Control Center for Vienna 2025
* [#3558814](https://git.drupalcode.org/project/ai_context/-/work_items/3558814): [Spike] CCC 1.0 brainstorming
* [#3559379](https://git.drupalcode.org/project/ai_context/-/work_items/3559379): [Meta] CCC rearchitecture and roadmap
* [#3563000](https://git.drupalcode.org/project/ai_context/-/work_items/3563000): Switch the AiContext config entity to a content entity
* [#3563008](https://git.drupalcode.org/project/ai_context/-/work_items/3563008): Tag ai_context for v2025 repo before rearchitecture
* [#3564709](https://git.drupalcode.org/project/ai_context/-/work_items/3564709): Switch global context to checkbox on context items
* [#3566811](https://git.drupalcode.org/project/ai_context/-/work_items/3566811): Add AI usage to CCC issue template
* [#3566842](https://git.drupalcode.org/project/ai_context/-/work_items/3566842): [META] Add overviews, better descriptions, and help text in CCC for better UX
* [#3567570](https://git.drupalcode.org/project/ai_context/-/work_items/3567570): [Meta] Context Control Center MVP demo
* [#3567571](https://git.drupalcode.org/project/ai_context/-/work_items/3567571): CCC MVP Demo: Create draft FinDrop context
* [#3569514](https://git.drupalcode.org/project/ai_context/-/work_items/3569514): [Spike] Research what Google Analytics data can be used in CCC
* [#3569776](https://git.drupalcode.org/project/ai_context/-/work_items/3569776): Adopt AI Core shared UI library in CCC and escape data before rendering
* [#3569967](https://git.drupalcode.org/project/ai_context/-/work_items/3569967): [Discuss] Figure out which CCC features can be optional for MVP
* [#3571299](https://git.drupalcode.org/project/ai_context/-/work_items/3571299): Add D11 CCC install steps on the project page
* [#3571393](https://git.drupalcode.org/project/ai_context/-/work_items/3571393): Add GitLab CI linting to CCC project
* [#3571794](https://git.drupalcode.org/project/ai_context/-/work_items/3571794): Update context list UI to include subcontext and scope
* [#3573713](https://git.drupalcode.org/project/ai_context/-/work_items/3573713): Full architecture review of CCC in prep for 1.0
* [#3573717](https://git.drupalcode.org/project/ai_context/-/work_items/3573717): Add automated testing to CCC in prep for 1.0
* [#3574359](https://git.drupalcode.org/project/ai_context/-/work_items/3574359): Refactor context selection logic
* [#3574420](https://git.drupalcode.org/project/ai_context/-/work_items/3574420): Add Drupal CMS 2.0 support to CCC
* [#3574445](https://git.drupalcode.org/project/ai_context/-/work_items/3574445): Add Drupal CMS 2.0 CCC install steps on the project page
* [#3574906](https://git.drupalcode.org/project/ai_context/-/work_items/3574906): CCC: Refactor to move key form validations into entity-level validators / presave
* [#3574908](https://git.drupalcode.org/project/ai_context/-/work_items/3574908): CCC: Refactor to convert entity HTML helpers to data-only methods and render arrays
* [#3574936](https://git.drupalcode.org/project/ai_context/-/work_items/3574936): Add search or filters to context listing
* [#3576089](https://git.drupalcode.org/project/ai_context/-/work_items/3576089): Remove support for D10 for CCC
* [#3576102](https://git.drupalcode.org/project/ai_context/-/work_items/3576102): Pre-beta security review in prep for CCC beta1
* [#3577087](https://git.drupalcode.org/project/ai_context/-/work_items/3577087): CCC MVP Demo: Finalize FinDrop context
* [#3577427](https://git.drupalcode.org/project/ai_context/-/work_items/3577427): Update context item revision diff feature for progressive enhancement
* [#3577644](https://git.drupalcode.org/project/ai_context/-/work_items/3577644): CCC beta1 release planning
* [#3577670](https://git.drupalcode.org/project/ai_context/-/work_items/3577670): CCC Chicago planning
* [#3579857](https://git.drupalcode.org/project/ai_context/-/work_items/3579857): CCC beta1 features list and blurbs for demos and promotions

## Additional Contributions

* Plan: 5
* Task: 50
* Support: 0
* Discuss: 0

## Contributors

**People:** kepol (135), aidanfoster (22), marcus_johansson (20), scottfalconer (18), bbruno (13), emma-horrell (12), dstorozhuk (10), ahmedj (9), danrod (9), erichomanchuk (7), tedbow (7), robloach (6), svendecabooter (6), yautja_cetanu (4), annmarysruthy (4), kostiantyn (3), b_sharpe (3), kafmil (2), mandclu (2), a.dmitriiev (2), breidert (2), guptahemant (2), rakhimandhania (2), axioteo (2), tonypaulbarker (2), unqunq (2), divyamdotfoo (2), hrishikesh-dalal (2), nickolaj (2), thamas (1), akhilbabu (1), ahmad-khader (1), rajabnatshah (1), abhisekmazumdar (1), fjgarlin (1), gantal (1), harivansh (1), jurgenhaas (1), nexusnovaz (1), nikro (1), shamir.vs (1), webbywe (1), ajv009 (1), horvan (1), kumarimedha09 (1), naveen.prakash.work (1), root_emarketing (1), roromedia (1), sujal_31 (1), twiesing (1)

**Organizations:** salsa digital (142), itty bitty byte (135), foster interactive inc. (28), acquia (27), freelygive (21), 1xinternet (17), the university of edinburgh (12), itech4web (12), drupal ukraine community (12), optasy (9), qed42 (8), kalamuna (6), dynamate (6), sven decabooter (6), imagex (3), digitaltrotter (2), vardot (2), entityone (2), annertech (2), localgov drupal (2), e-sepia web innovation (2), civicactions (1), drupalfit (1), opensense labs (1), lakedrops (1), zyxware technologies (1), dropsolid (1), elevated third (1), drupal association (1), zoocha (1)
