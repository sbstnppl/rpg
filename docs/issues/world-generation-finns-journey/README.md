# World Generation for Finn's Journey

**Status:** Planned
**Priority:** High
**Detected:** 2024-12-21
**Related Sessions:** Session 81

## Problem Statement

The world needs to be designed with Finn's hidden backstory in mind. Create locations, NPCs, and world lore that support the overarching mystery of ancient darkness and hidden guardians. The world must feel like a real medieval fantasy setting while subtly laying groundwork for the epic narrative ahead.

## Design Requirements

### 1. The Hollow Mountains (Far North)
- Ancient mountain range where primordial evil is sealed
- Named for the vast cavern systems within
- Local legends speak of "the darkness that sleeps"
- Few venture there; those who do rarely return unchanged
- Subtle signs: strange aurora at night, animals avoid the northern passes

### 2. Remnants of the Starbound Order
The Starbound were an ancient order of guardians who sealed the darkness. Create:

**Ruined Locations:**
- Temple of the Dawn Star (abandoned, in the Greywood Forest)
- The Watcher's Tower (crumbling, on a hill near Millbrook - locals think it's just an old watchtower)
- Hidden shrine beneath Millbrook's old well (sealed, forgotten)

**Artifacts & Symbols:**
- Seven-pointed star motif (appears on old buildings, dismissed as decoration)
- Silver pendants with star inscriptions (like the one Finn's mother left him)
- Old books in forgotten corners of libraries mentioning "the Bound Ones"

### 3. Signs of Weakening Seals
Subtle omens that something is stirring:
- Livestock born with strange marks
- Nightmares becoming more common in the region
- An unusual cold winter this year
- Old folk remedies "not working like they used to"
- The village seer's prophecies growing darker

### 4. Key NPCs with Legend Knowledge

| NPC | Location | Knowledge | Willingness |
|-----|----------|-----------|-------------|
| Old Aldric | Millbrook tavern | Fragments of old ballads about "star warriors" | Shares freely (thinks they're just songs) |
| Sister Maren | Millbrook chapel | Church records mention "the Binding" | Suspicious of questions |
| The Hermit | Greywood edge | Actually a fallen Starbound member | Cryptic, tests worthiness |
| Master Corin | Traveling merchant | Collects old star-marked artifacts | Mercenary, sells information |
| Widow Brennan | Brennan Farm | Knew Finn's mother, suspects something | Protective, reveals slowly |

### 5. Millbrook and Surroundings

**Geography (realistic medieval village):**
```
                    NORTH
                      |
    Greywood Forest   |   Rolling Hills
         [dense]      |   [sheep grazing]
              \       |       /
               \   Watcher's  /
                \   Tower    /
                 \   |      /
    River Moss ---[MILLBROOK]--- East Road to Harwick
                 /   |      \
                /    |       \
     Brennan  /      |        \ Miller's
      Farm   /    Market       \  Pond
            /      Square       \
           /         |           \
    West Woods    Chapel      Farmlands
    [hunting]    [stone]      [wheat, barley]
                      |
                    SOUTH
                (Road to Thornbury)
```

**Key Millbrook Locations:**
- **Market Square**: Weekly market, central well (sealed shrine below)
- **The Dusty Flagon**: Tavern where Old Aldric tells stories
- **Chapel of the Light**: Stone chapel, Sister Maren's domain
- **Blacksmith's Forge**: Run by Henrik, practical man
- **Brennan Farm**: 2 miles west, where Finn works
- **The Old Mill**: Abandoned, rumored haunted (actually just bats)
- **Watcher's Tower**: 1 mile north, crumbling ruins on a hill

**Surrounding Area:**
- **Greywood Forest**: Dense, old-growth. Temple of Dawn Star hidden within
- **River Moss**: Slow river, fishing. Strange fish seen lately
- **East Road**: Trade route to Harwick (larger town, 2 days travel)
- **South Road**: Leads to Thornbury (market town, 1 day travel)

## Implementation Notes

- All world elements should be discoverable through normal gameplay
- Hidden backstory elements require investigation/exploration to uncover
- NPCs should have schedules and routines that feel natural
- Weather and seasons should be tracked (currently late autumn)

## World Lore Summary

The Starbound Order was founded 1,000 years ago when the Darkness first emerged from the Hollow Mountains. Seven champions, blessed by the dawn star, managed to bind the entity in the mountain's heart. They established the order to maintain the seals and watch for signs of weakening.

Over centuries, the order declined. Their temples fell to ruin, their knowledge scattered. The last known Starbound died 200 years ago - or so it is believed. But the bloodline carries power, and when the seals weaken, those of Starbound descent may awaken to their heritage.

Finn's mother was the last known descendant. She fled from those who would exploit or kill her child. She left Finn with Widow Brennan and disappeared - whether dead or in hiding, none know.

The pendant she left him is a key to the old shrine beneath Millbrook's well - and to his destiny.

## Files to Create/Modify

- [ ] Location data for all Millbrook area locations
- [ ] NPC definitions with schedules and knowledge levels
- [ ] World facts (SPV format) for lore elements
- [ ] Item definitions for Starbound artifacts
- [ ] Event triggers for omen occurrences

## Test Cases

- [ ] Player can explore all Millbrook locations
- [ ] NPCs give appropriate lore hints based on relationship level
- [ ] Starbound symbols appear in correct locations
- [ ] Weather/season system works correctly
- [ ] Hidden locations can be discovered through gameplay

## References

- Session 81 character data (Finn's hidden backstory)
- `src/database/models/` for entity/location schemas
- `data/settings/fantasy/` for setting configuration
