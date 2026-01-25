# Arkham Horror LCG: Strategic Doctrine and Deckbuilding Logic for Decision Support Systems

## 1. Foundational Doctrine and System Architecture
The effective construction of investigator decks within Arkham Horror: The Card Game (AH:LCG) necessitates a shift from intuitive selection to rigorous probabilistic management. This document establishes the foundational doctrine for an AI-driven decision support system designed to optimize deck composition. The objective of deckbuilding in this system is not merely to assemble powerful cards, but to construct a reliable engine capable of mitigating the high variance inherent in the encounter deck and chaos token pulls. A deck must be viewed as a probabilistic machine where the inputs are actions and resources, and the outputs are scenario progress (clues) and stability (enemy management).
Successful deck construction relies on three pillars: Role, Foundation, and Economy.1 These pillars dictate that a deck must have a clearly defined problem-set it solves, a statistical baseline that leverages investigator strengths, and a solvency model that ensures assets can be played. The first doctrinal truth is that specific investigators dictate specific constraints; however, universal mathematical realities govern the game state across all classes.

### 1.1 The Economy of Actions and Resource Solvency
The fundamental currency of Arkham Horror is the Action. Each investigator is allotted three actions per turn. High-level play is defined by Action Compression—the ability to derive more than one unit of value from a single action.2 In a standard game state, one action equates to one resource or one card. Therefore, any card included in a deck must offer a return on investment (ROI) greater than this baseline to be considered efficient. For example, an event that costs 1 resource and 1 action to gain 2 clues effectively compresses two "Investigate" actions into one card play, yielding a net positive tempo.
The "Resource Curve" acts as the primary constraint on deck capability. A standard investigator generates one resource per turn during the upkeep phase. Over a typical 15-round scenario, an investigator has a natural baseline of roughly 15 to 20 resources. A deck requiring 30 or more resources to function without dedicated economy cards will inevitably stall, leading to a failure state known as "tempo lag," where the investigator must waste efficient actions clicking for resources. A functional resource equation for the decision support system is defined as: 10 + Resources Generated - Resources Spent = Low Positive Number.3 The constant "10" represents the resources available by Turn 5 (5 starting + 5 upkeep). If the cost of assets needed for critical setup exceeds this sum, the deck requires aggressive economy cards such as Emergency Cache or class-specific equivalents like Faustian Bargain.4
The implications of this curve are profound for asset density. A common error in decision logic is overloading a deck with high-cost assets (4+ resources). Without a matching influx of resource generation, these assets become "dead draws," occupying hand size without contributing to the board state. The AI system must evaluate the "Cost Curve" of a deck, prioritizing a distribution that allows for early-game deployment. For instance, a Guardian deck utilizing Lightning Gun (Cost 5) and Beat Cop (Cost 4) requires a significantly higher density of economy cards compared to a Survivor deck utilizing Fire Axe (Cost 1) and Cherished Keepsake (Cost 0).

### 1.2 Stochastic Analysis: The Chaos Bag and Skill Test Thresholds
The Chaos Bag serves as a variance generator that distinguishes AH:LCG from deterministic puzzles. Unlike dice, the probabilities change based on the scenario, the difficulty setting, and the remaining tokens in the bag. A deck must be built to withstand this variance, not just hope for positive outcomes.
The core metric for card evaluation is the ability to hit specific success thresholds. On Standard difficulty, the chaos bag typically contains tokens ranging from 0 to -4, with the highest concentration of probability mass around -1 and -2. Therefore, a skill value of +2 above the test difficulty is considered the doctrinal baseline for a "reliable" test, covering approximately 70-80% of the token distribution.6 For the decision support system, this means that if an investigator has a base Combat of 3 and intends to fight enemies with a Fight value of 3, the deck must provide static boosts (Assets) or temporary boosts (Skills/Events) to consistently reach a value of 5.
On Hard or Expert settings, the bag includes -5, -6, or even -8 tokens. The "reliable" threshold shifts to +4 above difficulty. This necessitates a shift in deck architecture from moderate boosting to massive stat alignment or "testless" actions—effects that guarantee damage or clues without drawing a token.7 The system must recognize that on Expert, the value of a +1 boost diminishes significantly compared to effects like "Discover 1 clue at your location" (e.g., Working a Hunch), which bypasses the chaos bag entirely.
Furthermore, the "Auto-Fail" token (the tentacle) represents a roughly 5-6% chance of failure regardless of skill value. High-level decks must incorporate mitigation for this inevitability. This can take the form of volume (taking enough tests that one failure does not end the campaign) or specific Survivor mechanics like Lucky! or Live and Learn that interact with the failure state itself.8 The doctrine dictates that no critical strategy should hinge on a single test without a contingency plan.

### 1.3 Slot Architecture and Asset Density
Investigators have limited slots: 1 Ally, 1 Body, 1 Accessory, 2 Hand, and 2 Arcane slots. The management of these slots is a critical variable in deck optimization.
Hand Slots are the most contested real estate. Guardians require them for weapons; Seekers for magnifying glasses or tomes. The system must flag conflicts, such as a deck including both Lightning Gun (2 hands) and Flashlight (1 hand) without a solution like Bandolier. The "Big Gun" archetype specifically requires Bandolier to function comfortably, allowing the investigator to hold a backup weapon or utility item while wielding a heavy firearm.9
The Ally Slot is statistically the most powerful slot due to the combination of static stat boosts and "soak" (damage/horror absorption). Allies like Dr. Milan Christopher or Leo De Luca define entire playstyles. The Charisma permanent talent, which grants an additional Ally slot, is frequently the highest-priority upgrade in the game because utilizing two allies simultaneously provides a force multiplier effect that few other upgrades can match.11
Asset vs. Event Ratio: A balanced starting deck often follows a 12 Asset / 10 Event / 8 Skill ratio, though this varies heavily by class.11 Assets provide long-term value but require upfront tempo cost (Action to play + Resource cost). Events provide immediate tempo (burst damage or clues) but are resource-neutral or negative in the long run. Skills are tempo-positive (costing 0 actions and 0 resources) but card-negative. The AI must balance these types to ensure the deck does not "stall" (too many assets, no money) or "burn out" (too many events, no board state).

### 1.4 The Mulligan Heuristic
The Mulligan phase is the first and most significant strategic decision of any scenario. The goal is to maximize the probability of finding critical "setup" assets. The decision support system must utilize hypergeometric probability to determine optimal mulligan strategies.
For most archetypes, players should discard any card that is not a critical setup piece. For a Guardian, this means throwing back decent events like Dodge or Vicious Blow to dig for a Weapon. For a Seeker, it means digging for Dr. Milan Christopher or Magnifying Glass. The math dictates that with 6 target cards in a deck and a "hard mulligan" (discarding all non-targets), the probability of starting with at least one target approaches 90%.13 Keeping a "mediocre" hand reduces the chance of finding the engine-enabling asset significantly. The system should recommend mulligan strategies based on the "Key Asset" tag assigned to specific cards within an archetype.

## 2. Class Doctrine: The Guardian
The Guardian class (Blue) fulfills the role of the primary combatant. In the division of labor, the Guardian is responsible for enemy management, ensuring that Seekers and other fragile classes can operate without threat. Their primary stats are Combat (Fight) and Willpower (Defense against the encounter deck). The core philosophy of the Guardian is Reliability. A Guardian does not "try" to fight; they must guarantee the kill. A failed attack action results in wasted resources, retained threat, and potential damage to the investigator, creating a negative feedback loop.

### 2.1 Weapon Density and Probability Models
A standard Guardian deck fails if it cannot kill an enemy the turn it spawns. Therefore, consistency in drawing a weapon is the single most important metric. A deck carrying only two weapons has a dangerously low probability of finding one in the opening hand (roughly 40-50% even with mulligan). The doctrine establishes a Weapon Density of 5-6 level 0 weapons as the standard.9 This density ensures that the Guardian can consistently perform their role from Turn 1.
The weapons themselves must be evaluated on Damage Compression. Weapons that deal +1 Damage (2 total) are the minimum standard for efficiency. A standard enemy has 2 or 3 health. A weapon dealing 1 damage requires 2 or 3 actions to kill it, consuming the Guardian's entire turn. A weapon dealing 2 damage (Machete, .45 Automatic) reduces this to 1 or 2 actions, effectively doubling the investigator's efficiency. Level 0 staples like Machete are highly valued because they provide this compression without consuming ammo resources, although they require careful engagement management.16

### 2.2 Archetype A: The "Big Gun" Specialist
This archetype focuses on high-XP, two-handed firearms to delete boss-level enemies and massive threats. The core cards include Lightning Gun, Flamethrower, and Shotgun. While these weapons offer immense power (3+ damage per shot), they suffer from two drawbacks: cost and ammo scarcity.
The "Stick to the Plan" Engine: The most defining upgrade for this archetype is Stick to the Plan. This permanent asset allows the player to search the deck for 3 tactic/supply events and attach them at the start of the game.10 This creates a deterministic opening. The doctrine mandates attaching:
Prepared for the Worst: To tutor the weapon immediately.
Emergency Cache: To generate the resources needed to pay for the expensive weapon.
Extra Ammunition / Custom Ammunition: To extend the weapon's lifespan.
This setup eliminates draw variance for the critical components of the build. The AI system should prioritize Stick to the Plan as the first XP purchase for any Guardian commander like Mark Harrigan or Zoey Samaras who intends to use firearms.
Support assets are also critical. Bandolier is required to free up a hand slot for utility items or a backup weapon. Venturer serves as a walking ammo cache, reloading the Flamethrower or Lightning Gun to prevent the Guardian from becoming useless once the chamber is empty.10

### 2.3 Archetype B: The Soak/Tank
This archetype utilizes the Guardian's high health and access to healing/mitigation to protect the team physically. Investigators like Tommy Muldoon or Mark Harrigan excel here.
Economy of Health: In this doctrine, Health and Sanity are viewed as resources to be spent. The "Soak" archetype uses assets like Leather Coat, Cherished Keepsake, and allies like Beat Cop (2) or Brother Xavier to absorb hits. This preserves the investigator's actual health pool while triggering abilities. Mark Harrigan, for instance, uses damage as a card draw mechanism (via his Sophie asset), requiring a deck rich in healing (Emergency Aid) and soak assets to fuel his engine without dying.18
Recursion Mechanics: Tommy Muldoon introduces a recursion loop where assets that are defeated by damage are shuffled back into the deck, granting resources. This converts incoming damage into economy, flipping the traditional attrition model. A deck built for Tommy must prioritize assets with health/sanity values rather than events, maximizing the fuel for his ability.

### 2.4 Investigator Specifics and Nuance
Roland Banks: As a hybrid Guardian/Seeker, Roland requires a different balance. His ability generates clues upon killing enemies. His deck should lean into "Testless Clues" (Evidence!, Scene of the Crime) rather than raw Intellect boosting, as his 3 Intellect is often insufficient for high-shroud locations on Hard difficulty. He benefits from Alice Luxley or Grete Wagner who support both fighting and cluing.1
Zoey Samaras: Zoey generates resources by engaging enemies. This "Bounty Hunter" economy allows her to run a higher curve than other Guardians, affording expensive assets like Lightning Gun more easily. However, her low sanity (6) requires aggressive horror soak (Holy Rosary, Star of Hyades) to prevent early elimination.19

### 2.5 Strategic Card Evaluation Table: Guardian

Card Name
Type
Doctrinal Function
Strategic Notes
Machete
Asset
Primary Weapon (Lvl 0)
The benchmark for efficiency. Infinite ammo makes it superior for long scenarios, but it fails if engaged with multiple enemies. 16
Vicious Blow
Skill
Damage Compression
Essential. Adds +1 damage to a fight action. Saves an entire action against 3-health enemies. Auto-include in every fighting deck. 16
Stand Together
Event
Support Economy
Multiplayer staple. Compresses resource generation for the team. A Guardian playing this enables the Seeker to setup faster.
Beat Cop (2)
Asset
Ally / Stat Boost
Provides +1 Combat and a testless ping of 1 damage. Highly efficient for finishing off odd-health enemies without wasting a weapon charge. 16
Prepared for the Worst
Event
Consistency Tutor
Essential for reliability. Mitigates the "no weapon" failure state. Should almost always be placed under Stick to the Plan. 17

## 3. Class Doctrine: The Seeker
The Seeker class (Yellow) fulfills the role of Clue Acquisition. In Arkham Horror, the primary win condition is advancing the Act deck, which almost invariably requires clues. Therefore, the Seeker is the engine of victory. Their primary stat is Intellect. The core philosophy of the Seeker is Efficiency. Investigating one clue at a time is often too slow for higher difficulties or high-player counts. The Seeker must compress the investigation timeline.

### 3.1 Clue Compression and Action Efficiency
The standard action of "Investigate" yields 1 clue. High-level Seeker play revolves around cards that yield 2 or more clues per action. Cards like Deduction (Skill) or Fingerprint Kit (Asset) allow acquiring additional clues for the same action cost. Deduction (2) is particularly potent, allowing for 3 clues in a single action. In a 4-player game where locations can have 8+ clues, this compression is vital to clear locations before the Doom clock advances.2
Testless Clues: Some locations have Shroud values (difficulty) that are prohibitively high (5+), or contain enemies that make investigating dangerous. "Testless" clue cards like Working a Hunch or Art Student bypass the skill test entirely. These cards are mathematically infinite in value regarding skill difficulty; they work equally well on a Shroud 1 location as a Shroud 6 location. The decision support system should prioritize these cards in decks intended for Hard/Expert campaigns where the chaos bag makes standard testing unreliable.

### 3.2 Movement Tech and Map Control
Movement is an inefficient action (1 action for 0 scenario progress). Seekers mitigate this with "Free" movement or teleportation. The doctrine treats movement tech as a form of action economy.
Pathfinder: This asset allows one free move per turn. If an investigator moves 10 times in a scenario, Pathfinder has generated 10 free actions—effectively giving the player three extra turns. It is widely considered one of the most powerful assets in the game.22
Shortcut: This event moves an investigator to a connecting location without spending an action or provoking attacks of opportunity. This dual utility serves as both mobility (getting to clues) and defense (escaping an enemy engaged with the Seeker). Shortcut (2) improves this by becoming a permanent attachment to a location, creating a "highway" for the entire team.23

### 3.3 Archetype A: The "Big Hand" Seeker
This archetype leverages cards that reward holding a large number of cards (8+). It is commonly associated with investigators like Daisy Walker or Harvey Walters.
The Engine: The core of this archetype is Higher Education (or its Taboo-adjusted variants) and Dream-Enhancing Serum. Higher Education allows converting resources into stat boosts at a 1:1 ratio, provided the hand size is large. This solves the difficulty curve of Hard/Expert modes by allowing theoretically infinite stat boosting.25 Dream-Enhancing Serum allows the player to hold duplicate cards and increases maximum hand size, facilitating the hoard.
Draw Mechanics: To maintain this hand size, the deck utilizes draw engines like Laboratory Assistant, Cryptic Research (Fast, draw 3), and Deep Knowledge. The goal is to draw through the deck rapidly, ensuring that the Seeker always has the optimal card for the situation.

### 3.4 Archetype B: The Deck-Cycle/Tutor
Seekers have the best card draw and search capabilities, allowing them to cycle their deck to play powerful events repeatedly.
Search Mechanics: Mr. Rook and Eureka! allow the Seeker to find specific answers. Mr. Rook is particularly potent as he filters the deck for weaknesses while finding key assets, compressing the "draw" phase significantly.
The "Pendant" Deck: Specific to builds utilizing Segment of Onyx. The goal is to search the deck rapidly to find the three segments, assembling the Pendant of the Queen. This relic provides auto-evasion and teleportation, granting the Seeker god-like control over the board state. Mandy Thompson is the premier investigator for this archetype due to her ability to search deeper and find multiple targets.26

### 3.5 Defensive Doctrine for Seekers
Seekers are physically vulnerable, often having low Combat and Agility. In multiplayer, Guardians protect them. In true solo, they must self-defend.
"I've got a plan!": An event that uses Intellect to deal damage. It can deal up to 4 damage in a single hit, essential for boss killing in solo Seeker decks. Without this, a solo Seeker is often hard-locked by a boss enemy.27
Occult Lexicon: This asset shuffles Blood-Rite events into the deck. Blood-Rite offers testless damage and card draw, providing a versatile tool for managing small enemies (Rats, Acolytes) without needing a weapon.
Evasion: High agility Seekers like Ursula Downs rely on evasion rather than fighting. Fieldwork and Hiking Boots boost her stats after moving, allowing her to evade an enemy and investigate in the same turn.28

### 3.6 Strategic Card Evaluation Table: Seeker

Card Name
Type
Doctrinal Function
Strategic Notes
Dr. Milan Christopher
Asset
Economy / Stat Engine
The gold standard for Seekers. +1 Intellect and generates resources on investigation success. Often nerfed by Taboo, but essential in base form. 20
Deduction
Skill
Clue Compression
Converts 1 action into 2 clues. Essential for tempo. Combines with Higher Education to guarantee the 2-clue pull. 2
Pathfinder
Asset
Action Economy
Saves 1 action per turn. Massive tempo gain over a scenario. Should be played Turn 1 if possible. 22
Cryptic Research
Event
Draw / Compression
Fast, draw 3. Zero cost. Perfect action compression. Can be used on other investigators to help them find setup pieces. 25
Logical Reasoning
Event
Mitigation
Heals horror or discards a Terror card. Critical for protecting low-sanity Guardians or clearing "Frozen in Fear."

## 4. Class Doctrine: The Rogue
The Rogue class (Green) fulfills the roles of High Utility, Burst Economy, and Evasion. Rogues are "Flex" investigators, capable of fighting or cluing depending on the build, often leveraging excessive resources to succeed. Their primary stats are Agility and Combat (often supplemented by items). The core philosophy of the Rogue is Excess. Where other classes manage scarcity, Rogues generate surplus resources and actions to overwhelm the game's math.

### 4.1 Economy as a Weapon: The "Big Money" Archetype
Rogues generate more resources than any other class. The doctrine of the Rogue is to convert this excess capital into game progress. This archetype, often called "Big Money," aims to hoard a resource pool of 10, 20, or even more.
Generators: The engine relies on cards like Faustian Bargain (gain 5 resources for 0 cost, add curses), Hot Streak (gain 7 or 10 resources), and Lone Wolf (passive income). Faustian Bargain is notable for being the most efficient burst economy card in the game, with the downside (curses) being manageable.5
Payoffs: Once the treasury is established, assets like Well Connected utilize the resource count to boost skill values. Well Connected allows the Rogue to exhaust the card to add +1 skill value for every 5 resources they have. With 20 resources, this is a +4 boost to any test, repeatedly. The Black Fan grants static stat boosts and an extra action if the Rogue has 10+ resources. Cunning Distraction and Money Talks utilize the resource pool to bypass tests or evade the entire board.4

### 4.2 Archetype B: "Succeed by X" Mechanics
This archetype utilizes cards that provide bonus effects if the skill test is passed by a wide margin (usually 2 or more). It is high-risk but generates massive momentum.
The Engine: Lucky Cigarette Case is the cornerstone. It allows the player to draw a card if they succeed by 2 or more. The upgraded version searches the deck, acting as a powerful tutor. This incentivizes the Rogue to "overshoot" tests significantly.
Synergy: Weapons like Switchblade (2) and Mauser C96 gain damage or resources only on "Success by 2." This requires high static skills or heavy committing of cards (Skill cards). Watch This! allows betting resources on a test, doubling the money if successful by 1.
Investigator Spotlight: Winifred Habbamock is the premier pilot for this archetype. Her investigator ability draws cards when committing skills, fueling the "Succeed by X" engine by replacing the committed cards immediately. This creates a cycle where the Rogue commits 3 cards to a test, passes by 6, draws 3 new cards, and gains extra actions or damage.31

### 4.3 Archetype C: Evasion Tanking and Lockpicks
Instead of killing enemies, the Rogue exhausts them. Evasion is often safer than fighting for high-health enemies (like the Conglomeration of Spheres or Elite bosses). It removes the enemy's turn, preventing attacks.
Lockdown: Cards like Lockpicks allow Rogues to investigate using their Agility added to their Intellect. This allows a Rogue with 1 Intellect and 5 Agility to investigate at a value of 6, making them highly competent clue gatherers. Pickpocketing (2) turns evasion into a card draw and resource engine, rewarding the Rogue for playing non-lethally.32
Warning: Evasion is temporary. In scenarios where enemies accumulate (e.g., "Doom Awaits"), evasion strategies must be paired with a solution for permanent removal or objective rushing. In True Solo, evasion is often superior to combat because leaving the location effectively solves the enemy problem.

### 4.4 Strategic Card Evaluation Table: Rogue

Card Name
Type
Doctrinal Function
Strategic Notes
Leo De Luca
Asset
Action Economy
Grants +1 Action per turn. Expensive (6 cost) but defines the class. The extra action allows for setup, movement, and recovery. 5
Lockpicks
Asset
Role Compression
Allows Rogues to investigate with Agility + Intellect. Highly reliable investigation tool that leverages the Rogue's best stat. 20
Faustian Bargain
Event
Burst Economy
5 Resources for 0 cost. The best burst economy card in the game. Essential for funding "Big Money" engines. 5
Lucky Cigarette Case
Asset
Draw Engine
Rewards the Rogue playstyle of over-succeeding. Provides steady card flow to find events and skills. 34
Double, Double
Asset
Utility / Multiplication
Allows playing an event twice. Powerful with Hot Streak (for money) or Pilfer (for clues). Defines the Sefina Rousseau archetype.

## 5. Class Doctrine: The Mystic
The Mystic class (Purple) fulfills the role of Willpower Substitution and Encounter Management. Mystics use magic to replace their physical stats with Willpower, allowing them to fight and investigate using a single attribute. Their primary stat is Willpower. The core philosophy of the Mystic is Willpower Supremacy. A well-built Mystic deck ignores Combat and Intellect stats entirely, relying on Spells to use Willpower for those tests.

### 5.1 The Spell Suite and Consistency
The Mystic's capability is entirely dependent on their assets. Without a spell, a Mystic is often a commoner with poor stats.
Combat: Shrivelling and Azure Flame allow using Willpower to fight and deal +1 damage.
Investigation: Rite of Seeking, Sixth Sense, and Clairvoyance allow using Willpower to investigate. Sixth Sense is notable for having infinite charges, providing reliability over long scenarios.
Evasion: Mists of R'lyeh uses Willpower to evade and provides movement.
Tutors: Because the Mystic is useless without these assets, Tutors (cards that find other cards) are mandatory. Arcane Initiate is a required include to ensure spells are drawn. It enters play cheaply and searches the deck for Spell cards, mitigating the draw variance.35

### 5.2 Archetype A: Chaos Bag Manipulation
Mystics interact directly with the probability engine of the game. This archetype seeks to reduce the variance of the chaos bag, effectively lowering the difficulty of the scenario.
Mechanic: Using cards to reveal multiple tokens and choose the best one (Grotesque Statue, Jacqueline Fine), or sealing bad tokens to remove them from the bag (Protective Incantation, The Chthonian Stone). By sealing a -4 or the Auto-Fail token, the Mystic mathematically increases the success rate of every test taken by the entire team.
Bless/Curse: Favor of the Sun and Favor of the Moon allow controlling when specific tokens are revealed. This triggers effects like Eye of Chaos or Armageddon, which have powerful bonuses when a Curse token is revealed. This turns the negative variance of Curses into a controlled resource.37

### 5.3 Archetype B: Doom Management
A high-risk archetype that places "Doom" on player cards for power, then removes the cards before the Doom threshold triggers the agenda advancement.
Key Cards: David Renfield generates resources and Willpower boosts but accumulates Doom. Arcane Acolyte is a cheap body that holds Doom. Marie Lambeau: An investigator designed for this, gaining free actions while Doom is on her cards. Mitigation: Moonlight Ritual removes Doom from cards. Sacrifice discards the card holding the Doom. Risk: Miscalculating the Doom threshold can cause the scenario to advance early, losing the game. This requires precise calculation of the Agenda deck and the "Doom Clock." A skilled Doom player knows exactly when the Agenda will flip and uses the "Witching Hour" (the turn before the flip) to load up on Doom that will be wiped away by the advancement.39

### 5.4 Strategic Card Evaluation Table: Mystic

Card Name
Type
Doctrinal Function
Strategic Notes
Shrivelling
Asset
Combat Substitute
The core combat spell. Essential for Mystic fighters. Converts Willpower to Damage. 35
Rite of Seeking
Asset
Clue Compression
The core investigation spell. Compresses clues (2 per action). High cost and charge limit requires support. 41
Arcane Initiate
Asset
Consistency Tutor
Enter play, search for spells. Critical for consistency. Taking 1 doom is usually worth the card draw. 35
Holy Rosary
Asset
Stat Boost
+1 Willpower and Horror soak. Highly efficient for the cost. Protects against spell backlash damage. 11
Ward of Protection
Event
Cancellation
Cancels a treachery card. Prevents game-ending effects like Ancient Evils. Auto-include in every Mystic deck. 35

## 6. Class Doctrine: The Survivor
The Survivor class (Red) fulfills the roles of Failure Mitigation, Recursion, and "Scrappiness." Survivors do not rely on high stats; they rely on altering the outcome of tests or profiting from failure. Their stats are often varied and mid-range. The core philosophy of the Survivor is Resilience. A Survivor deck is built on the assumption that tests will be failed, and that this failure can be weaponized.

### 6.1 The "Fail to Win" Mechanic
Survivor decks contain cards that trigger on failure.
Look What I Found!: If you fail an investigation by 2 or less, you discover 2 clues. This effectively turns a failed test into a double-success.
Lucky!: The defining card of the class. It allows a player to commit zero resources to a test, fail, and then spend 1 resource to add +2 to the result retroactively, turning the failure into a success. This is extreme resource efficiency because the resource is only spent when absolutely necessary.42
Drawing Thin: Increases test difficulty (making failure likely) to gain resources or cards. Combined with Take Heart (gain resources/cards on failure), a Survivor can generate massive economy by intentionally failing a test they had no intention of passing.43

### 6.2 Archetype A: Dark Horse / Poverty
This archetype intentionally keeps the resource pool at zero to trigger Dark Horse, which grants +1 to all stats.
Key Cards: Dark Horse, Fire Axe (Spend resources to boost combat), Madame Labranche (Gain resources if you have none). Economy: This deck requires no resource generation. It runs on a flat curve, spending every resource it gains immediately. It is highly consistent because it does not need to "build up" money. Fire Axe allows the Survivor to dump any accrued resources into a massive combat boost for a single swing, effectively using money as ammo.5

### 6.3 Archetype B: Recursion and Discard Synergy
Survivors have the best access to the discard pile, treating it as a second hand.
Looping: Scavenging allows recurring Item assets (like Ice Pick or Old Keyring) on a successful investigation. Yorick plays assets from the discard pile after defeating enemies. Infinite Loops: Resourceful is a skill card that, upon success, retrieves a Survivor card from the discard. By retrieving True Survivor (which retrieves Skills), a Survivor can create an infinite loop of playing their best skills every turn. Short Supply: This weakness-card-turned-asset forces the player to discard the top 10 cards of their deck at the start of the game. For a recursion Survivor, this is not a penalty but a setup, filling the discard pile with targets for Scavenging and Resourceful immediately.45
6.4 Defensive Mechanics: Soak and Evasion
Survivors often have high soak allies like Peter Sylvestre or Cherished Keepsake (the "Teddy Bear").
Peter Sylvestre: Widely considered one of the best allies in the game for his ability to soak horror and heal it at the end of the turn. He also boosts Agility (and Willpower in the upgraded version), covering the Survivor's defensive weaknesses and enabling evasion strategies. This makes Survivors surprisingly durable despite their often low sanity.35

### 6.5 Strategic Card Evaluation Table: Survivor

Card Name
Type
Doctrinal Function
Strategic Notes
Lucky!
Event
Failure Mitigation
Retroactively changes a failure to a success. The best Event in the game for tempo preservation. 35
Look What I Found!
Event
Clue Compression
Gains 2 clues on failure. Combos with low Intellect investigators to clear locations without passing tests. 35
Peter Sylvestre
Asset
Ally / Tank
Horror tank and stat boost. Essential for low-sanity Survivors. Self-healing mechanic provides infinite soak over time. 35
Take Heart
Skill
Economy
Commit to a test you will fail. Gain 2 resources and 2 cards. Weaponizes the encounter deck against itself. 20
Resourceful
Skill
Recursion
Recur a Survivor card from discard on success. Enables infinite loops and reuse of powerful events like Will to Survive. 45

## 7. Operational Context and Environmental Variables
The optimal deck is not static; it changes based on the environment. The decision support system must account for two primary variables: Player Count and Campaign Specifics.

### 7.1 True Solo vs. Multiplayer
True Solo (1 Investigator):
Generalist Doctrine: The deck must handle 100% of the clues and 100% of the enemies. A Guardian cannot just fight; they must have Flashlight or Evidence! to get clues. A Seeker cannot just clue; they must have I've got a plan! or Occult Lexicon to kill enemies.
Action Economy: The investigator has only 3 actions to solve the entire board state. Action compression is vital.
Evasion: Evasion becomes a primary defense. In multiplayer, evading an enemy leaves it alive to hurt a teammate. In solo, evading an enemy and leaving the location effectively solves the problem permanently.
Self-Sufficiency: Support cards like Stand Together lose significant value. Self-centered economy like Lone Wolf gains value.48
Multiplayer (3-4 Investigators):
Specialist Doctrine: Decks should be hyper-specialized. A Guardian should have 0 clue cards and 100% combat cards. Their job is to kill the boss which has scaled HP (Health per investigator). A Seeker should have 0 weapons; their job is to get the 12 clues per location.
Support: Cards like Stand Together, Encyclopedia, and Bob Jenkins gain immense value as they can boost the specialist who needs it most.
Movement: Maps are effectively larger because players are spread out. Movement tech (Safeguard, Pathfinder) is critical to keep the team in range of each other for protection.50

### 7.2 Campaign Specifics (Metagaming)
Different campaigns stress different stats.
The Forgotten Age: Heavily punishes low Agility. Decks without evasion or high agility will suffer trauma. Survivors and Rogues excel here.
The Circle Undone: Heavily punishes low Willpower via the encounter deck (Hexes). Mystics and high-willpower Guardians excel.
The Dunwich Legacy: Requires deck shuffling protection (Beyond the Veil) and high Intellect for specific scenarios.
The AI system should apply a "Campaign Weighting" to the evaluation of defensive stats based on the selected campaign.

### 7.3 The Taboo List
For competitive or balanced play, the "Taboo List" (optional official balance patch) adjusts card power.
Chained (XP Cost Increase): Cards like Higher Education and Streetwise often cost significantly more XP (3-8 XP), making them late-campaign upgrades rather than early staples.
Mutated (Text Change): Cards like Dr. Milan Christopher may have their resource generation capped (e.g., once per turn), reducing their dominance in "Big Money" decks.
Doctrine: When building for a system using Taboo, replace nerfed staples with alternative engines. For example, if Dr. Milan is nerfed, Seekers may switch to Jeremiah Kirby or Whitton Greene for economy.51

### 7.4 Mulligan Heuristics and Opening Hand Logic
The final operational check is the Mulligan.
The 5-Card Draw: Players draw 5 cards and may set aside any number to redraw.
Hard Mulligan Strategy: For setup-heavy decks (Big Gun Guardian, Asset-heavy Seeker), the strategy is to mulligan aggressively. If the hand does not contain the specific Key Asset (Weapon, Dr. Milan, Necronomicon), discard all 5 cards.
The Math: Discarding a decent card (like a skill) to dig for a Key Asset increases the probability of finding the Key Asset by roughly 15-20%. The tempo loss of playing without the Key Asset is far greater than the value of the kept skill card.
Exception: If the player holds a Tutor (Prepared for the Worst, Arcane Initiate), they effectively hold the Key Asset and can keep a more balanced hand.13

## 8. Conclusion: The Integrated Approach
Deckbuilding in Arkham Horror LCG is an exercise in risk management and resource optimization. The "best" deck is not the one with the highest potential damage ceiling, but the one that fails the least often. The doctrine presented here prioritizes:
Consistency: Through high asset density, tutors, and draw engines.
Solvency: Through a calculated resource curve and dedicated economy slots.
Role Adherence: Through specialization (Multiplayer) or role compression (Solo).
Mathematical Rigor: Through respecting the +2/+4 chaos bag thresholds and the importance of Mulligan probability.
By adhering to these principles, the decision support system can evaluate, construct, and refine decks that are resilient systems capable of surviving the Mythos, regardless of the specific investigator or scenario.

End of Doctrine


## Works cited
Investigating Fundamentals - Fantasy Flight Games, accessed January 25, 2026, https://www.fantasyflightgames.com/en/news/2025/3/11/investigating-fundamentals/
Arkham Horror LCG: Seeker Class - Make Craft Game ·, accessed January 25, 2026, https://makecraftgame.com/2025/07/11/arkham-horror-lcg-seeker-class/
How To Balance Your Economy in Arkham Horror LCG - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=CPLcPaK63NI
Arkham Horror Archetype Guide: Big Money - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=DT2r3yAHovc
What are the most popular deck archetypes? Or is there a site that explains the various 'types' of decks that are most popularly created? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/10ocp1l/what_are_the_most_popular_deck_archetypes_or_is/
Struggling to understand how to deal with increasing difficulty in the game... Is it just stacking assets and committing more cards? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/11qbsdh/struggling_to_understand_how_to_deal_with/
For those who play Hard and Expert, how do you do it? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1lpv4me/for_those_who_play_hard_and_expert_how_do_you_do/
Arkham Horror Deckbuilding Guide - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=ztqjOucWvEg
Arkham Horror LCG: Guardian Class - Make Craft Game ·, accessed January 25, 2026, https://makecraftgame.com/2025/05/09/arkham-horror-lcg-guardian-class/
Big Gun Guardian : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/ggy7gs/big_gun_guardian/
New to game. What's a good balance of skill, event, and asset cards and what to look for when comparing skill cards? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/9803do/new_to_game_whats_a_good_balance_of_skill_event/
Skills/assets/events numbers in a deck? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1dper8z/skillsassetsevents_numbers_in_a_deck/
HOW TO WIN ARKHAM HORROR: THE CARD GAME | Understanding Mulligans - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=y97RF-YY7Js
Tips for the Mulligan : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/17pzckb/tips_for_the_mulligan/
Building Custom Decks - Ratio's? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/cnpmwj/building_custom_decks_ratios/
Arkham Horror LCG: Top 10 Base Guardian Cards - Elevation Games, accessed January 25, 2026, https://www.elevation.games/blog/arkham-horror-lcg-top-10-base-guardian-cards
Best uses of Stick to the Plan - FFG Forum Archive, accessed January 25, 2026, https://ffg-forum-archive.entropicdreams.com/topic/305134-best-uses-of-stick-to-the-plan/
How do you best build around Big Gun : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/15yawe3/how_do_you_best_build_around_big_gun/
Four Deckbuilding Traps for New (and Old) Players : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/17azgbn/four_deckbuilding_traps_for_new_and_old_players/
Need help with Deckbuilding? Overwhelmed : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1qdemzo/need_help_with_deckbuilding_overwhelmed/
Deck building tips. : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/15zjtsm/deck_building_tips/
[COTD] Shortcut (7/5/2022) : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/vryu6h/cotd_shortcut_752022/
Shortcut | Arkham Horror: The Card Game Wiki - Fandom, accessed January 25, 2026, https://arkhamhorrorlcg.fandom.com/wiki/Shortcut
[COTD] Shortcut (4/12/2025) : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1jxhp94/cotd_shortcut_4122025/
Friends in Low Places is the Strongest Card Draw Engine in Arkham Horror - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1dz5zmq/friends_in_low_places_is_the_strongest_card_draw/
Arkham Horror: The Card Game - Deckbuilding for Beginners - - The Giant Brain, accessed January 25, 2026, https://giantbrain.co.uk/2020/04/22/arkham-horror-lcg-deckbuilding-for-beginners/
Seeking "seekers" deck building tips : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/gf5coh/seeking_seekers_deck_building_tips/
Seekers for solo? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/j2nbv2/seekers_for_solo/
Arkham Horror LCG: Top 10 Base Seeker Cards - Elevation Games, accessed January 25, 2026, https://www.elevation.games/blog/arkham-horror-lcg-top-10-base-seeker-cards
Rogue: Big Money | Archetype Guides | Arkham Horror: The Card Game - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=CPeNKZCbETU
Arkham Horror Archetype Guide: Succeed by X - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=XdxtkvBQbtw
Combat question vs tanky enemies : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/186g06k/combat_question_vs_tanky_enemies/
How is evade working out for you guys? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/74mx2v/how_is_evade_working_out_for_you_guys/
Rogue class, let's talk about it : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/hjxl27/rogue_class_lets_talk_about_it/
The top 5 level 0 cards (Hard) : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/8oqp0c/the_top_5_level_0_cards_hard/
I want to learn Mystic... I'm not sure where to start? : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/ubl2dk/i_want_to_learn_mystic_im_not_sure_where_to_start/
Mystic deck for token and bag control : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1ib96h2/mystic_deck_for_token_and_bag_control/
Evaluating Olive McBride with the Arkham Horror LCG Chaos Bag Simulator in R, accessed January 25, 2026, https://ntguardian.wordpress.com/2018/08/13/evaluating-olive-mcbride-arkham-horror-lcg-chaos-bag-simulator-r/
In-Depth Deck-Building: Mystic Doom Archetype | ARKHAM HORROR: THE CARD GAME, accessed January 25, 2026, https://www.youtube.com/watch?v=MEEgHnFmmV8
Doom Archetype : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/xpjg6g/doom_archetype/
Understanding Willpower - Rite of Seeking, accessed January 25, 2026, https://riteofseeking.com/2018/03/17/understanding-willpower/
The Survivor Nonsense Timing Video - Arkham Horror LCG Rules Roundup - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=JZVNhY3tRWM
Character Concept(s) – Unlimited Event Loops - Strength In Numbers - WordPress.com, accessed January 25, 2026, https://strengthinnumbersarkham.wordpress.com/2023/01/03/character-concepts-unlimited-event-loops/
Arkham Horror LCG Deckbuilding Guide: Dark Horse - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=an2Qg06phuc
Reduce, Reuse, Recycle --- Cards that manipulate the discard pile : r/arkhamhorrorlcg, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/yr5mny/reduce_reuse_recycle_cards_that_manipulate_the/
In-Depth Deck-Building: Survivor Discard Archetype | ARKHAM HORROR: THE CARD GAME - YouTube, accessed January 25, 2026, https://www.youtube.com/watch?v=j9N-M6PGWpw
The best Guardian is actually a Rogue/Seeker : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1743vnl/the_best_guardian_is_actually_a_rogueseeker/
Solo vs Multiplayer : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/1byizlb/solo_vs_multiplayer/
Prepared for the worst: a guide to solo deck building : r/arkhamhorrorlcg - Reddit, accessed January 25, 2026, https://www.reddit.com/r/arkhamhorrorlcg/comments/gjjdyy/prepared_for_the_worst_a_guide_to_solo_deck/
1-4 players, does that mean solo play as well? - FFG Forum Archive, accessed January 25, 2026, https://ffg-forum-archive.entropicdreams.com/topic/231522-1-4-players-does-that-mean-solo-play-as-well/
The List of Taboos - Fantasy Flight Games, accessed January 25, 2026, https://images-cdn.fantasyflightgames.com/filer_public/1b/4d/1b4d4cfb-6cb0-4ae5-9f2b-292ac3f41afc/list_of_taboos_v20.pdf
Taboo/FAQ 2.0 Roundup - Ancient Evils, accessed January 25, 2026, https://derbk.com/ancientevils/taboo-faq-2-0-roundup/
