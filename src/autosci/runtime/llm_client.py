"""LLM client — unified interface to LLM providers."""

import json
import logging
import os

from autosci.protocols.schemas import LLMResponse, ToolCall, TokenUsage

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM API client.

    Supports:
    - anthropic: native Anthropic API
    - openai: OpenAI-compatible endpoints (OpenAI, Tuzi, vLLM, etc.)
    """

    def __init__(self, config: dict):
        self.provider = config["provider"]
        self.model = config["model"]
        self.max_tokens = config.get("max_tokens", 8192)
        self._client = None
        self._init_client(config)

    def _init_client(self, config: dict) -> None:
        api_key_env = config.get("api_key_env", "")
        api_key = os.environ.get(api_key_env) if api_key_env else None

        if self.provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
            if not api_key:
                raise ValueError(f"API key not found. Set {api_key_env} environment variable.")
            self._client = anthropic.Anthropic(api_key=api_key)

        elif self.provider == "openai":
            try:
                import openai
            except ImportError:
                raise ImportError("openai package required: pip install openai")
            if not api_key:
                raise ValueError(f"API key not found. Set {api_key_env} environment variable.")
            base_url = config.get("base_url")
            self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def chat(
        self,
        messages: list[dict],
        system: str = None,
        tools: list[dict] = None,
    ) -> LLMResponse:
        """Send a chat request to the LLM and return a structured response."""
        if self.provider == "anthropic":
            return self._call_anthropic(messages, system, tools)
        elif self.provider == "openai":
            return self._call_openai(messages, system, tools)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _call_anthropic(
        self,
        messages: list[dict],
        system: str = None,
        tools: list[dict] = None,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)

        content = None
        tool_calls = None
        for block in response.content:
            if block.type == "text":
                content = (content or "") + block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )
        return LLMResponse(
            content=content, tool_calls=tool_calls,
            usage=usage, finish_reason=response.stop_reason or "",
        )

    def _call_openai(
        self,
        messages: list[dict],
        system: str = None,
        tools: list[dict] = None,
    ) -> LLMResponse:
        # Build messages with system prompt
        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})

        for msg in messages:
            converted = self._convert_message_to_openai(msg)
            if isinstance(converted, list):
                api_messages.extend(converted)
            else:
                api_messages.append(converted)

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": api_messages,
        }
        if tools:
            kwargs["tools"] = self._convert_tools_to_openai(tools)

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        # Parse content
        content = choice.message.content

        # Parse tool calls
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = []
            for tc in choice.message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        # Parse usage
        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        return LLMResponse(
            content=content, tool_calls=tool_calls,
            usage=usage, finish_reason=choice.finish_reason or "",
        )

    def _convert_message_to_openai(self, msg: dict) -> dict:
        """Convert Anthropic-style messages to OpenAI format."""
        role = msg["role"]
        content = msg["content"]

        # Simple string content
        if isinstance(content, str):
            return {"role": role, "content": content}

        # List content (tool_use / tool_result blocks)
        if isinstance(content, list):
            # Check if it's tool results (from user role)
            if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                # Convert to OpenAI tool messages
                # Return as a list marker — handled specially
                return self._convert_tool_results_to_openai(content)

            # Check if it's assistant content with tool_use
            if role == "assistant":
                return self._convert_assistant_content_to_openai(content)

        return {"role": role, "content": str(content)}

    def _convert_assistant_content_to_openai(self, content: list) -> dict:
        """Convert Anthropic assistant content blocks to OpenAI format."""
        text_parts = []
        tool_calls = []

        for block in content:
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"], ensure_ascii=False),
                    },
                })

        msg = {"role": "assistant", "content": "\n".join(text_parts) if text_parts else None}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return msg

    def _convert_tool_results_to_openai(self, content: list) -> list:
        """Convert Anthropic tool_result blocks to OpenAI tool messages.

        Returns a list of messages (one per tool result).
        """
        messages = []
        for block in content:
            messages.append({
                "role": "tool",
                "tool_call_id": block["tool_use_id"],
                "content": block["content"] if isinstance(block["content"], str) else json.dumps(block["content"]),
            })
        return messages

    def _convert_tools_to_openai(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool schemas to OpenAI function format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        return openai_tools
