"""Rich console observer for real-time pipeline visibility.

Uses the Rich library to provide pretty, colored console output
showing pipeline phases, LLM calls, tool executions, and validation.
"""

from rich.console import Console

from src.observability.events import (
    PhaseStartEvent,
    PhaseEndEvent,
    LLMCallStartEvent,
    LLMCallEndEvent,
    LLMTokenEvent,
    ToolExecutionEvent,
    ValidationEvent,
)


class RichConsoleObserver:
    """Pretty console output using Rich.

    Renders pipeline events to the console with colors, icons,
    and timing information.
    """

    # Phase icons for visual distinction
    PHASE_ICONS = {
        "context_building": "[blue]>[/]",
        "llm_tool_loop": "[cyan]@[/]",
        "grounding_validation": "[magenta]#[/]",
        "character_validation": "[magenta]%[/]",
        "state_application": "[green]*[/]",
        "narrative_cleaning": "[dim]-[/]",
    }

    def __init__(
        self,
        console: Console | None = None,
        show_tokens: bool = False,
        show_tool_details: bool = True,
        compact: bool = False,
        indent: str = "  ",
    ) -> None:
        """Initialize the console observer.

        Args:
            console: Rich Console instance. Creates new one if not provided.
            show_tokens: Stream LLM tokens to console.
            show_tool_details: Show tool arguments preview.
            compact: Use compact output format.
            indent: Indentation string for nested output.
        """
        self.console = console or Console()
        self.show_tokens = show_tokens
        self.show_tool_details = show_tool_details
        self.compact = compact
        self.indent = indent
        self._current_text = ""
        self._phase_times: dict[str, float] = {}
        self._in_llm_call = False

    def on_phase_start(self, event: PhaseStartEvent) -> None:
        """Render phase start."""
        icon = self.PHASE_ICONS.get(event.phase, "[dim]-[/]")
        self.console.print(f"{self.indent}{icon} {event.phase}...", end="")

    def on_phase_end(self, event: PhaseEndEvent) -> None:
        """Render phase completion with timing."""
        status = "[green]done[/]" if event.success else "[red]failed[/]"
        self.console.print(f" {status} ({event.duration_ms:.0f}ms)")
        self._phase_times[event.phase] = event.duration_ms

    def on_llm_call_start(self, event: LLMCallStartEvent) -> None:
        """Render LLM call start."""
        self._in_llm_call = True
        msgs_str = f" + {event.message_count} msgs" if event.message_count else ""
        tools_str = " [tools]" if event.has_tools else ""
        self.console.print(
            f"{self.indent}{self.indent}[cyan]LLM #{event.iteration}[/] "
            f"({event.system_prompt_tokens} sys tokens{msgs_str}){tools_str}",
            end="" if self.show_tokens else "\n",
        )
        if self.show_tokens:
            self.console.print()  # Newline before tokens
            self._current_text = ""

    def on_llm_token(self, event: LLMTokenEvent) -> None:
        """Render streaming token."""
        if self.show_tokens and not event.is_tool_use:
            self.console.print(event.token, end="")
            self._current_text += event.token

    def on_llm_call_end(self, event: LLMCallEndEvent) -> None:
        """Render LLM call completion."""
        self._in_llm_call = False
        if self.show_tokens and self._current_text:
            self.console.print()  # Newline after streamed tokens

        tools_str = f", {event.tool_count} tools" if event.has_tool_calls else ""
        preview = ""
        if event.text_preview and not self.show_tokens:
            preview = f' "{event.text_preview[:40]}..."'

        # Show cache status - green if cache hit, yellow if cache creation
        cache_str = ""
        if event.cache_read_tokens > 0:
            cache_str = f" [green]⚡cached:{event.cache_read_tokens}[/]"
        elif event.cache_creation_tokens > 0:
            cache_str = f" [yellow]📦caching:{event.cache_creation_tokens}[/]"

        self.console.print(
            f"{self.indent}{self.indent}{self.indent}-> {event.response_tokens} tokens, "
            f"{event.duration_ms:.0f}ms{tools_str}{cache_str}{preview}"
        )

    def on_tool_execution(self, event: ToolExecutionEvent) -> None:
        """Render tool execution."""
        status = "[green]+[/]" if event.success else "[red]x[/]"
        if self.show_tool_details:
            # Show abbreviated arguments
            args_preview = str(event.arguments)
            if len(args_preview) > 50:
                args_preview = args_preview[:50] + "..."
            self.console.print(
                f"{self.indent}{self.indent}{self.indent}{status} [yellow]{event.tool_name}[/] "
                f"({event.duration_ms:.0f}ms) {args_preview}"
            )
        else:
            self.console.print(
                f"{self.indent}{self.indent}{self.indent}{status} {event.tool_name} "
                f"({event.duration_ms:.0f}ms)"
            )

    def on_validation(self, event: ValidationEvent) -> None:
        """Render validation attempt."""
        if event.passed:
            status = "[green]passed[/]"
        else:
            status = "[yellow]retry[/]"

        attempt_str = f"({event.attempt}/{event.max_attempts})"
        self.console.print(
            f"{self.indent}[magenta]{event.validator_type}[/] {status} {attempt_str}"
        )

        # Show errors if validation failed
        if not event.passed and event.errors:
            for err in event.errors[:3]:  # Show up to 3 errors
                self.console.print(f"{self.indent}{self.indent}! {err}", style="dim red")

    def print_timing_summary(self) -> None:
        """Print summary of phase timings."""
        if not self._phase_times:
            return

        self.console.print("\n[bold]Phase Timing Summary:[/]")
        total = 0.0
        for phase, ms in self._phase_times.items():
            self.console.print(f"  {phase}: {ms:.0f}ms")
            total += ms
        self.console.print(f"  [bold]Total: {total:.0f}ms[/]")

    def reset(self) -> None:
        """Reset state for new turn."""
        self._current_text = ""
        self._phase_times = {}
        self._in_llm_call = False
