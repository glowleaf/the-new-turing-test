# How to play Magic: The Gathering — a decision knowledge base

Written for a model that has to choose between plays. Two halves: **how the game is won**
(fundamentals, from Reid Duke's *Level One*) and **how to read a card** (threat assessment —
what makes a card dangerous, and therefore what to kill, block, or race).

Sources and attribution: `kb/SOURCES.md`. Full article corpus: `kb/level_one/`.

---

## Part 1 — The five things that decide games

1. **Mana** is the resource that gates everything. A card you can't cast is not a card.
   Untapped lands are options; tapped lands are not. Playing a land every turn is nearly
   always right, and holding mana up is a real cost paid for a real option.
2. **Card advantage**: a card that answers two of theirs is worth more than one that answers
   one. Trading one-for-one is fine; trading one-for-none loses. Board sweepers are the
   biggest card-advantage swings in the game.
3. **Tempo**: spending less mana than the opponent for the same effect. A one-mana answer to
   a four-mana threat is a two-turn head start. Tempo and card advantage trade against each
   other — you cannot always have both.
4. **Who's the beatdown?** (Mike Flores, 1999) In every game one player should be attacking
   and the other defending. Get this wrong and you lose games you should win: the control
   player who attacks, or the aggro player who blocks, is playing the opponent's game.
   - The player with **inevitability** (the deck that wins if the game goes long) must NOT be
     the beatdown. The other player must.
   - Role is **fluid** — it can flip when the draw changes. Re-ask the question each turn.
   - Ties break on: who goes first, who has the faster draw, life totals, and who has the
     better late game.
5. **Damage racing**: when neither player can take control, the game becomes a race. Life
   totals change value over time — 5 life on turn 3 is a resource, 5 life on turn 12 is
   nothing. **Behind on the race, stem the bleeding (block, trade, remove) before racing
   back.** Ahead on the race, press — every point of damage shortens their clock.

---

## Part 2 — How to read a card (threat assessment)

**Stats alone do not tell you how dangerous a card is.** Power and toughness say what happens
in combat *if combat happens*. Abilities say whether combat happens at all, and whether your
answers work. Read abilities first, then stats.

### The evasion hierarchy — who actually threatens your life total

| ability | can it be blocked? | threat level |
|---|---|---|
| **flying** | only by flying or reach | **highest** — usually unblockable in practice |
| **menace** | needs two blockers | high — most decks can't spare two |
| **fear / intimidate / unblockable** | only by specific colours | high |
| **trample** | yes, and a chump blocker still absorbs its toughness | **moderate** — overflow damage only |
| **deathtouch** | yes, but any block trades | high on defence, not evasion |
| no ability | yes, by anything | low |

**Worked example (the classic trap):** a **3/3 with trample** versus a **2/1 with flying**.
- The 3/3 trample is blockable by any 1/1. A single chump blocker eats 3 damage and the
  trample player gets nothing. It cannot win the game through a board.
- The 2/1 flying is **unblockable** unless you have a flyer. It deals 2 every turn regardless
  of your ground defence. Left alone it kills from 20 in ten turns and there is nothing your
  ground creatures can do about it.

**So the 2/1 flyer is the more dangerous card, and it is the correct target for removal** —
even though it has smaller stats. The rule generalises: **remove the creature that beats your
defence, not the creature with the biggest numbers.** The biggest creature you can block is
often the one you should ignore.

### Ability-by-ability: what each one changes about your decisions

- **Flying / reach** — flying is evasion; reach is the answer to it. If they have flyers and
  you don't, you are on a clock and must race or remove.
- **Trample** — damage overflows past blockers. Matters only when the blocker is smaller than
  the attacker's power; a chump block still stops most of it.
- **Deathtouch** — any amount of damage is lethal, so a 1/1 deathtouch trades with your 8/8.
  Never block it with something you care about; it turns every blocker into a trade.
- **First strike / double strike** — wins combat against equal stats and survives. A 2/2
  first strike beats a 2/2, and beats a 3/3 by killing it before damage back.
- **Lifelink** — changes the race maths twice (their life up, your clock longer). A lifelinker
  you can't block is often the single most important thing on the board.
- **Haste** — attacks the turn it lands, so sorcery-speed answers are too late.
- **Flash** — played on your turn to ambush a blocker or a removal spell; breaks your combat
  maths because it was not on the board when you attacked.
- **Vigilance** — attacks *and* blocks: it provides two turns of value per turn. Undervalued.
- **Hexproof / ward / protection** — your removal may not legally target it. Do not plan a
  removal spell for a hexproof creature; plan a blocker, a sweeper, or a race instead.
- **Indestructible** — "destroy" does nothing. Only exile, -X/-X, sacrifice, or bounce work.
- **Enter-the-battlefield triggers** — the value already happened. Killing it afterwards
  trades your card for their trigger, which is usually a losing exchange.
- **Activated abilities that grow** (pump, +1/+1 counters, "whenever you cast") — the threat
  compounds each turn. These move up the removal priority list fast.
- **Planeswalkers** — repeatable advantage every turn, and they protect themselves. Kill them
  or attack them before they take over; ignoring one is rarely right.

### Removal targeting priority — the order to ask

1. **Can I race it?** If the creature can't profitably attack (it's blockable and small),
   leave it. Removal is a scarce resource; spend it on problems.
2. **Can I block it?** If a blocker answers it, the blocker is the answer. Don't spend removal
   on something your board already handles.
3. **Can it win the game alone?** Evasive + evasive-lifelink + growing + planeswalker = yes.
   That is the target.
4. **Does my removal even work?** Hexproof, indestructible, ward — check before planning.
5. **What is the exchange?** Two-mana removal on a six-mana threat is a win. Premium removal
   on a one-mana creature is usually a loss.

**The single sentence to remember:** *remove the creature that beats your defence, and block
the creature that doesn't.*

---

## Part 3 — Combat decisions

From *Attacking and Blocking*: **"you should usually attack if you can and usually block if
you can."** Being passive in combat is the most common beginner error — a creature that
neither attacks nor blocks has wasted a turn of value. But "usually" is doing work, and the
exceptions are what separate good players:

**Attack when:**
- the attack is lethal, or the creature is unblocked (free damage, no downside);
- you can make a favourable trade (your power kills theirs and theirs doesn't kill yours);
- you are the beatdown and the race is the game — every point of damage matters;
- your creature's death is acceptable because the opponent must block badly to do it.

**Hold back when:**
- the blocker kills your attacker and survives — you lose a creature for zero damage;
- you are behind on the race and need the creature to block next turn;
- the creature has a valuable future (a mana creature, a growing threat) and chumping now
  wastes it.

**Block when:**
- it is an even trade or better — you kill their creature and save damage;
- the incoming damage is lethal — a chump block is correct precisely then;
- you are the control player and every turn you survive is a turn closer to your win.

**Don't block when:**
- it is an early chump block. *"There's often little point to chump blocking early"* — the
  blocker still has work to do (casting your bigger spells, trading later for more). Chump
  blocks are a **late-game** tool, used when the damage is about to kill you and the blocker
  has no future anyway.
- the attacker is small and you can take the damage — life is a resource, and 3 damage now
  is often cheaper than losing the blocker forever.

---

## Part 4 — The questions to ask before every decision

1. **Who's the beatdown?** Am I the aggressor or the defender *right now*?
2. **What is my clock, and what is theirs?** Turns to kill, both directions.
3. **What card in their hand beats me?** Play around the likeliest one, not the scariest one.
4. **What does this play cost me if it goes wrong?** A creature is a real cost; a life point
   usually is not.
5. **If I do nothing, what happens?** Sometimes the answer is "nothing bad" — but often the
   answer is "I fall further behind," and that is what passivity costs.
6. **What is the exchange?** Cards, mana, tempo, life — name the currency before spending it.
