# Poper: Bounty Hunter Hold'em — Game Bible
**Version 0.2 | Working Document**

---

## 1. Overview

**Title:** Poper: Bounty Hunter Hold'em
**Genre:** Online multiplayer card game (poker-adjacent)
**Platform Target:** PC (primary), Web (secondary)
**Player Count:** 2–8 players (online multiplayer)
**Core Loop:** Players are dealt a hand of weapon, item, and infusion cards, then bet across five reveal rounds as a shared Bounty and its modifiers are unveiled. At showdown, damage is calculated and the highest damage wins the pot.

The name "Poper" is a playtest nickname (slip of the tongue) — consider it a working title that may become the official brand.

---

## 2. Design Pillars

1. **Strategy through imperfect information.** Like poker, players never know how strong their hand is until the board develops. The Bounty's type, terrain, and mods are revealed incrementally, so hand value shifts round by round.
2. **Shared risk, individual identity.** Every player fights the same Bounty — but their weapon type, infusion, and class determine how well they match up.
3. **Accessible depth.** The damage formula is simple enough to mentally estimate, but edge cases (resistance cancellation, Bounty Mod stacking, the 25% resistance drop) reward experienced players.

---

## 3. Core Concepts & Terminology

| Term | Definition |
|---|---|
| Bounty | The shared enemy revealed each hand. Has one base Infusion Vulnerability and one Infusion Resistance. The Terrain card adds a second Vulnerability. |
| Infusion | An elemental damage type applied via cards or consumables. Types: Electric, Fire, Ice, Holy, Evil, Acid, Sonic. |
| Weapon Card | The primary damage-dealing card. Deals one or two physical damage types. |
| Item Card | Flat bonus damage card. Adds to base damage of a specific physical damage type. |
| Infusion Card | Grants the player an elemental infusion type. |
| Class Card | Chosen at game start. Defines a player's base weapon damage output per level (LV). Starting LV is 1. |
| Bounty Mod | A modifier card that buffs or debuffs a specific physical damage type for all players. Three are revealed per hand. |
| Terrain Card | Revealed in Round 4. Adds a second Infusion Vulnerability to the Bounty. |
| Wager Pot | The shared pool of coins players bet into each round. |
| CP | Coin Points — the currency unit. 1 copper = 1cp, 1 silver = 5cp, 1 gold = 10cp. |

---

## 4. Card Types Reference

### 4.1 Physical Damage Types
Constricting, Slashing, Blunt, Piercing, Magic

### 4.2 Infusion Types
Electric, Fire, Ice, Holy, Evil, Acid, Sonic

### 4.3 Bounties (7 total)

| Bounty | Vulnerable To | Resistant To |
|---|---|---|
| Beast | Sonic | Ice |
| Serpent | Fire | Acid |
| Giant Flytrap | Acid | Electric |
| Dragon | Ice | Fire |
| Angel | Evil | Holy |
| Demon | Holy | Evil |
| Construct | Electric | Sonic |

The Bounty card defines one Vulnerability and one Resistance. The Terrain card (Round 4) provides the second Vulnerability.

### 4.4 Terrain Cards (7 total)
Each terrain grants the Bounty a second Vulnerability:

| Terrain | Adds Vulnerability |
|---|---|
| Cave | Sonic |
| Tundra | Fire |
| Forest | Acid |
| Mountain | Ice |
| Sacred Ground | Evil |
| Cemetery | Holy |
| Grasslands | Electric |

### 4.5 Bounty Mods (12 total)
Three categories of prefix/suffix combos:
- **Vulnerable to [Damage Type]** — increases damage dealt by all cards of that type by +1 (appears twice per type in the deck)
- **Deflects [Damage Type]** — decreases damage dealt by all cards of that type by −1

Physical damage types affected: Piercing, Blunt, Slashing, Constricting

> **Note:** The CSV uses the prefix "Weak to" — this should be renamed "Vulnerable to" in the final card data to match Terrain card language and avoid player-perspective ambiguity ("Weak to Slashing" reads as the player being weak, not the Bounty).

### 4.6 Weapons (20 total)
Weapons deal 3–6 base damage in one or two physical damage types.

| Tier | Weapons |
|---|---|
| Base (3 dmg) | Greatsword (slashing), Lance (piercing), Maul (blunt), Hand to Hand Grappling (constricting) |
| Mid+ (4 dmg) | Scimitar+, Bow and Arrow+, Net+, Mace+, and split-type combos (Sword and Board, Bola, Spear, Shortsword, Spiked Whip, Grappling Hook) |
| High+ (5–6 dmg) | Greatsword+, Lance+, Maul+, Hand to Hand Grappling+, Wand (magic 5), Staff (magic 6) |

### 4.7 Items (18 total)
Flat bonus damage in a physical type. Range: +1 to +3 per card.

| Item | Bonus |
|---|---|
| Rope / Net | +1 / +2 Constricting |
| Blades / Razors | +1 / +2 Slashing |
| Mallet / Hammer | +1 / +2 Blunt |
| Spikes / Caltrops | +1 / +2 Piercing |
| Spellscroll / Spellbook | +2 / +3 Magic |

### 4.8 Infusion Cards (21 total — 3 copies of each of 7 types)

| Card Name | Infusion Type |
|---|---|
| Shocking | Electric |
| Burning | Fire |
| Frozen | Ice |
| Divine | Holy |
| Diabolic | Evil |
| Corrosive | Acid |
| Thunderous | Sonic |

### 4.9 Classes

**Singleclasses (5 unique):**
| Class | Base Damage | Type |
|---|---|---|
| Wrangler | 2+LV | Constricting |
| Soldier | 2+LV | Slashing |
| Berserker | 2+LV | Blunt |
| Assassin | 2+LV | Piercing |
| Mage | 3+LV | Magic |

**Multiclasses (10 unique):**
All deal two damage types. One type deals 2+LV, the other deals 3+LV (the favored type).

| Class | Type 1 | Type 2 (favored, 3+LV) |
|---|---|---|
| Gladiator | Constricting | Slashing |
| Brawler | Constricting | Blunt |
| Spellbinder | Constricting | Magic |
| Rogue | Constricting | Piercing ★ |
| Warrior | Slashing | Blunt |
| Spellblade | Slashing | Magic ★ |
| Duelist | Slashing | Piercing |
| Battlemage | Blunt | Magic ★ |
| Mutilator | Blunt | Piercing |
| Shadowcaster | Piercing | Magic ★ |

★ = the 3+LV favored type for that class.

**Class Setup:** Players choose their Class Card before the first hand is dealt. The class does not change during a Classic game. Starting LV = 1. Leveling up is a Hunter mode mechanic (backlogged).

---

## 5. Rules Reference

### 5.1 Game Setup
1. Each player chooses a Class Card.
2. All players place an ante into the wager pot.
3. Each player is dealt a starting hand of four cards: one Weapon Card, one Item Card, one Infusion Card, and one randomly determined card (either another Infusion Card or another Item Card).

> **Open Issue:** When the random 4th card is dealt, what is the probability split? 50/50 between Item and Infusion, or weighted?

### 5.2 Round Order

| Round | Reveal | Notes |
|---|---|---|
| 1 | First Bounty Mod | Players bet based on starting hand + Mod |
| 2 | The Bounty | Reveals 1 Vulnerability and 1 Resistance |
| 3 | Second Bounty Mod | 25% chance the Bounty's Resistance is dropped this round |
| 4 | Terrain Card | Adds the Bounty's 2nd Vulnerability |
| 5 | Third Bounty Mod | Final adjustment before showdown |

**Resistance Drop:** At the start of Round 3, a 25% chance roll determines whether the Bounty loses its Resistance for this hand. The result is announced publicly before betting begins.

> **Open Issue:** Betting order is not defined. A dealer button or equivalent needs to be established, with turn order rotating clockwise each hand.

> **Open Issue:** No rule defines what happens when a player goes all-in for less than the current bet.

### 5.3 Betting Actions

| Action | Effect |
|---|---|
| Call | Match current bet |
| Raise | Increase current bet |
| Check | No change (0 added to pot) |
| Fold | Forfeit hand |
| All-In | Commit all remaining coins; may create side pot |

**Betting Limit:** Max bet = 10cp OR the current pot size, whichever is greater.

### 5.4 Damage Calculation

**Step 1 — Base Damage:**
- Start with Weapon Card damage + Class Card damage (at current LV)
- Add flat bonuses from Item Cards
- Apply Bounty Mod adjustments per matching damage type (stacks per card of that type in the hand)

**Step 2 — Infusion Multiplier:**
- Start at ×1.0
- +0.5 per Infusion in hand that matches a Bounty Vulnerability
- −0.5 per Infusion in hand that matches a Bounty Resistance
- Floor: ×0.5 (can never go below)
- If an Infusion type is both Vulnerable and Resistant for the same Bounty: effects cancel, treat as ×1

**Step 3 — Final Damage:**
`Final Damage = ceil(Base Damage × Infusion Multiplier)`

> **Open Issue:** Do duplicate Infusion cards of the same type each add +0.5 to the multiplier, or is the bonus capped at one application per unique type?

### 5.5 Winning
- Highest damage wins the entire pot.
- Tie: pot splits evenly.
- If all remaining players fold, the last player to have not folded wins the pot.

> **Open Issue:** Clarify whether a folded player can still win a side pot they were all-in for before folding.

---

## 6. Game Modes

### 6.1 Classic Mode ✅ (Vertical Slice Target)

| Setting | Value |
|---|---|
| Starting coins | 150cp (10×1cp, 12×5cp, 8×10cp) |
| Ante | 5cp per hand |
| Player deck | Reshuffled every hand |
| Bounty deck | Reshuffled every 6 hands |
| End condition | Indefinite — until players stop or one player holds all coins |

Classic is the primary target for the vertical slice. No shop, no consumables, no class leveling.

### 6.2 Hunter Mode 🔒 (Backlog)

A structured 5-hand mode with escalating antes, a shop between hands, consumables, and a trophy scoring system. Full details preserved in Section 8.

---

## 7. Vertical Slice Scope

### In (Classic, Online Multiplayer)
- Classic mode, fully playable online with 2–8 players
- Lobby creation and joining via room code
- Full card sets: weapons, items, infusions, bounties, terrains, Bounty Mods
- All five betting rounds with full betting actions (call, raise, check, fold, all-in)
- Automated damage calculation and showdown reveal
- Side pot support for all-in scenarios
- Persistent save file: wins, losses, total coin earned, player level, XP
- Basic player level system (XP from playing/winning) — infrastructure only, cosmetics are backlog
- Functional UI — card display, pot display, coin counts, round indicator

### Out (Backlog)
- Hunter mode and all its systems (shop, consumables, class leveling, trophies, stipend)
- Consumable card types: Potions, Infused Objects, Feints, Traps, Null Runes
- In-game class leveling
- Divergent Training / Multiclassing
- Cosmetics (card backs, avatars, table skins)
- Spectator mode, replays, tournaments, ranked matchmaking, mobile

---

## 8. Backlog: Hunter Mode (Full Design)

### 8.1 Structure
- 5 hands total
- Ante = 5cp × hand number (5, 10, 15, 20, 25cp)
- Starting coins: 25cp
- Stipend before each hand = 25cp × hand number
- Player coin totals are hidden from opponents

### 8.2 Scoring
- Win a hand → win the pot + a Bounty Trophy (25 points)
- Tie → Bounty Trophy liquidated into 25cp, split
- Most points after 5 hands wins

### 8.3 Shop (between hands)
- Deals 3 random consumable cards from the pool
- Max 2 consumables purchased per shop visit
- Class upgrade: 5cp × (upgrades + 1) for singleclass; 10cp × (upgrades + 1) for multiclass

### 8.4 Consumable Types

| Type | Cost | Effect |
|---|---|---|
| Potion | 10cp | Adds flat physical damage of a specific type |
| Infused Object | 25cp | Grants an infusion type |
| Feint | 5cp | Fake card — must be discarded at next shop visit |
| Trap | 5cp | Reduces a specific physical damage type by 1 per card for all opponents |
| Null Rune | 15cp | Adds a Resistance to the Bounty for a specific infusion type |

> **Design Note (Feints):** Feint behavior needs further definition — does the opponent see the card's name when it's played? Is it revealed only when discarded at the shop?

### 8.5 Hunter Actions (in-hand)
- **Buy a Card:** Once per hand, before acting in a round. Cost = 2cp × current round. Discard one Item Card, draw a new one.
- **Declare Consumables:** When the Bounty is revealed (Round 2), publicly declare count of consumables being used. Max 2 per hand.

---

## 9. Persistent Save System

Applies to all game modes. Local save for the vertical slice; cloud save is backlog.

| Field | Type | Notes |
|---|---|---|
| player_name | string | Set on first launch |
| player_level | int | XP-based, gates cosmetics |
| total_xp | int | +10 per hand played, +25 bonus per hand won |
| total_wins | int | Hands won |
| total_hands | int | Hands played |
| total_coins_earned | int | Lifetime coins won |
| cosmetics_unlocked | array | IDs of unlocked cosmetic items |

Build the XP/level infrastructure in the vertical slice so progression carries forward when cosmetics are added.

---

## 10. Open Issues

Issues still requiring a ruling:

1. **4th card probability** — 50/50 Item vs Infusion, or weighted?
2. **Infusion stacking** — Do duplicate Infusion cards of the same type each contribute +0.5 to the multiplier?
3. **Betting order** — Define dealer button, clockwise turn order, and under-bet all-in handling.
4. **Side pot + fold edge case** — Can a player who folded still win a side pot they were previously all-in for?

---

## 11. Data Notes (CSV Files)

Duplicate rows in the CSVs are intentional — they represent card copies for deck density (e.g., 3 copies of each infusion type = 21 infusion card rows). When loading card data, de-duplicate by unique card identity; the copy count determines how many go in the deck.

`training.csv` is a placeholder — all 39 rows are identical. Real training card data is needed before Hunter mode development begins.

`feints.csv` has 16 identical rows with no description beyond "fake card." Feint design needs finalization before Hunter mode.

---

*End of Game Bible v0.2*
