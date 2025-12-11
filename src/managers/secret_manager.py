"""Secret Manager for NPC secrets, revelations, and dramatic intrigue.

This manager handles NPC secrets that create engagement through:
- Dark secrets that can be discovered
- Hidden goals that may conflict with stated goals
- Betrayal conditions that trigger dramatic moments
- Revelation tracking and GM alerts
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.database.models.entities import Entity, NPCExtension
from src.database.models.enums import EntityType
from src.database.models.session import GameSession
from src.managers.base import BaseManager


@dataclass
class NPCSecret:
    """A secret held by an NPC."""

    entity_key: str
    display_name: str
    dark_secret: str | None
    hidden_goal: str | None
    betrayal_conditions: str | None
    is_revealed: bool
    revealed_turn: int | None


@dataclass
class SecretRevealAlert:
    """Alert for GM when conditions for secret reveal are met."""

    entity_key: str
    display_name: str
    secret_type: str  # "dark_secret", "hidden_goal", "betrayal"
    secret_content: str
    trigger_reason: str


@dataclass
class BetrayalRisk:
    """Assessment of betrayal risk for an NPC."""

    entity_key: str
    display_name: str
    betrayal_conditions: str
    risk_level: str  # "low", "medium", "high", "imminent"
    current_situation: str | None = None


class SecretManager(BaseManager):
    """Manages NPC secrets and dramatic revelations.

    NPC secrets create intrigue by:
    - Tracking dark secrets that can be discovered
    - Managing hidden goals that may differ from stated ones
    - Monitoring betrayal conditions
    - Alerting GM when revelation conditions are met
    """

    def set_dark_secret(
        self,
        entity_key: str,
        secret: str,
    ) -> NPCExtension:
        """Set or update an NPC's dark secret.

        Args:
            entity_key: Entity key of the NPC.
            secret: The secret being hidden.

        Returns:
            The updated NPCExtension.

        Raises:
            ValueError: If entity not found or not an NPC.
        """
        npc_ext = self._get_npc_extension(entity_key)
        npc_ext.dark_secret = secret
        npc_ext.secret_revealed = False
        npc_ext.secret_revealed_turn = None

        self.db.commit()
        self.db.refresh(npc_ext)
        return npc_ext

    def set_hidden_goal(
        self,
        entity_key: str,
        goal: str,
    ) -> NPCExtension:
        """Set or update an NPC's hidden goal.

        Args:
            entity_key: Entity key of the NPC.
            goal: The true goal (may differ from stated goals).

        Returns:
            The updated NPCExtension.

        Raises:
            ValueError: If entity not found or not an NPC.
        """
        npc_ext = self._get_npc_extension(entity_key)
        npc_ext.hidden_goal = goal

        self.db.commit()
        self.db.refresh(npc_ext)
        return npc_ext

    def set_betrayal_conditions(
        self,
        entity_key: str,
        conditions: str,
    ) -> NPCExtension:
        """Set or update an NPC's betrayal conditions.

        Args:
            entity_key: Entity key of the NPC.
            conditions: What would cause this NPC to betray the player.

        Returns:
            The updated NPCExtension.

        Raises:
            ValueError: If entity not found or not an NPC.
        """
        npc_ext = self._get_npc_extension(entity_key)
        npc_ext.betrayal_conditions = conditions

        self.db.commit()
        self.db.refresh(npc_ext)
        return npc_ext

    def reveal_secret(
        self,
        entity_key: str,
    ) -> NPCExtension:
        """Mark an NPC's dark secret as revealed.

        Args:
            entity_key: Entity key of the NPC.

        Returns:
            The updated NPCExtension.

        Raises:
            ValueError: If entity not found or not an NPC.
        """
        npc_ext = self._get_npc_extension(entity_key)
        npc_ext.secret_revealed = True
        npc_ext.secret_revealed_turn = self.current_turn

        self.db.commit()
        self.db.refresh(npc_ext)
        return npc_ext

    def get_npc_secret(self, entity_key: str) -> NPCSecret | None:
        """Get an NPC's secret information.

        Args:
            entity_key: Entity key of the NPC.

        Returns:
            NPCSecret if found, None otherwise.
        """
        entity = self._get_entity(entity_key)
        if not entity or not entity.npc_extension:
            return None

        ext = entity.npc_extension
        return NPCSecret(
            entity_key=entity.entity_key,
            display_name=entity.display_name,
            dark_secret=ext.dark_secret,
            hidden_goal=ext.hidden_goal,
            betrayal_conditions=ext.betrayal_conditions,
            is_revealed=ext.secret_revealed,
            revealed_turn=ext.secret_revealed_turn,
        )

    def get_npcs_with_secrets(self) -> list[NPCSecret]:
        """Get all NPCs that have any secrets defined.

        Returns:
            List of NPCSecret objects.
        """
        # Query NPCs with any secret field populated
        npcs = (
            self.db.query(Entity)
            .join(NPCExtension)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_type == EntityType.NPC,
                    (
                        (NPCExtension.dark_secret.isnot(None))
                        | (NPCExtension.hidden_goal.isnot(None))
                        | (NPCExtension.betrayal_conditions.isnot(None))
                    ),
                )
            )
            .all()
        )

        return [
            NPCSecret(
                entity_key=npc.entity_key,
                display_name=npc.display_name,
                dark_secret=npc.npc_extension.dark_secret,
                hidden_goal=npc.npc_extension.hidden_goal,
                betrayal_conditions=npc.npc_extension.betrayal_conditions,
                is_revealed=npc.npc_extension.secret_revealed,
                revealed_turn=npc.npc_extension.secret_revealed_turn,
            )
            for npc in npcs
        ]

    def get_unrevealed_secrets(self) -> list[NPCSecret]:
        """Get all NPCs with unrevealed dark secrets.

        Returns:
            List of NPCSecret objects with unrevealed secrets.
        """
        npcs = (
            self.db.query(Entity)
            .join(NPCExtension)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_type == EntityType.NPC,
                    NPCExtension.dark_secret.isnot(None),
                    NPCExtension.secret_revealed == False,  # noqa: E712
                )
            )
            .all()
        )

        return [
            NPCSecret(
                entity_key=npc.entity_key,
                display_name=npc.display_name,
                dark_secret=npc.npc_extension.dark_secret,
                hidden_goal=npc.npc_extension.hidden_goal,
                betrayal_conditions=npc.npc_extension.betrayal_conditions,
                is_revealed=False,
                revealed_turn=None,
            )
            for npc in npcs
        ]

    def get_npcs_with_betrayal_conditions(self) -> list[NPCSecret]:
        """Get all NPCs that have betrayal conditions defined.

        Returns:
            List of NPCSecret objects with betrayal conditions.
        """
        npcs = (
            self.db.query(Entity)
            .join(NPCExtension)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_type == EntityType.NPC,
                    NPCExtension.betrayal_conditions.isnot(None),
                )
            )
            .all()
        )

        return [
            NPCSecret(
                entity_key=npc.entity_key,
                display_name=npc.display_name,
                dark_secret=npc.npc_extension.dark_secret,
                hidden_goal=npc.npc_extension.hidden_goal,
                betrayal_conditions=npc.npc_extension.betrayal_conditions,
                is_revealed=npc.npc_extension.secret_revealed,
                revealed_turn=npc.npc_extension.secret_revealed_turn,
            )
            for npc in npcs
        ]

    def check_betrayal_triggers(
        self,
        situation_keywords: list[str],
    ) -> list[BetrayalRisk]:
        """Check if current situation might trigger any betrayals.

        This is a simple keyword-based check. For more sophisticated
        checking, use LLM-based analysis.

        Args:
            situation_keywords: Keywords describing current situation.

        Returns:
            List of NPCs at risk of betrayal.
        """
        npcs_with_betrayal = self.get_npcs_with_betrayal_conditions()
        risks: list[BetrayalRisk] = []

        for npc in npcs_with_betrayal:
            if not npc.betrayal_conditions:
                continue

            # Simple keyword matching
            conditions_lower = npc.betrayal_conditions.lower()
            matching_keywords = [
                kw for kw in situation_keywords
                if kw.lower() in conditions_lower
            ]

            if matching_keywords:
                risk_level = "low"
                if len(matching_keywords) >= 3:
                    risk_level = "imminent"
                elif len(matching_keywords) >= 2:
                    risk_level = "high"
                elif len(matching_keywords) >= 1:
                    risk_level = "medium"

                risks.append(BetrayalRisk(
                    entity_key=npc.entity_key,
                    display_name=npc.display_name,
                    betrayal_conditions=npc.betrayal_conditions,
                    risk_level=risk_level,
                    current_situation=", ".join(matching_keywords),
                ))

        return risks

    def generate_secret_reveal_alerts(
        self,
        trigger_context: str,
    ) -> list[SecretRevealAlert]:
        """Generate alerts for potential secret reveals based on context.

        Args:
            trigger_context: Description of current situation/context.

        Returns:
            List of alerts for secrets that might be revealed.
        """
        alerts: list[SecretRevealAlert] = []
        context_lower = trigger_context.lower()

        for npc in self.get_unrevealed_secrets():
            # Check if context might trigger secret reveal
            if npc.dark_secret:
                secret_keywords = npc.dark_secret.lower().split()
                # Simple check: if context contains words from secret
                matches = sum(1 for kw in secret_keywords if len(kw) > 4 and kw in context_lower)
                if matches >= 2:
                    alerts.append(SecretRevealAlert(
                        entity_key=npc.entity_key,
                        display_name=npc.display_name,
                        secret_type="dark_secret",
                        secret_content=npc.dark_secret,
                        trigger_reason=f"Context contains related keywords",
                    ))

        return alerts

    def get_secrets_context(self) -> str:
        """Generate GM context for NPC secrets.

        Returns:
            Formatted string with secret summaries for GM.
        """
        secrets = self.get_npcs_with_secrets()
        if not secrets:
            return ""

        lines = ["## NPC Secrets (GM Only)"]
        for secret in secrets:
            lines.append(f"\n### {secret.display_name}")
            if secret.dark_secret:
                status = "REVEALED" if secret.is_revealed else "hidden"
                lines.append(f"Dark Secret [{status}]: {secret.dark_secret}")
            if secret.hidden_goal:
                lines.append(f"Hidden Goal: {secret.hidden_goal}")
            if secret.betrayal_conditions:
                lines.append(f"Betrayal Triggers: {secret.betrayal_conditions}")

        return "\n".join(lines)

    def get_betrayal_risks_context(
        self,
        situation_keywords: list[str] | None = None,
    ) -> str:
        """Generate GM context for betrayal risks.

        Args:
            situation_keywords: Optional keywords to check triggers.

        Returns:
            Formatted string with betrayal risk assessment.
        """
        if not situation_keywords:
            npcs = self.get_npcs_with_betrayal_conditions()
            if not npcs:
                return ""

            lines = ["## Potential Betrayals"]
            for npc in npcs:
                lines.append(f"- {npc.display_name}: {npc.betrayal_conditions}")
            return "\n".join(lines)

        risks = self.check_betrayal_triggers(situation_keywords)
        if not risks:
            return ""

        lines = ["## Betrayal Risk Assessment"]
        for risk in sorted(risks, key=lambda r: {"imminent": 0, "high": 1, "medium": 2, "low": 3}[r.risk_level]):
            lines.append(f"\n### {risk.display_name} - {risk.risk_level.upper()} RISK")
            lines.append(f"Conditions: {risk.betrayal_conditions}")
            if risk.current_situation:
                lines.append(f"Triggered by: {risk.current_situation}")

        return "\n".join(lines)

    def _get_entity(self, entity_key: str) -> Entity | None:
        """Get an entity by key.

        Args:
            entity_key: Entity key.

        Returns:
            Entity if found, None otherwise.
        """
        return (
            self.db.query(Entity)
            .filter(
                and_(
                    Entity.session_id == self.session_id,
                    Entity.entity_key == entity_key,
                )
            )
            .first()
        )

    def _get_npc_extension(self, entity_key: str) -> NPCExtension:
        """Get NPC extension, creating if needed.

        Args:
            entity_key: Entity key.

        Returns:
            NPCExtension for the entity.

        Raises:
            ValueError: If entity not found or not an NPC.
        """
        entity = self._get_entity(entity_key)
        if not entity:
            raise ValueError(f"Entity '{entity_key}' not found")

        if entity.entity_type != EntityType.NPC:
            raise ValueError(f"Entity '{entity_key}' is not an NPC")

        if not entity.npc_extension:
            # Create NPCExtension if it doesn't exist
            ext = NPCExtension(entity_id=entity.id)
            self.db.add(ext)
            self.db.commit()
            self.db.refresh(entity)

        return entity.npc_extension
