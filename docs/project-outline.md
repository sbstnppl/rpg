# RPG Game Project Outline

## Vision

An agentic console-based role-playing game that provides a rich, immersive narrative experience with consistent world state tracking. The game uses AI to drive storytelling while maintaining a coherent world where actions have consequences.

## Core Principles

1. **Consistent World State**: Every entity (characters, items, locations) has a persistent state that evolves over time
2. **Player Agency**: Players can do anything; the AI adapts to their choices
3. **Meaningful Relationships**: NPCs remember interactions and relationships develop naturally
4. **Time Matters**: The world continues even when the player isn't present
5. **Flexible Settings**: Support fantasy, contemporary, sci-fi, or any custom setting

## Key Features

### Characters
- **Player Character**: Customizable with AI-assisted creation
- **NPCs**: Rich personalities, schedules, jobs, hobbies, relationships
- **Monsters/Animals**: Combat-ready with loot tables

### World Simulation
- **Time System**: In-game clock with day/night cycles
- **NPC Schedules**: Rule-based routines (bartender works evenings, etc.)
- **Dynamic Events**: AI-generated occurrences (robberies, weather, discoveries)
- **Location Persistence**: Places remember their state between visits

### Inventory & Equipment
- **Body Slots with Layers**: Realistic clothing/armor system
- **Owner vs Holder**: Items can be borrowed/lent
- **Condition System**: Items degrade and can break

### Relationships
- **4-Dimension Attitudes**: Trust, Liking, Respect, Romantic Interest (0-100)
- **Memory**: NPCs remember what the player did
- **Consequences**: Actions affect how NPCs treat the player

### Combat
- **Dice-Based**: D&D-style mechanics with dice rolls
- **Attribute Checks**: Skill/attribute tests for various actions
- **Loot System**: Defeated enemies drop items

### Tasks & Quests
- **Appointments**: Scheduled meetings with NPCs
- **Goals**: Open-ended objectives
- **Quests**: Multi-stage story arcs

## Target Platforms

- **Phase 1**: Console CLI (Typer + Rich)
- **Phase 2**: Web UI (future)

## Tech Stack

- **Backend**: Python 3.11+
- **AI Framework**: LangGraph (multi-agent)
- **Database**: PostgreSQL with SQLAlchemy
- **LLM**: Anthropic Claude + OpenAI GPT (dual support)
- **CLI**: Typer + Rich

## Non-Goals (Out of Scope)

- Multiplayer support
- Real-time gameplay
- Graphics/visual assets
- Mobile app
