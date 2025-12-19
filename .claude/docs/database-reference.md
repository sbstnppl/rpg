# Database Reference

## Connection

**Always read connection details from `.env`:**
```bash
# .env contains:
DATABASE_URL=postgresql://langgraphrpg:bRXAKO0T8t23Wz3l9tyB@138.199.236.25/langgraphrpg
```

**Connection command:**
```bash
PGPASSWORD=bRXAKO0T8t23Wz3l9tyB psql -h 138.199.236.25 -U langgraphrpg -d langgraphrpg
```

## Before Querying

**ALWAYS run these first to discover structure:**
```sql
\dt                    -- List all tables
\d table_name          -- Describe table structure
\d+ table_name         -- Describe with more details
```

## Key Tables

### game_sessions
Central session table. All other tables have `session_id` FK to this.
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_name | varchar(200) | |
| setting | varchar(50) | e.g., "fantasy" |
| player_entity_id | integer | FK to entities |
| status | varchar(20) | |
| total_turns | integer | Current turn count |

### turns
Turn history. Immutable record of player/GM exchanges.
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_id | integer | FK to game_sessions |
| turn_number | integer | 1-indexed |
| player_input | text | |
| gm_response | text | |
| location_at_turn | varchar(100) | location_key |
| mentioned_items | json | Deferred items for on-demand spawning |
| entities_extracted | json | |

### entities
Characters, NPCs, monsters, objects.
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_id | integer | FK |
| entity_key | varchar(100) | Unique per session |
| display_name | varchar(200) | |
| entity_type | entitytype | PLAYER, NPC, MONSTER, OBJECT |
| is_alive | boolean | |
| is_active | boolean | |

### items
Physical items in the world.
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_id | integer | FK |
| item_key | varchar(100) | Unique per session |
| display_name | varchar(200) | |
| item_type | itemtype | WEAPON, ARMOR, CLOTHING, etc. |
| owner_id | integer | FK to entities - permanent owner |
| holder_id | integer | FK to entities - who has it now |
| storage_location_id | integer | FK to storage_locations |
| owner_location_id | integer | FK to locations - for environmental items |
| body_slot | varchar(30) | If equipped |
| body_layer | integer | Clothing layer (0=skin, higher=outer) |

### locations
World locations (rooms, areas, buildings).
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_id | integer | FK |
| location_key | varchar(100) | Unique per session |
| display_name | varchar(200) | |
| description | text | |
| parent_location_id | integer | FK to self (hierarchy) |
| category | varchar(50) | interior, exterior, etc. |

### facts
SPV (Subject-Predicate-Value) fact store.
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_id | integer | FK |
| subject_type | varchar(30) | "entity", "location", etc. |
| subject_key | varchar(100) | |
| predicate | varchar(100) | |
| value | text | |
| is_secret | boolean | Hidden from player |

### relationships
Entity-to-entity relationships with attitude dimensions.
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_id | integer | FK |
| from_entity_id | integer | FK to entities |
| to_entity_id | integer | FK to entities |
| trust | integer | 0-100 |
| liking | integer | 0-100 |
| respect | integer | 0-100 |
| romantic_interest | integer | 0-100 |
| familiarity | integer | 0-100 |
| fear | integer | 0-100 |

### storage_locations
Containers and storage spaces (bags, chests, body storage).
| Column | Type | Notes |
|--------|------|-------|
| id | integer | PK |
| session_id | integer | FK |
| location_key | varchar(100) | Unique per session |
| location_type | storagelocationtype | BODY, CONTAINER, ROOM, etc. |
| owner_entity_id | integer | FK to entities |
| container_item_id | integer | FK to items (if container is an item) |

## Common Queries

### Get latest session
```sql
SELECT * FROM game_sessions ORDER BY id DESC LIMIT 1;
```

### Get recent turns for current session
```sql
SELECT turn_number, substring(player_input, 1, 50) as input,
       substring(gm_response, 1, 50) as response, mentioned_items
FROM turns
WHERE session_id = (SELECT id FROM game_sessions ORDER BY id DESC LIMIT 1)
ORDER BY turn_number DESC LIMIT 10;
```

### Get player entity
```sql
SELECT e.* FROM entities e
JOIN game_sessions gs ON e.id = gs.player_entity_id
WHERE gs.id = (SELECT id FROM game_sessions ORDER BY id DESC LIMIT 1);
```

### Get items at location
```sql
SELECT i.* FROM items i
JOIN locations l ON i.owner_location_id = l.id
WHERE l.location_key = 'farmhouse_kitchen'
AND i.session_id = (SELECT id FROM game_sessions ORDER BY id DESC LIMIT 1);
```

### Get player inventory
```sql
SELECT i.* FROM items i
WHERE i.holder_id = (
    SELECT player_entity_id FROM game_sessions ORDER BY id DESC LIMIT 1
)
AND i.session_id = (SELECT id FROM game_sessions ORDER BY id DESC LIMIT 1);
```

### Reset to specific turn
```sql
-- Delete turns >= N
DELETE FROM turns
WHERE session_id = (SELECT id FROM game_sessions ORDER BY id DESC LIMIT 1)
AND turn_number >= 9;

-- Update session turn count
UPDATE game_sessions SET total_turns = 8
WHERE id = (SELECT id FROM game_sessions ORDER BY id DESC LIMIT 1);
```

## Important Notes

1. **Session scoping**: EVERY query must filter by `session_id`
2. **Item ownership model**:
   - `owner_id`: Permanent owner (entity)
   - `holder_id`: Who currently has it (entity)
   - `storage_location_id`: If in a container/storage
   - `owner_location_id`: For environmental items (owned by location)
3. **Unique constraints**: `entity_key`, `item_key`, `location_key` are unique per session
4. **Deferred items**: Stored in `turns.mentioned_items` as JSON array
