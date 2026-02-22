"""Base agent class - shared Claude API tool-use loop."""

from __future__ import annotations

import json
import logging
from typing import Callable

import anthropic

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all pipeline agents. Implements the tool-use agentic loop."""

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-4-20250514-v2"):
        self.client = client
        self.model = model

    def run(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        tool_handlers: dict[str, Callable[..., str]],
        max_tokens: int = 4096,
        max_iterations: int = 25,
    ) -> str:
        """Execute the agent's tool-use loop and return the final text response.

        Args:
            system_prompt: The system message defining the agent's role.
            user_message: The task/input for the agent.
            tools: List of tool definition dicts (Anthropic format).
            tool_handlers: Map of tool_name -> callable that returns a string.
            max_tokens: Max tokens per API call.
            max_iterations: Safety limit on tool-use iterations.

        Returns:
            The final text response from the agent.
        """
        messages = [{"role": "user", "content": user_message}]

        for iteration in range(max_iterations):
            logger.debug(f"Agent iteration {iteration + 1}/{max_iterations}")

            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=messages,
                tools=tools if tools else [],
                max_tokens=max_tokens,
            )

            # Check if agent is done (no more tool calls)
            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            # Process tool calls
            tool_use_blocks = [
                block for block in response.content if block.type == "tool_use"
            ]

            if not tool_use_blocks:
                return self._extract_text(response)

            # Build assistant message with all content blocks
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call and collect results
            tool_results = []
            for tool_block in tool_use_blocks:
                tool_name = tool_block.name
                tool_input = tool_block.input

                logger.info(f"Tool call: {tool_name}({json.dumps(tool_input)[:200]}...)")

                handler = tool_handlers.get(tool_name)
                if handler:
                    try:
                        result = handler(**tool_input)
                    except Exception as e:
                        logger.error(f"Tool {tool_name} failed: {e}")
                        result = json.dumps({"error": f"Tool execution failed: {e}"})
                else:
                    result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        # If we hit max iterations, return whatever we have
        logger.warning(f"Agent hit max iterations ({max_iterations})")
        return self._extract_text(response)

    def _extract_text(self, response) -> str:
        """Extract text content from a Claude response."""
        text_blocks = [
            block.text for block in response.content if hasattr(block, "text")
        ]
        return "\n".join(text_blocks)

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> str:
        """Simple generation without tools (used by email composer)."""
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=max_tokens,
        )
        return self._extract_text(response)
