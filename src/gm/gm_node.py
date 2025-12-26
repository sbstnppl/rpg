"""GM Node for the Simplified GM Pipeline.

Single LLM call with tool use for the Game Master.
Handles tool execution loop for skill checks, combat, and entity creation.
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.llm.factory import get_reasoning_provider
from src.llm.base import LLMProvider
from src.llm.message_types import Message, MessageRole, MessageContent
from src.llm.tool_types import ToolDefinition, ToolParameter
from src.llm.response_types import LLMResponse, ToolCall
from src.gm.context_builder import GMContextBuilder
from src.gm.grounding import GroundingManifest
from src.gm.grounding_validator import GroundingValidator, strip_key_references
from src.gm.tools import GMTools
from src.gm.schemas import GMResponse, StateChange, NewEntity, StateChangeType
# GM_SYSTEM_PROMPT is now built dynamically by context_builder.build_system_prompt()

logger = logging.getLogger(__name__)


class GMNode:
    """Game Master node with tool use.

    Executes the GM LLM with tools for skill checks, combat, and entity creation.
    Handles the tool execution loop until the LLM completes its response.
    """

    MAX_TOOL_ITERATIONS = 10  # Safety limit
    OOC_PREFIXES = ("ooc:", "ooc ", "[ooc]", "(ooc)")

    # Patterns for markdown formatting that should be stripped from narrative
    _MARKDOWN_HEADER_PATTERNS = (
        r"^\*\*[A-Za-z ]+(\([^)]+\))?:\*\*\s*$",  # **Section:** or **Updated Inventory (Finn):**
        r"^#+\s+.*$",  # ## Header or # Header
    )

    @staticmethod
    def _clean_narrative_static(narrative: str) -> str:
        """Clean markdown formatting from GM narrative output.

        The LLM sometimes outputs structured markdown sections like:
        - **Response:** headers
        - **Updated Inventory:** sections with bullet lists
        - **New Storage Container:** sections

        This method strips those while preserving pure prose narrative.

        Args:
            narrative: Raw narrative text from LLM.

        Returns:
            Cleaned narrative with markdown formatting removed.
        """
        import re

        if not narrative or not narrative.strip():
            return ""

        lines = narrative.split("\n")
        cleaned_lines = []
        in_structured_section = False

        for line in lines:
            stripped = line.strip()

            # Empty lines reset structured section tracking
            if not stripped:
                in_structured_section = False
                # Only keep blank line if we have content before it
                if cleaned_lines and cleaned_lines[-1].strip():
                    cleaned_lines.append("")
                continue

            # Check for markdown header patterns
            is_header = False
            for pattern in GMNode._MARKDOWN_HEADER_PATTERNS:
                if re.match(pattern, stripped):
                    is_header = True
                    break

            if is_header:
                # Check if this is a "section with structured content" header
                # like **Updated Inventory:** - these are followed by bullet lists
                if "**" in stripped and stripped.endswith(":**"):
                    # Check if header name suggests structured content
                    header_name = stripped.lower()
                    if any(
                        keyword in header_name
                        for keyword in [
                            "inventory",
                            "items",
                            "storage",
                            "container",
                            "equipment",
                            "added",
                            "removed",
                        ]
                    ):
                        in_structured_section = True
                # Skip the header line itself
                continue

            # Skip bullet points and numbered lists
            if re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
                continue

            # If in a structured section, skip until we hit a blank line
            if in_structured_section:
                continue

            cleaned_lines.append(line)

        # Join and clean up multiple blank lines
        result = "\n".join(cleaned_lines).strip()
        result = re.sub(r"\n{3,}", "\n\n", result)

        # Strip "GM:" prefix if present (LLM sometimes starts responses this way)
        if result.startswith("GM:"):
            result = result[3:].strip()

        # Remove inline bold (**text**) - keep the text
        result = re.sub(r"\*\*([^*]+)\*\*", r"\1", result)

        # Remove inline italic (*text*) - keep the text
        result = re.sub(r"\*([^*]+)\*", r"\1", result)

        # Remove inline code (`text`) - keep the text
        result = re.sub(r"`([^`]+)`", r"\1", result)

        # Remove mechanical status lines (e.g., "Your hunger decreases from...")
        # These contain technical data like "56/100" or "peckish (56/100)"
        result = re.sub(
            r"\n*Your \w+ (increases?|decreases?) from[^\n]*\n*",
            "",
            result,
            flags=re.IGNORECASE,
        )

        # Clean up any resulting extra whitespace
        result = re.sub(r"\n{3,}", "\n\n", result)

        return result.strip()

    def _clean_narrative(self, narrative: str) -> str:
        """Instance method wrapper for _clean_narrative_static."""
        return self._clean_narrative_static(narrative)

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        player_id: int,
        location_key: str,
        roll_mode: str = "auto",
        llm_provider: LLMProvider | None = None,
    ) -> None:
        """Initialize the GM node.

        Args:
            db: Database session.
            game_session: Current game session.
            player_id: Player entity ID.
            location_key: Current location key.
            roll_mode: "auto" or "manual" for dice rolls.
            llm_provider: LLM provider (defaults to get_gm_provider).
        """
        self.db = db
        self.game_session = game_session
        self.player_id = player_id
        self.location_key = location_key
        self.roll_mode = roll_mode
        self.llm_provider = llm_provider or get_reasoning_provider()

        self.context_builder = GMContextBuilder(db, game_session)
        self.tools = GMTools(db, game_session, player_id, roll_mode, location_key)

        # Track tool results and state changes
        self.tool_results: list[dict[str, Any]] = []
        self.pending_rolls: list[dict[str, Any]] = []

        # Dynamic system prompt and grounding manifest (set in run())
        self._current_system_prompt: str = ""
        self._current_manifest: GroundingManifest | None = None

        # Grounding validation settings
        self.grounding_enabled: bool = True
        self.grounding_max_retries: int = 2
        self.grounding_log_only: bool = False  # Log but don't retry if True

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """Get tool definitions for the LLM.

        Returns:
            List of ToolDefinition objects.
        """
        # Convert from dict format to ToolDefinition
        tool_dicts = self.tools.get_tool_definitions()
        definitions = []

        for tool_dict in tool_dicts:
            params = []
            schema = tool_dict.get("input_schema", {})
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))

            for name, prop in properties.items():
                param = ToolParameter(
                    name=name,
                    type=prop.get("type", "string"),
                    description=prop.get("description", ""),
                    required=name in required,
                    enum=tuple(prop["enum"]) if "enum" in prop else None,
                )
                params.append(param)

            definition = ToolDefinition(
                name=tool_dict["name"],
                description=tool_dict["description"],
                parameters=tuple(params),
            )
            definitions.append(definition)

        return definitions

    def _detect_explicit_ooc(self, player_input: str) -> tuple[bool, str]:
        """Detect explicit OOC prefix and strip it.

        Args:
            player_input: The raw player input.

        Returns:
            Tuple of (is_ooc, cleaned_input).
        """
        input_lower = player_input.lower().strip()
        for prefix in self.OOC_PREFIXES:
            if input_lower.startswith(prefix):
                return True, player_input[len(prefix):].strip()
        return False, player_input

    async def run(
        self,
        player_input: str,
        turn_number: int = 1,
    ) -> GMResponse:
        """Run the GM node to generate a response.

        Uses conversational context: world state in system prompt,
        turn history as message pairs.

        Args:
            player_input: The player's input/action.
            turn_number: Current turn number.

        Returns:
            GMResponse with narrative and state changes.
        """
        # Update tools with current turn number for fact recording
        self.tools.turn_number = turn_number

        # Detect explicit OOC prefix
        is_explicit_ooc, cleaned_input = self._detect_explicit_ooc(player_input)

        # Build grounding manifest for validation
        self._current_manifest = self.context_builder.build_grounding_manifest(
            player_id=self.player_id,
            location_key=self.location_key,
        )

        # Build dynamic system prompt with world state and summaries
        system_prompt = self.context_builder.build_system_prompt(
            player_id=self.player_id,
            location_key=self.location_key,
            include_grounding=self.grounding_enabled,
        )

        # Build conversation messages (turn history + current input)
        messages = self.context_builder.build_conversation_messages(
            player_id=self.player_id,
            player_input=cleaned_input,
            turn_number=turn_number,
            is_ooc_hint=is_explicit_ooc,
        )

        # Store system prompt for tool loop
        self._current_system_prompt = system_prompt

        # Try with tools first, fall back to simple completion if not supported
        try:
            tools = self.get_tool_definitions()
            response = await self._run_tool_loop(messages, tools)
        except Exception as e:
            if "does not support tools" in str(e).lower():
                logger.info("Provider doesn't support tools, using simple completion")
                response = await self._run_simple(messages)
            else:
                raise

        # Validate grounding if enabled
        if self.grounding_enabled and self._current_manifest:
            response = await self._validate_grounding(response, messages, tools)

        # Parse response into GMResponse
        return self._parse_response(response, player_input, turn_number)

    async def _run_simple(self, messages: list[Message]) -> LLMResponse:
        """Run without tools for providers that don't support them.

        Args:
            messages: Conversation messages.

        Returns:
            LLM response.
        """
        return await self.llm_provider.complete(
            messages=messages,
            system_prompt=self._current_system_prompt,
            temperature=0.7,
            max_tokens=2048,
        )

    async def _validate_grounding(
        self,
        response: LLMResponse,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> LLMResponse:
        """Validate grounding and retry if needed.

        Checks that all [key:text] references exist in the manifest
        and that entity names aren't mentioned without [key:text] format.

        Args:
            response: The LLM response to validate.
            messages: Current conversation messages (for retry).
            tools: Tool definitions (for retry).

        Returns:
            Validated (or cleaned) response.
        """
        if not self._current_manifest:
            return response

        validator = GroundingValidator(self._current_manifest)

        for attempt in range(self.grounding_max_retries + 1):
            result = validator.validate(response.content)

            if result.valid:
                if attempt > 0:
                    logger.info(f"Grounding validation passed on retry {attempt}")
                return response

            # Log validation errors
            logger.warning(
                f"Grounding validation failed (attempt {attempt + 1}): "
                f"{result.error_count} errors"
            )
            for err in result.invalid_keys:
                logger.debug(f"  Invalid key: [{err.key}:{err.text}]")
            for err in result.unkeyed_mentions:
                logger.debug(f"  Unkeyed mention: {err.display_name}")

            # If log-only mode, don't retry
            if self.grounding_log_only:
                break

            # If we have retries left, ask LLM to fix
            if attempt < self.grounding_max_retries:
                error_feedback = result.error_feedback()
                messages.append(Message.user(
                    f"GROUNDING ERROR - Please fix and respond again:\n\n{error_feedback}"
                ))

                # Get new response
                response = await self.llm_provider.complete_with_tools(
                    messages=messages,
                    tools=tools,
                    system_prompt=self._current_system_prompt,
                    temperature=0.7,
                    max_tokens=2048,
                    think=False,
                )

        # After max retries or in log-only mode, return as-is
        # The key stripping in _parse_response will clean up any valid [key:text] refs
        logger.warning(
            f"Grounding validation failed after {self.grounding_max_retries} retries, "
            "proceeding with response"
        )
        return response

    async def _run_tool_loop(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> LLMResponse:
        """Run the tool execution loop.

        Continues calling the LLM and executing tools until
        the LLM completes without tool calls.

        Args:
            messages: Conversation messages.
            tools: Available tools.

        Returns:
            Final LLM response with accumulated text from all iterations.
        """
        # Accumulate text from all iterations (narrative may come before tool calls)
        accumulated_text: list[str] = []

        for iteration in range(self.MAX_TOOL_ITERATIONS):
            logger.debug(f"GM tool loop iteration {iteration + 1}")

            # Call LLM with tools
            response = await self.llm_provider.complete_with_tools(
                messages=messages,
                tools=tools,
                system_prompt=self._current_system_prompt,
                temperature=0.7,
                max_tokens=2048,
                think=False,  # Disable thinking - GM decisions are straightforward
            )

            # Accumulate any text content from this response
            if response.content and response.content.strip():
                accumulated_text.append(response.content.strip())

            # Check for tool calls
            if not response.has_tool_calls:
                logger.debug("GM completed without tool calls")
                # Return response with accumulated text
                if accumulated_text:
                    # Combine all accumulated text
                    combined_text = "\n\n".join(accumulated_text)
                    return LLMResponse(
                        content=combined_text,
                        finish_reason=response.finish_reason,
                        tool_calls=response.tool_calls,
                        raw_response=response.raw_response,
                    )
                return response

            # Execute tool calls and build proper message content
            tool_use_blocks = []
            tool_result_messages = []

            for tool_call in response.tool_calls:
                # Create tool_use content block for assistant message
                tool_use_blocks.append(MessageContent(
                    type="tool_use",
                    tool_use_id=tool_call.id,
                    tool_name=tool_call.name,
                    tool_input=tool_call.arguments,
                ))

                # Execute the tool
                result = await self._execute_tool_call(tool_call)

                # Create tool result message
                result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                tool_result_messages.append(Message.tool_result(
                    tool_call_id=tool_call.id,
                    content=result_str,
                ))

            # Add assistant message with tool_use blocks
            # Include any text content as a text block if present
            assistant_content_blocks = []
            if response.content and response.content.strip():
                assistant_content_blocks.append(MessageContent(
                    type="text",
                    text=response.content,
                ))
            assistant_content_blocks.extend(tool_use_blocks)

            messages.append(Message(
                role=MessageRole.ASSISTANT,
                content=tuple(assistant_content_blocks),
            ))

            # Add tool result messages
            for tool_result_msg in tool_result_messages:
                messages.append(tool_result_msg)

            # Add narrative reminder after tool results
            # Reference the original player input to keep response grounded
            messages.append(Message(
                role=MessageRole.USER,
                content=(
                    "Now write your narrative response to the player's action. "
                    "Write 2-5 sentences in second person that directly describe what happens "
                    "in response to the player's input. Stay grounded in the scene context - "
                    "only reference NPCs, items, and locations that exist. "
                    "Do NOT explain tools or summarize mechanics - just tell the story."
                ),
            ))

        logger.warning(f"GM tool loop reached max iterations ({self.MAX_TOOL_ITERATIONS})")
        # Return with accumulated text even on max iterations
        if accumulated_text:
            combined_text = "\n\n".join(accumulated_text)
            return LLMResponse(
                content=combined_text,
                finish_reason=response.finish_reason,
                tool_calls=response.tool_calls,
                raw_response=response.raw_response,
            )
        return response

    async def _execute_tool_call(self, tool_call: ToolCall) -> dict[str, Any]:
        """Execute a single tool call.

        Args:
            tool_call: The tool call to execute.

        Returns:
            Tool result dictionary.
        """
        logger.debug(f"Executing tool: {tool_call.name} with args: {tool_call.arguments}")

        result = self.tools.execute_tool(tool_call.name, tool_call.arguments)

        # Track the result
        self.tool_results.append({
            "tool": tool_call.name,
            "arguments": tool_call.arguments,
            "result": result,
        })

        # Check for pending rolls (manual mode)
        if result.get("pending"):
            self.pending_rolls.append({
                "tool": tool_call.name,
                "arguments": tool_call.arguments,
                "partial_result": result,
            })

        return result

    def _parse_response(
        self,
        response: LLMResponse,
        player_input: str,
        turn_number: int = 1,
    ) -> GMResponse:
        """Parse LLM response into GMResponse.

        Args:
            response: The LLM response.
            player_input: Original player input.
            turn_number: Current turn number for observation recording.

        Returns:
            Parsed GMResponse.
        """
        narrative = response.content.strip()

        # Detect if GM responded OOC (marked with [OOC] prefix)
        is_ooc = narrative.startswith("[OOC]")
        if is_ooc:
            # Strip the marker - display layer will handle styling
            narrative = narrative[5:].strip()

        # Clean any hallucinated markdown formatting from the narrative
        narrative = self._clean_narrative(narrative)

        # Strip [key:text] references for display (e.g., [marcus_001:Marcus] → Marcus)
        if self.grounding_enabled:
            narrative = strip_key_references(narrative)

        # Extract state changes from tool results
        state_changes = self._extract_state_changes()
        new_entities = self._extract_new_entities()
        referenced_entities = self._extract_referenced_entities(narrative)

        # Record observations for any storages that had items created
        self._record_storage_observations(new_entities, turn_number)

        # For OOC responses, no time passes; otherwise estimate
        if is_ooc:
            time_passed = 0
        else:
            time_passed = self._estimate_time_passed(player_input, state_changes)

        return GMResponse(
            narrative=narrative,
            is_ooc=is_ooc,
            referenced_entities=referenced_entities,
            new_entities=new_entities,
            state_changes=state_changes,
            time_passed_minutes=time_passed,
            tool_results=self.tool_results,
        )

    def _extract_state_changes(self) -> list[StateChange]:
        """Extract state changes from tool results.

        Returns:
            List of StateChange objects.
        """
        changes = []

        for result in self.tool_results:
            tool = result["tool"]
            args = result["arguments"]
            res = result["result"]

            if tool == "damage_entity" and res.get("damage_taken", 0) > 0:
                changes.append(StateChange(
                    change_type=StateChangeType.DAMAGE,
                    target=args.get("target", ""),
                    details={
                        "amount": res.get("damage_taken", 0),
                        "remaining_hp": res.get("remaining_hp", 0),
                        "damage_type": args.get("damage_type", "physical"),
                    },
                ))

        return changes

    def _extract_new_entities(self) -> list[NewEntity]:
        """Extract new entities from create_entity tool calls.

        Returns:
            List of NewEntity objects.
        """
        entities = []

        for result in self.tool_results:
            if result["tool"] == "create_entity" and result["result"].get("success"):
                res = result["result"]
                args = result["arguments"]

                from src.gm.schemas import EntityType as GMEntityType

                entity_type_str = args.get("entity_type", "item")
                entity_type = getattr(GMEntityType, entity_type_str.upper(), GMEntityType.ITEM)

                entities.append(NewEntity(
                    entity_type=entity_type,
                    key=res.get("entity_key", ""),
                    display_name=res.get("display_name", args.get("name", "")),
                    description=args.get("description", ""),
                    gender=args.get("gender"),
                    occupation=args.get("occupation"),
                    item_type=args.get("item_type"),
                    storage_location_key=res.get("storage_location_key"),
                    category=args.get("category"),
                    parent_location=args.get("parent_location"),
                ))

        return entities

    def _extract_referenced_entities(self, narrative: str) -> list[str]:
        """Extract entity references from narrative.

        For now, returns entity keys that were used in tool calls.
        Could be enhanced with NLP to find entity mentions in text.

        Args:
            narrative: The narrative text.

        Returns:
            List of entity keys.
        """
        refs = set()

        for result in self.tool_results:
            args = result["arguments"]

            # Add target entities
            if "target" in args:
                refs.add(args["target"])

            # Add attacker entities
            if "attacker" in args and args["attacker"] != "player":
                refs.add(args["attacker"])

        return list(refs)

    def _estimate_time_passed(
        self,
        player_input: str,
        state_changes: list[StateChange],
    ) -> int:
        """Estimate in-game minutes passed based on tools called.

        Uses tool calls to infer time rather than parsing player input,
        which avoids false positives from keyword matching.

        Args:
            player_input: The player's input (unused, kept for signature).
            state_changes: State changes that occurred.

        Returns:
            Estimated minutes.
        """
        # Check for combat (quick actions)
        if any(tc.change_type == StateChangeType.DAMAGE for tc in state_changes):
            return 1  # Combat round

        # Infer time from tool calls
        max_time = 1  # Default: 1 minute for simple actions

        for result in self.tool_results:
            tool_name = result.get("name", "")
            args = result.get("input", {})

            # Need satisfaction - longest activities
            if tool_name == "satisfy_need":
                need = args.get("need", "")
                if need == "hunger":
                    max_time = max(max_time, 15)  # Eating
                elif need == "thirst":
                    max_time = max(max_time, 3)   # Drinking
                elif need == "stamina":
                    max_time = max(max_time, 15)  # Resting
                elif need == "hygiene":
                    max_time = max(max_time, 20)  # Bathing
                elif need == "social_connection":
                    max_time = max(max_time, 10)  # Socializing
                else:
                    max_time = max(max_time, 5)   # Other needs

            # Skill checks - brief focused actions
            elif tool_name == "skill_check":
                max_time = max(max_time, 2)

            # Combat rolls
            elif tool_name in ("attack_roll", "damage_entity"):
                max_time = max(max_time, 1)

            # Item manipulation - quick
            elif tool_name in ("take_item", "drop_item", "give_item"):
                max_time = max(max_time, 1)

            # Entity creation - depends on type
            elif tool_name == "create_entity":
                max_time = max(max_time, 2)

            # NPC attitude check - conversation context
            elif tool_name == "get_npc_attitude":
                max_time = max(max_time, 2)

            # Stimulus application - just observation
            elif tool_name == "apply_stimulus":
                max_time = max(max_time, 1)

        return max_time

    def _record_storage_observations(
        self,
        new_entities: list[NewEntity],
        turn_number: int,
    ) -> None:
        """Record observations for storages that had items created.

        When items are created in a storage via create_entity, this records
        the observation so the GM knows to reference established contents
        on future visits.

        Args:
            new_entities: Newly created entities from the response.
            turn_number: Current turn number.
        """
        from src.database.models.items import StorageLocation, Item
        from src.managers.storage_observation_manager import StorageObservationManager
        from src.managers.time_manager import TimeManager

        # Find unique storage location keys from new entities
        storage_keys = set()
        for entity in new_entities:
            if entity.storage_location_key:
                storage_keys.add(entity.storage_location_key)

        if not storage_keys:
            return

        # Get current game time for the observation
        time_manager = TimeManager(self.db, self.game_session)
        game_day, game_time = time_manager.get_current_time()

        # Initialize observation manager
        obs_manager = StorageObservationManager(self.db, self.game_session)

        # Record observation for each accessed storage
        for storage_key in storage_keys:
            # Look up storage location
            storage = self.db.query(StorageLocation).filter(
                StorageLocation.session_id == self.game_session.id,
                StorageLocation.location_key == storage_key,
            ).first()

            if not storage:
                logger.debug(f"Storage not found: {storage_key}")
                continue

            # Check if already observed (skip if so)
            if obs_manager.has_observed(self.player_id, storage.id):
                continue

            # Get current items in storage
            items = self.db.query(Item).filter(
                Item.session_id == self.game_session.id,
                Item.storage_location_id == storage.id,
            ).all()
            contents = [item.item_key for item in items]

            # Record the observation
            obs_manager.record_observation(
                observer_id=self.player_id,
                storage_location_id=storage.id,
                contents=contents,
                turn=turn_number,
                game_day=game_day,
                game_time=game_time,
            )
            logger.debug(
                f"Recorded observation: player={self.player_id} "
                f"storage={storage_key} contents={contents}"
            )


async def run_gm_node(
    db: Session,
    game_session: GameSession,
    player_id: int,
    location_key: str,
    player_input: str,
    turn_number: int = 1,
    roll_mode: str = "auto",
) -> GMResponse:
    """Convenience function to run the GM node.

    Args:
        db: Database session.
        game_session: Current game session.
        player_id: Player entity ID.
        location_key: Current location key.
        player_input: Player's input.
        turn_number: Current turn number.
        roll_mode: "auto" or "manual".

    Returns:
        GMResponse with narrative and state changes.
    """
    node = GMNode(
        db=db,
        game_session=game_session,
        player_id=player_id,
        location_key=location_key,
        roll_mode=roll_mode,
    )
    return await node.run(player_input, turn_number)
