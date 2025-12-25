"""GM Node for the Simplified GM Pipeline.

Single LLM call with tool use for the Game Master.
Handles tool execution loop for skill checks, combat, and entity creation.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.database.models.session import GameSession
from src.llm.factory import get_reasoning_provider
from src.llm.base import LLMProvider
from src.llm.message_types import Message, MessageRole
from src.llm.tool_types import ToolDefinition, ToolParameter
from src.llm.response_types import LLMResponse, ToolCall
from src.gm.context_builder import GMContextBuilder
from src.gm.tools import GMTools
from src.gm.schemas import GMResponse, StateChange, NewEntity, StateChangeType
from src.gm.prompts import GM_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GMNode:
    """Game Master node with tool use.

    Executes the GM LLM with tools for skill checks, combat, and entity creation.
    Handles the tool execution loop until the LLM completes its response.
    """

    MAX_TOOL_ITERATIONS = 10  # Safety limit
    OOC_PREFIXES = ("ooc:", "ooc ", "[ooc]", "(ooc)")

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

        Args:
            player_input: The player's input/action.
            turn_number: Current turn number.

        Returns:
            GMResponse with narrative and state changes.
        """
        # Detect explicit OOC prefix
        is_explicit_ooc, cleaned_input = self._detect_explicit_ooc(player_input)

        # Build context with OOC hint
        context = self.context_builder.build(
            player_id=self.player_id,
            location_key=self.location_key,
            player_input=cleaned_input,
            turn_number=turn_number,
            is_ooc_hint=is_explicit_ooc,
        )

        # Build initial messages
        messages: list[Message] = [
            Message(role=MessageRole.USER, content=context),
        ]

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

        # Parse response into GMResponse
        return self._parse_response(response, player_input)

    async def _run_simple(self, messages: list[Message]) -> LLMResponse:
        """Run without tools for providers that don't support them.

        Args:
            messages: Conversation messages.

        Returns:
            LLM response.
        """
        return await self.llm_provider.complete(
            messages=messages,
            system_prompt=GM_SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=2048,
        )

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
                system_prompt=GM_SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=2048,
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

            # Execute tool calls
            tool_results_content = []
            for tool_call in response.tool_calls:
                result = await self._execute_tool_call(tool_call)
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": str(result),
                })

            # Add assistant message with tool calls
            # Anthropic requires non-empty content, so use placeholder if needed
            assistant_content = response.content or "[Executing tools...]"
            messages.append(Message(
                role=MessageRole.ASSISTANT,
                content=assistant_content,
            ))

            # Add tool results as user message
            # For Anthropic, tool results need to be in the proper format
            messages.append(Message(
                role=MessageRole.USER,
                content=str(tool_results_content),
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

    def _parse_response(self, response: LLMResponse, player_input: str) -> GMResponse:
        """Parse LLM response into GMResponse.

        Args:
            response: The LLM response.
            player_input: Original player input.

        Returns:
            Parsed GMResponse.
        """
        narrative = response.content.strip()

        # Detect if GM responded OOC (marked with [OOC] prefix)
        is_ooc = narrative.startswith("[OOC]")
        if is_ooc:
            # Strip the marker - display layer will handle styling
            narrative = narrative[5:].strip()

        # Extract state changes from tool results
        state_changes = self._extract_state_changes()
        new_entities = self._extract_new_entities()
        referenced_entities = self._extract_referenced_entities(narrative)

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
        """Estimate in-game minutes passed.

        Args:
            player_input: The player's input.
            state_changes: State changes that occurred.

        Returns:
            Estimated minutes.
        """
        input_lower = player_input.lower()

        # Check for combat (quick actions)
        if any(tc.change_type == StateChangeType.DAMAGE for tc in state_changes):
            return 1  # Combat round is quick

        # Check for movement
        if any(word in input_lower for word in ["go", "walk", "move", "travel"]):
            return 5

        # Check for conversation
        if any(word in input_lower for word in ["talk", "ask", "say", "tell"]):
            return 2

        # Check for observation
        if any(word in input_lower for word in ["look", "examine", "search"]):
            return 2

        # Default
        return 1


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
