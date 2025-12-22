"""Simplified GM Pipeline.

This module implements a single-call GM approach where:
1. ContextBuilder gathers rich context
2. GM LLM generates narrative + structured output with tools
3. Validator checks grounding
4. Applier persists state changes
"""
