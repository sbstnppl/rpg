"""Tests for prompt templates."""

from pathlib import Path

import pytest


def get_templates_dir() -> Path:
    """Get the path to the templates directory."""
    return Path(__file__).parent.parent.parent / "data" / "templates"


class TestTemplateDirectory:
    """Tests for templates directory structure."""

    def test_templates_dir_exists(self):
        """Templates directory should exist."""
        templates_dir = get_templates_dir()
        assert templates_dir.exists()
        assert templates_dir.is_dir()


class TestGameMasterTemplate:
    """Tests for game_master.md template."""

    def test_game_master_template_exists(self):
        """game_master.md should exist."""
        template_path = get_templates_dir() / "game_master.md"
        assert template_path.exists()

    def test_game_master_has_scene_context_placeholder(self):
        """Should have {scene_context} placeholder."""
        template = (get_templates_dir() / "game_master.md").read_text()
        assert "{scene_context}" in template

    def test_game_master_has_player_input_placeholder(self):
        """Should have {player_input} placeholder."""
        template = (get_templates_dir() / "game_master.md").read_text()
        assert "{player_input}" in template

    def test_game_master_has_state_section(self):
        """Should have ---STATE--- output section."""
        template = (get_templates_dir() / "game_master.md").read_text()
        assert "---STATE---" in template


class TestEntityExtractorTemplate:
    """Tests for entity_extractor.md template."""

    def test_entity_extractor_template_exists(self):
        """entity_extractor.md should exist."""
        template_path = get_templates_dir() / "entity_extractor.md"
        assert template_path.exists()

    def test_entity_extractor_has_gm_response_placeholder(self):
        """Should have {gm_response} placeholder."""
        template = (get_templates_dir() / "entity_extractor.md").read_text()
        assert "{gm_response}" in template

    def test_entity_extractor_has_player_input_placeholder(self):
        """Should have {player_input} placeholder."""
        template = (get_templates_dir() / "entity_extractor.md").read_text()
        assert "{player_input}" in template


class TestWorldSimulatorTemplate:
    """Tests for world_simulator.md template."""

    def test_world_simulator_template_exists(self):
        """world_simulator.md should exist."""
        template_path = get_templates_dir() / "world_simulator.md"
        assert template_path.exists()

    def test_world_simulator_has_required_placeholders(self):
        """Should have all required placeholders."""
        template = (get_templates_dir() / "world_simulator.md").read_text()
        # Core simulation context
        assert "{time_state}" in template
        assert "{player_location}" in template
        assert "{hours_passed}" in template

    def test_world_simulator_has_output_section(self):
        """Should have structured output section."""
        template = (get_templates_dir() / "world_simulator.md").read_text()
        assert "---OUTPUT---" in template or "---STATE---" in template


class TestCombatResolverTemplate:
    """Tests for combat_resolver.md template."""

    def test_combat_resolver_template_exists(self):
        """combat_resolver.md should exist."""
        template_path = get_templates_dir() / "combat_resolver.md"
        assert template_path.exists()

    def test_combat_resolver_has_required_placeholders(self):
        """Should have all required placeholders."""
        template = (get_templates_dir() / "combat_resolver.md").read_text()
        # Combat state context
        assert "{combat_state}" in template
        assert "{current_combatant}" in template

    def test_combat_resolver_has_output_section(self):
        """Should have structured output section."""
        template = (get_templates_dir() / "combat_resolver.md").read_text()
        assert "---STATE---" in template or "---OUTPUT---" in template


class TestTemplateFormatting:
    """Tests for template formatting consistency."""

    @pytest.mark.parametrize(
        "template_name",
        ["game_master.md", "entity_extractor.md", "world_simulator.md", "combat_resolver.md"],
    )
    def test_template_has_title(self, template_name: str):
        """Each template should have a title (# header)."""
        template_path = get_templates_dir() / template_name
        template = template_path.read_text()
        assert template.startswith("#")

    @pytest.mark.parametrize(
        "template_name",
        ["game_master.md", "entity_extractor.md", "world_simulator.md", "combat_resolver.md"],
    )
    def test_template_uses_curly_brace_placeholders(self, template_name: str):
        """Templates should use {placeholder} format."""
        template_path = get_templates_dir() / template_name
        template = template_path.read_text()
        # At least one placeholder
        assert "{" in template and "}" in template
