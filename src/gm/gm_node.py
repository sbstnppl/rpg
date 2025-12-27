"""GM Node for the Simplified GM Pipeline.

Single LLM call with tool use for the Game Master.
Handles tool execution loop for skill checks, combat, and entity creation.
"""

import json
import logging
import re
import time
from typing import Any, TYPE_CHECKING

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
from src.llm.audit_logger import set_audit_context
from src.gm.tools import GMTools
from src.gm.schemas import GMResponse, StateChange, NewEntity, StateChangeType
# GM_SYSTEM_PROMPT is now built dynamically by context_builder.build_system_prompt()

if TYPE_CHECKING:
    from src.observability.hooks import ObservabilityHook

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

    # Patterns that indicate the model broke character (speaking as AI/assistant)
    _CHARACTER_BREAK_PATTERNS = (
        # AI self-identification
        r"\bmy name is\b",  # Speaking as self (should be narrating NPC)
        r"\bi'?m an? (?:ai|llm|language model|assistant)\b",
        r"\bi am an? (?:ai|llm|language model|assistant)\b",
        r"\bas an? (?:ai|llm|assistant)\b",
        r"\bi don'?t have (?:a )?(?:name|feelings|emotions)\b",
        # Chatbot phrases
        r"\bfeel free to (?:ask|reach out)\b",
        r"\byou'?re welcome\b",
        r"\bhow can i help\b",
        r"\bhappy to (?:help|assist)\b",
        # Third-person narration (should be second-person "you")
        r"\bthe player\b",  # Should be "you", not "the player"
        r"\bplayer has\b",
        r"\bplayer's (?:actions|character|inventory)\b",
        # Meta-commentary about errors/tools (technical debugging)
        r"\bthe error (?:arises|occurs|is|indicates|shows)\b",
        r"\b(?:this|the) (?:error|issue) (?:can be|is) (?:resolved|fixed)\b",
        r"\bto (?:resolve|fix) this\b",
        r"\bfunction call\b",
        r"\bjson\s*\{",  # JSON code blocks
        r"\b(?:the|this) (?:function|tool|api)\b",
        r"\breferencing an? (?:undefined|invalid)\b",
        r"\bentity.+not found\b",
        r"\bitem.+(?:not|doesn't) exist\b",
        r"\bis not recognized\b",  # Technical debugging
        r"\bhas not been (?:introduced|provided|defined)\b",
        r"\bno prior (?:mention|information|context)\b",
        r"\bin the current context\b",  # Technical scoping language
        # Game design / strategy game style
        r"\bnext steps?:",  # Strategy game prompt
        r"\bnarratively,?\s+this\b",  # Meta-commentary on narrative
        # Tool output exposure / meta-questions
        r"\bwhat would you like\b",
        r"\bthe provided text\b",
        r"\brules for (?:handling|managing|processing)\b",
        r"\blet me know if\b",
        r"\bwhat .+ do with (?:this|these)\b",
        r"\bwould you like me to\b",
        r"\bfor clarification\b",
        r"\bto ensure i address\b",
        r"\bno specific (?:question|task)\b",
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

    @classmethod
    def _detect_character_break(cls, text: str) -> tuple[bool, str | None]:
        """Detect if the model broke character (responding as AI instead of GM).

        Args:
            text: The narrative text to check.

        Returns:
            Tuple of (is_broken, matched_pattern) where matched_pattern
            is the pattern that triggered detection, or None.
        """
        if not text:
            return False, None

        text_lower = text.lower()
        for pattern in cls._CHARACTER_BREAK_PATTERNS:
            if re.search(pattern, text_lower):
                return True, pattern
        return False, None

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        player_id: int,
        location_key: str,
        roll_mode: str = "auto",
        llm_provider: LLMProvider | None = None,
        observability_hook: "ObservabilityHook | None" = None,
    ) -> None:
        """Initialize the GM node.

        Args:
            db: Database session.
            game_session: Current game session.
            player_id: Player entity ID.
            location_key: Current location key.
            roll_mode: "auto" or "manual" for dice rolls.
            llm_provider: LLM provider (defaults to get_gm_provider).
            observability_hook: Optional hook for real-time observability.
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

        # Observability hook (NullHook does nothing if not provided)
        if observability_hook is None:
            from src.observability.hooks import NullHook
            self._hook: "ObservabilityHook" = NullHook()
        else:
            self._hook = observability_hook

        # Minimal context mode for local LLMs
        self._use_minimal_context = self._should_use_minimal_context()

    def _should_use_minimal_context(self) -> bool:
        """Determine if minimal context mode should be used.

        Returns:
            True if minimal context mode should be enabled.
        """
        from src.config import settings

        # Explicit setting takes precedence
        if settings.use_minimal_context is not None:
            return settings.use_minimal_context

        # Auto-detect based on provider
        provider_name = getattr(self.llm_provider, "provider_name", "")
        return provider_name in ("ollama", "qwen-agent")

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
        from src.observability.events import PhaseStartEvent, PhaseEndEvent

        # Set audit context for LLM logging
        set_audit_context(
            session_id=self.game_session.id,
            turn_number=turn_number,
            call_type="gm",
        )

        # Update tools with current turn number for fact recording
        self.tools.turn_number = turn_number

        # Detect explicit OOC prefix
        is_explicit_ooc, cleaned_input = self._detect_explicit_ooc(player_input)

        # Phase: Context Building
        self._hook.on_phase_start(PhaseStartEvent(phase="context_building"))
        context_start = time.perf_counter()

        # Build grounding manifest for validation
        self._current_manifest = self.context_builder.build_grounding_manifest(
            player_id=self.player_id,
            location_key=self.location_key,
        )

        # Build system prompt (minimal or full depending on provider)
        if self._use_minimal_context:
            # Minimal context mode for local LLMs
            from src.gm.action_classifier import ActionClassifier
            action_category = ActionClassifier.classify(cleaned_input)
            system_prompt = self.context_builder.build_minimal_system_prompt(
                player_id=self.player_id,
                location_key=self.location_key,
                action_category=action_category,
            )
            logger.debug(f"Using minimal context mode (action: {action_category.value})")
        else:
            # Full context mode for cloud providers with caching
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

        self._hook.on_phase_end(PhaseEndEvent(
            phase="context_building",
            duration_ms=(time.perf_counter() - context_start) * 1000,
        ))

        # Phase: LLM Tool Loop
        self._hook.on_phase_start(PhaseStartEvent(phase="llm_tool_loop"))
        tool_loop_start = time.perf_counter()

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

        self._hook.on_phase_end(PhaseEndEvent(
            phase="llm_tool_loop",
            duration_ms=(time.perf_counter() - tool_loop_start) * 1000,
        ))

        # Validate grounding if enabled
        if self.grounding_enabled and self._current_manifest:
            response = await self._validate_grounding(response, messages, tools)

        # Validate character consistency (detect AI-like responses)
        response = await self._validate_character(response, messages)

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
        from src.observability.events import ValidationEvent

        if not self._current_manifest:
            return response

        validator = GroundingValidator(self._current_manifest)
        max_attempts = self.grounding_max_retries + 1

        for attempt in range(max_attempts):
            result = validator.validate(response.content)

            # Emit validation event
            errors = [f"Invalid: [{e.key}:{e.text}]" for e in result.invalid_keys]
            errors.extend([f"Unkeyed: {e.display_name}" for e in result.unkeyed_mentions])

            self._hook.on_validation(ValidationEvent(
                validator_type="grounding",
                attempt=attempt + 1,
                max_attempts=max_attempts,
                passed=result.valid,
                error_count=result.error_count,
                errors=errors[:5],  # Limit to 5 errors for display
            ))

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

                # Build context about tool results so LLM narrates the action, not scene
                tool_context = ""
                if self.tool_results:
                    tool_context = "\n\nREMINDER: You already processed the player's action. Narrate what happened based on these tool results:\n"
                    for tr in self.tool_results:
                        tool_name = tr.get("tool", "unknown")
                        tool_result = tr.get("result", {})
                        if isinstance(tool_result, dict) and tool_result.get("success"):
                            tool_context += f"- {tool_name}: {tool_result.get('message', 'success')}\n"

                messages.append(Message.user(
                    f"GROUNDING ERROR - Please fix your narrative and respond again.\n\n"
                    f"{error_feedback}\n\n"
                    f"{tool_context}"
                    "Write ONLY the corrected narrative text - do NOT call any tools. "
                    "Narrate the RESULTS of the player's action, not just the scene."
                ))

                # Get new response (no tools to force narrative-only response)
                response = await self.llm_provider.complete(
                    messages=messages,
                    system_prompt=self._current_system_prompt,
                    temperature=0.7,
                    max_tokens=2048,
                )

        # After max retries or in log-only mode, return as-is
        # The key stripping in _parse_response will clean up any valid [key:text] refs
        logger.warning(
            f"Grounding validation failed after {self.grounding_max_retries} retries, "
            "proceeding with response"
        )
        return response

    async def _validate_character(
        self,
        response: LLMResponse,
        messages: list[Message],
    ) -> LLMResponse:
        """Validate that the response stays in GM character.

        Detects AI-assistant patterns (e.g., "My name is...", "You're welcome",
        "How can I help") and retries with correction if found.

        Args:
            response: The LLM response to validate.
            messages: Current conversation messages (for retry).

        Returns:
            Validated or corrected response.
        """
        from src.observability.events import ValidationEvent

        if not response.content:
            return response

        has_break, pattern = self._detect_character_break(response.content)

        if not has_break:
            # Emit passing validation event
            self._hook.on_validation(ValidationEvent(
                validator_type="character",
                attempt=1,
                max_attempts=2,
                passed=True,
            ))
            return response

        # Emit failing validation event
        self._hook.on_validation(ValidationEvent(
            validator_type="character",
            attempt=1,
            max_attempts=2,
            passed=False,
            error_count=1,
            errors=[f"Pattern matched: {pattern}"],
        ))

        logger.warning(
            f"Character break detected (pattern: {pattern}): "
            f"{response.content[:100]}..."
        )

        # Retry with explicit correction
        messages.append(Message.user(
            "CHARACTER ERROR - You broke character and responded as an AI assistant.\n\n"
            "CRITICAL RULES:\n"
            "- You ARE the Game Master narrating a fantasy RPG\n"
            "- NEVER say 'My name is...' - narrators don't have names\n"
            "- NEVER use assistant phrases like 'You're welcome' or 'How can I help'\n"
            "- NEVER refer to 'the player' - use 'you' (second person)\n"
            "- NEVER write 'Next steps:' or game design commentary\n"
            "- NEVER explain errors, debug tools, or provide technical commentary\n"
            "- If a tool fails, handle it gracefully IN THE STORY\n"
            "- Write immersive second-person narrative prose: 'You see...', 'You notice...'\n\n"
            "Now write the proper GM narrative response to the player's input. "
            "Stay in character as the invisible narrator describing the game world."
        ))

        corrected = await self.llm_provider.complete(
            messages=messages,
            system_prompt=self._current_system_prompt,
            temperature=0.7,
            max_tokens=2048,
        )

        # Check if correction worked
        still_broken, _ = self._detect_character_break(corrected.content or "")

        # Emit second validation event
        self._hook.on_validation(ValidationEvent(
            validator_type="character",
            attempt=2,
            max_attempts=2,
            passed=not still_broken,
            error_count=1 if still_broken else 0,
            errors=["Pattern still matched after retry"] if still_broken else [],
        ))

        if still_broken:
            logger.error(
                "Character break persists after correction attempt, "
                "proceeding with original response"
            )
            return response

        logger.info("Character validation passed after correction")
        return corrected

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
        from src.observability.events import LLMCallStartEvent, LLMCallEndEvent

        # Accumulate text from all iterations (narrative may come before tool calls)
        accumulated_text: list[str] = []

        # Estimate system prompt tokens (rough: 4 chars per token)
        sys_tokens = len(self._current_system_prompt) // 4

        for iteration in range(self.MAX_TOOL_ITERATIONS):
            logger.debug(f"GM tool loop iteration {iteration + 1}")

            # Emit LLM call start event
            self._hook.on_llm_call_start(LLMCallStartEvent(
                iteration=iteration + 1,
                model=getattr(self.llm_provider, "default_model", "unknown"),
                has_tools=len(tools) > 0,
                system_prompt_tokens=sys_tokens,
                message_count=len(messages),
            ))

            llm_start = time.perf_counter()

            # Call LLM with tools - use streaming if available
            if hasattr(self.llm_provider, "complete_with_tools_streaming"):
                from src.observability.events import LLMTokenEvent

                def emit_token(token: str) -> None:
                    self._hook.on_llm_token(LLMTokenEvent(token=token, is_tool_use=False))

                response = await self.llm_provider.complete_with_tools_streaming(
                    messages=messages,
                    tools=tools,
                    system_prompt=self._current_system_prompt,
                    temperature=0.7,
                    max_tokens=2048,
                    on_token=emit_token,
                )
            else:
                response = await self.llm_provider.complete_with_tools(
                    messages=messages,
                    tools=tools,
                    system_prompt=self._current_system_prompt,
                    temperature=0.7,
                    max_tokens=2048,
                    think=False,
                )

            llm_duration = (time.perf_counter() - llm_start) * 1000

            # Get actual token count and cache stats from usage if available
            resp_tokens = 0
            cache_read = 0
            cache_creation = 0
            if response.usage:
                resp_tokens = response.usage.completion_tokens
                cache_read = response.usage.cache_read_tokens
                cache_creation = response.usage.cache_creation_tokens
            else:
                # Fall back to rough estimate
                resp_tokens = len(response.content or "") // 4

            # Emit LLM call end event
            self._hook.on_llm_call_end(LLMCallEndEvent(
                iteration=iteration + 1,
                duration_ms=llm_duration,
                response_tokens=resp_tokens,
                has_tool_calls=response.has_tool_calls,
                tool_count=len(response.tool_calls) if response.tool_calls else 0,
                text_preview=(response.content or "")[:50],
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
            ))

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

                # Execute the tool (with timing)
                result = await self._execute_tool_call(tool_call)

                # Create tool result message (TOOL role for provider compatibility)
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

            # Add tool result messages (TOOL role)
            # The Anthropic provider will merge these into a single user message
            # No separate narrative reminder - system prompt already instructs this
            for tool_result_msg in tool_result_messages:
                messages.append(tool_result_msg)

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
        from src.observability.events import ToolExecutionEvent

        logger.debug(f"Executing tool: {tool_call.name} with args: {tool_call.arguments}")

        tool_start = time.perf_counter()
        result = self.tools.execute_tool(tool_call.name, tool_call.arguments)
        tool_duration = (time.perf_counter() - tool_start) * 1000

        # Emit tool execution event
        success = result.get("success", True) if isinstance(result, dict) else True
        self._hook.on_tool_execution(ToolExecutionEvent(
            tool_name=tool_call.name,
            arguments=tool_call.arguments,
            result=result if isinstance(result, dict) else {"result": str(result)},
            duration_ms=tool_duration,
            success=success,
        ))

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
