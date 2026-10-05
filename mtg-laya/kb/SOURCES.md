# Sources and attribution

Everything in `kb/` is free, publicly published material, kept with its origin and used as a
knowledge base for decision-making. Nothing here is redistributed commercially.

## Strategy corpus — `kb/level_one/`

**Level One** by Reid Duke — the complete strategy course published by Wizards of the Coast on
magic.wizards.com, 2014–2015. 46 articles, free to read, ordered by the author as a curriculum.
Syllabus page: <https://magic.wizards.com/en/news/feature/level-one-full-course-2015-10-05>

The decision-relevant articles for this project:

| article | why it matters here |
|---|---|
| Attacking and Blocking | the combat rules: attack when you can, block when you can, and the exceptions |
| Tempo / Tempo & Card Advantage | what spending less mana than the opponent is worth |
| Role Assignment | "who's the beatdown" — whether to attack or defend at all |
| Damage Racing | when to race, when to stem the bleeding, when a chump block is correct |
| Playing From Ahead, Playing From Behind | how the correct play flips with the score |
| Playing Safe and Playing Scared | risk calibration |
| Mulligans / Mulligans III | opening-hand decisions |
| Sequencing | order of operations |
| Building a Mana Base | land counts and colour requirements |

## Supplementary essays

| file | source |
|---|---|
| `X-whos-the-beatdown.md` | Mike Flores, "Who's The Beatdown?" (1999), StarCityGames — the canonical role-assignment essay |
| `X-eight-core-principles-of-whos-the-beatdown.md` | StarCityGames, "Eight Core Principles of Who's The Beatdown?" |

## Card data — `kb/cards/` (not committed; regenerate with the command below)

**Scryfall bulk data**, free, updated every 12 hours, no API key required.
`oracle_cards` — one JSON object per Oracle ID, 38,706 cards with full rules text (24 MB gzipped
JSONL). Docs: <https://scryfall.com/docs/api/bulk-data>

```bash
curl -s https://api.scryfall.com/bulk-data \
  | python -c "import json,sys; print([b['jsonl_download_uri'] for b in json.load(sys.stdin)['data'] if b['type']=='oracle_cards'][0])" \
  | xargs -I{} curl -sL {} -o kb/cards/oracle-cards.jsonl.gz
```

## The file written for this project

`HOW_TO_PLAY.md` — the decision knowledge base. Part 1 is the fundamentals distilled from
Level One; Part 2 is **how to read a card** (threat assessment: evasion hierarchy, what each
ability changes about your decisions, removal targeting priority); Part 3 is the combat
decision rules; Part 4 is the checklist to run before each decision.

Written because card *text* is not card *threat*: a 3/3 trample is blockable by anything, while
a 2/1 flying is unblockable without a flyer — same-ish stats, opposite removal priority. The
guide is what turns a card's text into a decision.
