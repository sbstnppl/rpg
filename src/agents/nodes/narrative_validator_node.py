"""Narrative validation node for post-narration checking.

This node validates that the narrator didn't hallucinate items, NPCs,
or locations that don't exist in the game state. If validation fails,
it uses intelligent handling with story-aware spawn decisions:

- SPAWN: Create reasonable environmental items normally
- DEFER: Track decorative items for later on-demand spawning
- PLOT_HOOK_MISSING: Don't spawn, mention item is mysteriously absent
- PLOT_HOOK_RELOCATED: Spawn at alternate location (creates quest hook)

Uses LLM-based item extraction for accurate detection (no false positives
like "bewildering" being flagged as "ring").

Philosophy: Like a GM who considers "should this item exist, or is it
more interesting if it's missing?"
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.agents.state import GameState
from src.database.models.session import GameSession
from src.narrator.narrative_validator import NarrativeValidator
from src.narrator.item_extractor import ItemExtractor, ItemImportance, ExtractedItem
from src.narrator.npc_extractor import NPCExtractor, NPCImportance, ExtractedNPC
from src.narrator.location_extractor import LocationExtractor
from src.narrator.hallucination_handler import spawn_hallucinated_items
from src.oracle.complication_types import (
    ItemSpawnDecision,
    ItemSpawnResult,
    NPCSpawnDecision,
    NPCSpawnResult,
)


logger = logging.getLogger(__name__)

# Maximum number of re-narration attempts
MAX_RETRY_COUNT = 2


async def narrative_validator_node(state: GameState) -> dict[str, Any]:
    """Validate narrative against known game state.

    Uses LLM-based item extraction and story-aware spawn decisions.
    If validation fails and we haven't exceeded retry limit, signals
    for re-narration with stricter constraints.

    Args:
        state: Current game state with gm_response.

    Returns:
        Partial state update with validation result and routing signal.
    """
    narrative = state.get("gm_response", "")
    retry_count = state.get("narrative_retry_count", 0)

    # Skip validation for scene intros (they use different constraints)
    if state.get("is_scene_request"):
        logger.debug("Skipping validation for scene request")
        return {
            "narrative_validation_result": {"is_valid": True},
        }

    # Skip validation if no narrative
    if not narrative:
        logger.debug("Skipping validation - no narrative")
        return {
            "narrative_validation_result": {"is_valid": True},
        }

    # Get database and session
    db: Session | None = state.get("_db")
    game_session: GameSession | None = state.get("_game_session")
    player_location = state.get("player_location", "unknown")
    scene_context = state.get("scene_context", "")

    # Gather context for validation
    spawned_items = state.get("spawned_items") or []

    # Get items at location from turn_result metadata if available
    items_at_location: list[dict[str, Any]] = []
    npcs_present: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    equipped: list[dict[str, Any]] = []

    # Try to extract from dynamic_plans metadata
    dynamic_plans = state.get("dynamic_plans") or {}
    for plan in dynamic_plans.values():
        if isinstance(plan, dict):
            relevant_state = plan.get("_relevant_state", {})
            if relevant_state:
                items_at_location = relevant_state.get("items_at_location", [])
                npcs_present = relevant_state.get("npcs_present", [])
                inventory = relevant_state.get("inventory", [])
                equipped = relevant_state.get("equipped", [])
                break

    # Create item and NPC extractors with LLM provider
    from src.llm.factory import get_extraction_provider

    llm_provider = get_extraction_provider()
    item_extractor = ItemExtractor(llm_provider=llm_provider)
    npc_extractor = NPCExtractor(llm_provider=llm_provider)

    # Get player name for NPC extraction
    player_name = state.get("player_name", "the player")

    # Build validator with LLM-based extraction
    validator = NarrativeValidator(
        items_at_location=items_at_location,
        npcs_present=npcs_present,
        available_exits=[],
        spawned_items=spawned_items,
        inventory=inventory,
        equipped=equipped,
        item_extractor=item_extractor,
        npc_extractor=npc_extractor,
        current_location=player_location,
        player_name=player_name,
    )

    # Use async validation if extractor available, else fall back to sync
    if item_extractor:
        result = await validator.validate_async(narrative)
    else:
        result = validator.validate(narrative)

    if not result.is_valid:
        logger.info(
            "New items detected in narrative, evaluating spawn decisions: %s",
            [getattr(i, 'name', str(i)) for i in result.hallucinated_items],
        )

        # Use story-aware spawn decisions via ComplicationOracle
        return await _handle_hallucinated_items(
            state=state,
            result=result,
            validator=validator,
            db=db,
            game_session=game_session,
            player_location=str(player_location),
            scene_context=scene_context,
            retry_count=retry_count,
            spawned_items=spawned_items,
        )

    # Item validation passed, now check for hallucinated NPCs
    npc_result: dict[str, Any] = {}
    if result.hallucinated_npcs:
        logger.info(
            "New NPCs detected in narrative, evaluating spawn decisions: %s",
            [getattr(n, 'name', str(n)) for n in result.hallucinated_npcs],
        )
        npc_result = await _handle_hallucinated_npcs(
            state=state,
            hallucinated_npcs=result.hallucinated_npcs,
            db=db,
            game_session=game_session,
            player_location=str(player_location),
            scene_context=scene_context,
        )

    # Validation passed
    logger.debug("Narrative validation passed")
    base_result = {
        "narrative_validation_result": {
            "is_valid": True,
            "extracted_items": [
                {"name": i.name, "importance": i.importance.value}
                for i in result.extracted_items
            ] if result.extracted_items else [],
            "extracted_npcs": [
                {"name": n.name, "importance": n.importance.value}
                for n in result.extracted_npcs
            ] if result.extracted_npcs else [],
        },
    }

    # Merge NPC handling results
    if npc_result:
        base_result.update(npc_result)

    return base_result


async def _handle_hallucinated_items(
    state: GameState,
    result: Any,
    validator: NarrativeValidator,
    db: Session | None,
    game_session: GameSession | None,
    player_location: str,
    scene_context: str,
    retry_count: int,
    spawned_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Handle hallucinated items with story-aware spawn decisions.

    Uses ComplicationOracle to decide for each item:
    - SPAWN: Create normally
    - DEFER: Track for later
    - PLOT_HOOK_MISSING: Re-narrate mentioning item is absent
    - PLOT_HOOK_RELOCATED: Spawn elsewhere

    Args:
        state: Current game state.
        result: Validation result with hallucinated items.
        validator: The validator instance.
        db: Database session.
        game_session: Current game session.
        player_location: Player's current location key.
        scene_context: Current scene context.
        retry_count: Current re-narration retry count.
        spawned_items: Already spawned items this turn.

    Returns:
        State update dict with spawn results or re-narration signal.
    """
    from src.oracle.complication_oracle import ComplicationOracle

    # Items to spawn, defer, or create plot hooks for
    items_to_spawn: list[ExtractedItem] = []
    items_to_defer: list[ExtractedItem] = []
    plot_hook_missing: list[ItemSpawnResult] = []
    plot_hook_relocated: list[ItemSpawnResult] = []
    new_facts: list[str] = []
    extracted_locations: list[dict[str, Any]] = []

    # Get LLM provider for oracle decisions
    from src.llm.factory import get_extraction_provider
    from src.managers.location_manager import LocationManager

    llm_provider = get_extraction_provider()

    # Extract locations from narrative for proper item placement
    # This enables "bucket at the well" to create the well location
    location_key_map: dict[str, str] = {}
    if db and game_session:
        location_manager = LocationManager(db, game_session)
        known_locations = location_manager.get_all_location_keys()

        # Get the narrative from the validation result's context
        narrative = state.get("gm_response", "")

        if narrative:
            location_extractor = LocationExtractor(llm_provider=llm_provider)
            loc_result = await location_extractor.extract(narrative, known_locations)

            if loc_result.locations:
                for loc in loc_result.locations:
                    # Create or resolve location
                    location = location_manager.resolve_or_create_location(
                        location_text=loc.name,
                        parent_hint=loc.parent_hint,
                        category=loc.category.value,
                        description=loc.description,
                    )
                    location_key_map[loc.name.lower()] = location.location_key

                    # Also map without "the " prefix
                    name_no_the = loc.name.lower()
                    if name_no_the.startswith("the "):
                        name_no_the = name_no_the[4:]
                    location_key_map[name_no_the] = location.location_key

                    extracted_locations.append({
                        "location_key": location.location_key,
                        "display_name": location.display_name,
                        "category": loc.category.value,
                        "description": loc.description,
                    })

                logger.debug(
                    f"Extracted {len(loc_result.locations)} locations from narrative"
                )

    # Create oracle if we have db and session
    oracle = None
    if db and game_session:
        oracle = ComplicationOracle(
            db=db,
            game_session=game_session,
            llm_provider=llm_provider,
        )

    # Evaluate each hallucinated item
    for item in result.hallucinated_items:
        # Handle both ExtractedItem objects and plain strings (legacy)
        if isinstance(item, str):
            # Legacy string format - treat as IMPORTANT
            extracted_item = ExtractedItem(
                name=item,
                importance=ItemImportance.IMPORTANT,
                context="",
                is_new=True,
            )
        else:
            extracted_item = item

        # Get oracle decision if available
        if oracle:
            spawn_result = await oracle.evaluate_item_spawn(
                item=extracted_item,
                player_location=player_location,
                scene_context=scene_context,
                is_player_present=True,  # Player is at the location
            )

            logger.debug(
                f"Oracle decision for '{extracted_item.name}': "
                f"{spawn_result.decision.value} - {spawn_result.reasoning}"
            )

            # Sort items by decision
            if spawn_result.decision == ItemSpawnDecision.SPAWN:
                items_to_spawn.append(extracted_item)
            elif spawn_result.decision == ItemSpawnDecision.DEFER:
                items_to_defer.append(extracted_item)
            elif spawn_result.decision == ItemSpawnDecision.PLOT_HOOK_MISSING:
                plot_hook_missing.append(spawn_result)
                new_facts.extend(spawn_result.new_facts)
            elif spawn_result.decision == ItemSpawnDecision.PLOT_HOOK_RELOCATED:
                plot_hook_relocated.append(spawn_result)
                new_facts.extend(spawn_result.new_facts)
        else:
            # No oracle - default behavior based on importance
            if extracted_item.importance == ItemImportance.DECORATIVE:
                items_to_defer.append(extracted_item)
            else:
                items_to_spawn.append(extracted_item)

    # Handle plot hooks that require re-narration
    if plot_hook_missing:
        return await _handle_plot_hook_missing(
            plot_hook_missing,
            validator,
            retry_count,
            new_facts,
        )

    # Handle relocated items - spawn at alternate locations
    newly_spawned = list(spawned_items)
    if plot_hook_relocated and db and game_session:
        for hook in plot_hook_relocated:
            if hook.spawn_location:
                spawned = spawn_hallucinated_items(
                    db=db,
                    game_session=game_session,
                    items=[hook.item_name],
                    location_key=hook.spawn_location,
                    context=f"Relocated by oracle: {hook.reasoning}",
                )
                newly_spawned.extend(spawned)
                logger.info(
                    f"Spawned '{hook.item_name}' at '{hook.spawn_location}' "
                    f"(plot hook: {hook.plot_hook_description})"
                )

    # Spawn normal items at their extracted locations (or player location if none)
    if items_to_spawn and db and game_session:
        # Group items by their location for batch spawning
        items_by_location: dict[str, list[ExtractedItem]] = {}
        for item in items_to_spawn:
            # Determine spawn location
            spawn_loc = player_location
            if item.location:
                item_loc_lower = item.location.lower()
                if item_loc_lower in location_key_map:
                    spawn_loc = location_key_map[item_loc_lower]
                elif item_loc_lower.startswith("the "):
                    item_loc_lower = item_loc_lower[4:]
                    if item_loc_lower in location_key_map:
                        spawn_loc = location_key_map[item_loc_lower]
                else:
                    # Try fuzzy match or create new location
                    location_manager = LocationManager(db, game_session)
                    matched = location_manager.fuzzy_match_location(item.location)
                    if matched:
                        spawn_loc = matched.location_key
                    else:
                        new_loc = location_manager.resolve_or_create_location(
                            location_text=item.location,
                            category="exterior",
                            description="Location mentioned in narrative",
                        )
                        spawn_loc = new_loc.location_key
                        location_key_map[item_loc_lower] = spawn_loc

            if spawn_loc not in items_by_location:
                items_by_location[spawn_loc] = []
            items_by_location[spawn_loc].append(item)

        # Spawn items at each location
        for loc_key, items in items_by_location.items():
            item_names = [i.name for i in items]
            spawned = spawn_hallucinated_items(
                db=db,
                game_session=game_session,
                items=item_names,
                location_key=loc_key,
                context="spawned to match narrative",
            )
            newly_spawned.extend(spawned)

            logger.info(
                "Spawned %d items at %s: %s",
                len(spawned),
                loc_key,
                [s.get("display_name") for s in spawned],
            )

        db.commit()

    # Track deferred items for later on-demand spawning with correct locations
    deferred_items = []
    for item in items_to_defer:
        item_location = player_location
        if item.location:
            item_loc_lower = item.location.lower()
            if item_loc_lower in location_key_map:
                item_location = location_key_map[item_loc_lower]
            elif item_loc_lower.startswith("the "):
                item_loc_lower = item_loc_lower[4:]
                if item_loc_lower in location_key_map:
                    item_location = location_key_map[item_loc_lower]
            elif db and game_session:
                # Try fuzzy match or create location
                location_manager = LocationManager(db, game_session)
                matched = location_manager.fuzzy_match_location(item.location)
                if matched:
                    item_location = matched.location_key
                else:
                    new_loc = location_manager.resolve_or_create_location(
                        location_text=item.location,
                        category="exterior",
                        description="Location mentioned in narrative",
                    )
                    item_location = new_loc.location_key
                    location_key_map[item_loc_lower] = item_location

        deferred_items.append({
            "name": item.name,
            "context": item.context,
            "location": item_location,
            "location_description": item.location_description,
        })

    if deferred_items:
        logger.debug(f"Deferred {len(deferred_items)} decorative items for later spawning")

    # All items handled - validation now passes
    result_dict: dict[str, Any] = {
        "narrative_validation_result": {
            "is_valid": True,
            "fixed_by_spawning": [i.name for i in items_to_spawn],
            "deferred_items": deferred_items,
            "new_facts": new_facts,
        },
        "spawned_items": newly_spawned,
        "deferred_items": deferred_items,  # For persistence node
    }

    # Include extracted locations if any were created
    if extracted_locations:
        result_dict["extracted_locations"] = extracted_locations

    return result_dict


async def _handle_plot_hook_missing(
    plot_hooks: list[ItemSpawnResult],
    validator: NarrativeValidator,
    retry_count: int,
    new_facts: list[str],
) -> dict[str, Any]:
    """Handle PLOT_HOOK_MISSING items by triggering re-narration.

    Adds constraints telling the narrator to mention the items as
    mysteriously absent.

    Args:
        plot_hooks: List of items to treat as missing.
        validator: The validator instance.
        retry_count: Current retry count.
        new_facts: Facts to record.

    Returns:
        State update dict with re-narration signal.
    """
    if retry_count >= MAX_RETRY_COUNT:
        logger.error(
            "Max re-narration attempts exceeded for plot hooks: %s",
            [h.item_name for h in plot_hooks],
        )
        return {
            "narrative_validation_result": {
                "is_valid": False,
                "max_retries_exceeded": True,
                "plot_hooks": [h.to_dict() for h in plot_hooks],
            },
            "errors": [
                f"Narrative validation failed after {MAX_RETRY_COUNT} retries. "
                f"Could not incorporate plot hooks for: {[h.item_name for h in plot_hooks]}"
            ],
        }

    # Build constraint prompt for re-narration
    constraint_parts = [
        "IMPORTANT NARRATIVE CONSTRAINTS:",
        "",
    ]

    for hook in plot_hooks:
        constraint_parts.append(
            f"- The {hook.item_name} is MYSTERIOUSLY ABSENT. "
            f"Mention that it's missing or unusual. "
            f"({hook.plot_hook_description or 'creates intrigue'})"
        )

    constraints = "\n".join(constraint_parts)

    logger.info(
        "Triggering re-narration (attempt %d/%d) for plot hooks: %s",
        retry_count + 1,
        MAX_RETRY_COUNT,
        [h.item_name for h in plot_hooks],
    )

    return {
        "narrative_validation_result": {
            "is_valid": False,
            "plot_hooks": [h.to_dict() for h in plot_hooks],
            "new_facts": new_facts,
        },
        "narrative_retry_count": retry_count + 1,
        "narrative_constraints": constraints,
        "_route_to_narrator": True,
    }


async def _handle_hallucinated_npcs(
    state: GameState,
    hallucinated_npcs: list[Any],
    db: Session | None,
    game_session: GameSession | None,
    player_location: str,
    scene_context: str,
) -> dict[str, Any]:
    """Handle hallucinated NPCs with spawn/defer decisions.

    Named NPCs (CRITICAL/SUPPORTING with proper names) are spawned immediately
    with full generation. Background NPCs are deferred to mentioned_npcs.

    Args:
        state: Current game state.
        hallucinated_npcs: List of ExtractedNPC objects.
        db: Database session.
        game_session: Current game session.
        player_location: Player's current location key.
        scene_context: Current scene context.

    Returns:
        State update dict with spawned/deferred NPCs.
    """
    from src.oracle.complication_oracle import ComplicationOracle
    from src.llm.factory import get_extraction_provider

    npcs_to_spawn: list[ExtractedNPC] = []
    npcs_to_defer: list[ExtractedNPC] = []
    spawned_npcs: list[dict[str, Any]] = []
    deferred_npcs: list[dict[str, Any]] = []

    # Get LLM provider for oracle decisions (if needed)
    llm_provider = get_extraction_provider()

    # Create oracle if we have db and session
    oracle = None
    if db and game_session:
        oracle = ComplicationOracle(
            db=db,
            game_session=game_session,
            llm_provider=llm_provider,
        )

    # Evaluate each hallucinated NPC
    for npc in hallucinated_npcs:
        # Handle both ExtractedNPC objects and plain strings (legacy)
        if isinstance(npc, str):
            # Legacy string format - treat as SUPPORTING
            extracted_npc = ExtractedNPC(
                name=npc,
                importance=NPCImportance.SUPPORTING,
                is_named=True,  # Assume named if it's a string
            )
        else:
            extracted_npc = npc

        # Get oracle decision if available
        if oracle:
            spawn_result = await oracle.evaluate_npc_spawn(
                npc=extracted_npc,
                player_location=player_location,
                scene_context=scene_context,
            )

            logger.debug(
                f"Oracle NPC decision for '{extracted_npc.name}': "
                f"{spawn_result.decision.value} - {spawn_result.reasoning}"
            )

            # Sort NPCs by decision
            if spawn_result.decision == NPCSpawnDecision.SPAWN:
                npcs_to_spawn.append(extracted_npc)
            elif spawn_result.decision == NPCSpawnDecision.DEFER:
                npcs_to_defer.append(extracted_npc)
            # PLOT_HOOK_ABSENT would require re-narration (not implemented for NPCs yet)
        else:
            # No oracle - default behavior based on importance and is_named
            if (
                extracted_npc.importance == NPCImportance.BACKGROUND
                or not extracted_npc.is_named
            ):
                npcs_to_defer.append(extracted_npc)
            else:
                npcs_to_spawn.append(extracted_npc)

    # Spawn named NPCs with full generation
    if npcs_to_spawn and db and game_session:
        from src.services.emergent_npc_generator import EmergentNPCGenerator
        from src.managers.entity_manager import EntityManager

        npc_generator = EmergentNPCGenerator(db, game_session)
        entity_manager = EntityManager(db, game_session)

        for npc in npcs_to_spawn:
            # Check if NPC already exists
            existing = entity_manager.get_entity_by_display_name(npc.name)
            if existing:
                logger.debug(f"NPC '{npc.name}' already exists, skipping")
                continue

            try:
                # Generate entity key from name
                entity_key = _generate_npc_entity_key(npc.name, npc.role_hint)

                # Generate full NPC
                npc_state = npc_generator.create_npc(
                    context=f"{npc.context or 'present in scene'}. {npc.description or ''}",
                    location_key=player_location,
                    constraints={
                        "name": npc.name,
                        "gender": npc.gender_hint,
                        "occupation": npc.occupation_hint,
                        "role": npc.role_hint,
                    },
                )

                spawned_npcs.append({
                    "entity_id": npc_state.entity_id,
                    "entity_key": npc_state.entity_key,
                    "display_name": npc_state.display_name,
                    "role_hint": npc.role_hint,
                })

                logger.info(
                    f"Spawned NPC '{npc.name}' at {player_location} "
                    f"(entity_key={npc_state.entity_key})"
                )
            except Exception as e:
                logger.error(f"Failed to spawn NPC '{npc.name}': {e}")
                # Fall back to deferring
                npcs_to_defer.append(npc)

        db.commit()

    # Track deferred NPCs for later on-demand spawning
    for npc in npcs_to_defer:
        deferred_npcs.append({
            "name": npc.name,
            "description": npc.description,
            "context": npc.context,
            "location": player_location,
            "gender_hint": npc.gender_hint,
            "occupation_hint": npc.occupation_hint,
            "role_hint": npc.role_hint,
        })

    if deferred_npcs:
        logger.debug(f"Deferred {len(deferred_npcs)} background NPCs for later spawning")

    return {
        "spawned_npcs": spawned_npcs,
        "deferred_npcs": deferred_npcs,  # For persistence node
    }


def _generate_npc_entity_key(name: str, role_hint: str | None = None) -> str:
    """Generate a unique entity key for an NPC.

    Args:
        name: The NPC's display name.
        role_hint: Optional role hint (employer, guard, etc.).

    Returns:
        A unique entity key like "employer_aldric_a1b2" or "npc_marta_c3d4".
    """
    import uuid

    # Clean the name - take first word, lowercase
    name_clean = name.lower().split()[0] if name else "npc"
    # Remove non-alphanumeric
    name_clean = "".join(c for c in name_clean if c.isalnum())

    # Use role if provided, else "npc"
    prefix = "npc"
    if role_hint:
        prefix = role_hint.lower().replace(" ", "_")
        prefix = "".join(c for c in prefix if c.isalnum() or c == "_")

    # Add unique suffix
    unique_id = uuid.uuid4().hex[:4]

    return f"{prefix}_{name_clean}_{unique_id}"
