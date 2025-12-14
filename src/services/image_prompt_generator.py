"""Image prompt generator for FLUX.1-dev.

Generates optimized image prompts from game state for use with FLUX.1-dev
or similar text-to-image models. Prompts are limited to ~60 tokens to fit
within CLIP's 77-token limit.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from src.database.models.entities import Entity
from src.database.models.session import GameSession, Turn
from src.llm.factory import get_cheap_provider
from src.llm.message_types import Message, MessageRole
from src.managers.context_compiler import ContextCompiler
from src.managers.entity_manager import EntityManager
from src.managers.item_manager import ItemManager


# Style suffixes for different output types
SCENE_STYLES = {
    "photo": "photorealistic, highly detailed, cinematic lighting, 8k",
    "art": "digital illustration, fantasy art style, painterly, detailed",
}

PORTRAIT_STYLES = {
    "photo": "portrait photography, soft lighting, shallow depth of field, detailed face, 8k",
    "art": "character portrait, digital painting, fantasy art style, detailed face, painterly",
}

# Load template
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "data" / "templates" / "image_prompt.md"


def _load_template() -> str:
    """Load the image prompt system template."""
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text()
    # Fallback inline template
    return """You generate FLUX.1-dev image prompts. Rules:
- Maximum 60 tokens (CLIP limit is 77)
- NO text, signs, or writing in images
- Focus on visual, concrete elements
- Use commas to separate descriptors
- End with the provided style suffix
- Output ONLY the prompt, no explanation"""


class ImagePromptGenerator:
    """Generates FLUX.1-dev image prompts from game state."""

    def __init__(
        self,
        db: Session,
        game_session: GameSession,
        player: Entity,
    ) -> None:
        """Initialize the generator.

        Args:
            db: Database session.
            game_session: Current game session.
            player: Player entity.
        """
        self.db = db
        self.game_session = game_session
        self.player = player
        self._compiler = ContextCompiler(db, game_session)
        self._item_manager = ItemManager(db, game_session)

    def _get_player_location(self) -> str | None:
        """Get the player's current location from turn history or npc_extension.

        Returns:
            Location key or None if not found.
        """
        # First try npc_extension (if player has one)
        if self.player.npc_extension and self.player.npc_extension.current_location:
            return self.player.npc_extension.current_location

        # Fall back to most recent turn's location
        last_turn = (
            self.db.query(Turn)
            .filter(Turn.session_id == self.game_session.id)
            .order_by(Turn.turn_number.desc())
            .first()
        )
        if last_turn and last_turn.location_at_turn:
            return last_turn.location_at_turn

        return None

    def _get_npcs_visual_descriptions(self, location_key: str) -> str:
        """Get visual descriptions of NPCs at location for image prompts.

        Args:
            location_key: Location to get NPCs from.

        Returns:
            Formatted string with NPC visual descriptions.
        """
        entity_manager = EntityManager(self.db, self.game_session)
        npcs = entity_manager.get_npcs_in_scene(location_key)

        if not npcs:
            return ""

        descriptions = []
        for npc in npcs[:3]:  # Limit to 3 NPCs to stay within token budget
            parts = [npc.get_appearance_summary()]
            equipment = self._item_manager.format_outfit_description(npc.id)
            if equipment:
                parts.append(f"wearing {equipment}")
            if npc.npc_extension and npc.npc_extension.current_activity:
                parts.append(npc.npc_extension.current_activity)
            descriptions.append(f"- {npc.display_name}: {', '.join(parts)}")

        return "\n".join(descriptions)

    async def generate_scene_prompt(
        self,
        perspective: str = "pov",
        style: str = "photo",
    ) -> str:
        """Generate an image prompt for the current scene.

        Args:
            perspective: 'pov' for first-person, 'third' for third-person with player.
            style: 'photo' for photorealistic, 'art' for illustration.

        Returns:
            FLUX.1-dev optimized prompt string (~60 tokens).
        """
        # Get current location
        location_key = self._get_player_location()
        if not location_key:
            return "Fantasy scene, " + SCENE_STYLES.get(style, SCENE_STYLES["photo"])

        # Compile scene context
        scene = self._compiler.compile_scene(
            player_id=self.player.id,
            location_key=location_key,
            turn_number=self.game_session.total_turns or 1,
            include_secrets=False,
        )

        # Build player description for third-person view
        player_desc = ""
        if perspective == "third":
            player_desc = f"""
PLAYER CHARACTER (must be visible in scene):
- {self.player.display_name}: {self.player.get_appearance_summary()}
- Wearing: {self._item_manager.format_outfit_description(self.player.id) or 'simple clothing'}"""

        # Get NPC visual descriptions (not the full GM context)
        npcs_visual = self._get_npcs_visual_descriptions(location_key)

        user_prompt = f"""Generate a FLUX.1-dev scene prompt.

LOCATION: {scene.location_context}
TIME/WEATHER: {scene.time_context}
{player_desc}
NPCS IN SCENE (include their visual appearance, not just names):
{npcs_visual or 'None'}

PERSPECTIVE: {perspective} ({'first-person POV, viewer is the player' if perspective == 'pov' else 'third-person, player character visible in scene'})
STYLE SUFFIX: {SCENE_STYLES.get(style, SCENE_STYLES['photo'])}

IMPORTANT: Preserve character visual details (appearance, clothing colors/materials) for reproducibility. Do NOT just use names like "Marta" - describe what they look like.

Output ONLY the prompt (max 80 tokens for scenes with characters, 60 for empty scenes):"""

        return await self._generate(user_prompt)

    async def generate_portrait_prompt(
        self,
        mode: str = "current",
        style: str = "photo",
    ) -> str:
        """Generate an image prompt for a character portrait.

        Args:
            mode: 'base' for appearance only, 'current' for full state.
            style: 'photo' for photorealistic, 'art' for illustration.

        Returns:
            FLUX.1-dev optimized prompt string (~60 tokens).
        """
        # Base appearance
        appearance = self.player.get_appearance_summary()

        # Current state (if requested)
        equipment = ""
        condition = ""
        injuries = ""

        if mode == "current":
            equipment = self._item_manager.format_outfit_description(self.player.id)
            condition = self._compiler._get_needs_description(self.player.id, visible_only=True)
            injuries = self._compiler._get_injury_description(self.player.id, visible_only=True)

        user_prompt = f"""Generate a FLUX.1-dev character portrait prompt.

CHARACTER APPEARANCE: {appearance}
EQUIPMENT: {equipment or 'N/A' if mode == 'current' else 'Not included (base mode)'}
CONDITION: {condition or 'Normal' if mode == 'current' else 'Not included (base mode)'}
VISIBLE INJURIES: {injuries or 'None' if mode == 'current' else 'Not included (base mode)'}

MODE: {mode} ({'appearance only, neutral expression' if mode == 'base' else 'include equipment and reflect condition in expression'})
STYLE SUFFIX: {PORTRAIT_STYLES.get(style, PORTRAIT_STYLES['photo'])}

IMPORTANT: Preserve clothing visual details (colors, materials, details like buckles/belts) for reproducibility.

Output ONLY the prompt (max 70 tokens). Focus on face/upper body portrait framing:"""

        return await self._generate(user_prompt)

    async def _generate(self, user_prompt: str) -> str:
        """Call LLM to generate the prompt.

        Args:
            user_prompt: The formatted prompt for the LLM.

        Returns:
            Generated image prompt string.
        """
        provider = get_cheap_provider()
        system_prompt = _load_template()

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_prompt),
        ]

        response = await provider.complete(messages, max_tokens=150, temperature=0.7)

        # Clean up response - remove quotes if present
        result = response.content.strip()
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        if result.startswith("'") and result.endswith("'"):
            result = result[1:-1]

        return result


def estimate_tokens(text: str) -> int:
    """Rough estimate of CLIP tokens (words + punctuation).

    Args:
        text: The text to estimate.

    Returns:
        Estimated token count.
    """
    # Simple heuristic: split on spaces and commas
    parts = text.replace(",", " ").split()
    return len(parts)
