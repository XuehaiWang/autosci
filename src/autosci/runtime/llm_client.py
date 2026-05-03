"""LLM client — unified interface to LLM providers.

Supported providers (protocol types):
    anthropic          Anthropic Messages API   → /v1/messages
    openai             OpenAI Chat Completions  → /v1/chat/completions
    openai-responses   OpenAI Responses API     → /v1/responses
    gemini             Google Gemini REST        → /v1beta/models/{model}:generateContent

Each provider has a default base_url (the official API endpoint).
Set base_url to use a custom/proxy endpoint while keeping the same protocol.
"""

import json
import logging
import os

from autosci.protocols.schemas import LLMResponse, ToolCall, TokenUsage

logger = logging.getLogger(__name__)


# ── Provider defaults ─────────────────────────────────────────────────────────

_PROVIDER_DEFAULTS = {
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com",
        "api_key_env": "OPENAI_API_KEY",
    },
    "openai-responses": {
        "base_url": "https://api.openai.com",
        "api_key_env": "OPENAI_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com",
        "api_key_env": "GEMINI_API_KEY",
    },
}


class LLMClient:
    """Unified LLM API client.

    Supports four protocol types: anthropic, openai, openai-responses, gemini.
    Each can be used with its official endpoint (default) or a custom base_url.
    """

    def __init__(self, config: dict):
        self.provider = config["provider"]
        if self.provider not in _PROVIDER_DEFAULTS:
            raise ValueError(
                f"Unsupported provider: {self.provider}. "
                f"Choose from: {', '.join(_PROVIDER_DEFAULTS)}"
            )

        defaults = _PROVIDER_DEFAULTS[self.provider]
        self.model = config["model"]
        self.max_tokens = config.get("max_tokens", 8192)
        self.base_url = (config.get("base_url") or defaults["base_url"]).rstrip("/")

        # Resolve API key
        api_key_env = config.get("api_key_env") or defaults["api_key_env"]
        self._api_key = os.environ.get(api_key_env) if api_key_env else None
        if not self._api_key:
            raise ValueError(f"API key not found. Set {api_key_env} environment variable.")

        # Initialize SDK clients for providers that use them
        self._client = None
        if self.provider == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
            self._client = anthropic.Anthropic(
                api_key=self._api_key,
                base_url=self.base_url if config.get("base_url") else None,
            )
        elif self.provider in ("openai", "openai-responses"):
            try:
                import openai
            except ImportError:
                raise ImportError("openai package required: pip install openai")
            self._client = openai.OpenAI(api_key=self._api_key, base_url=self.base_url)
        elif self.provider == "gemini":
            try:
                from google import genai
                from google.genai import types as genai_types
            except ImportError:
                raise ImportError("google-genai package required: pip install google-genai")
            http_options = None
            if config.get("base_url"):
                http_options = genai_types.HttpOptions(base_url=self.base_url)
            self._client = genai.Client(api_key=self._api_key, http_options=http_options)

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
        elif self.provider == "openai-responses":
            return self._call_openai_responses(messages, system, tools)
        elif self.provider == "gemini":
            return self._call_gemini(messages, system, tools)
        raise ValueError(f"Unsupported provider: {self.provider}")

    # ── Anthropic (/v1/messages) ──────────────────────────────────────────────

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

    # ── OpenAI Chat Completions (/v1/chat/completions) ────────────────────────

    def _call_openai(
        self,
        messages: list[dict],
        system: str = None,
        tools: list[dict] = None,
    ) -> LLMResponse:
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

        content = choice.message.content
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

    # ── OpenAI Responses API (/v1/responses) ──────────────────────────────────

    def _call_openai_responses(
        self,
        messages: list[dict],
        system: str = None,
        tools: list[dict] = None,
    ) -> LLMResponse:
        # Build input items from Anthropic-style messages
        input_items = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content")

            if isinstance(content, str):
                input_items.append({"role": role, "content": content})
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        input_items.append({"role": role, "content": block["text"]})
                    elif block.get("type") == "tool_use":
                        input_items.append({
                            "type": "function_call",
                            "call_id": block["id"],
                            "name": block["name"],
                            "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                        })
                    elif block.get("type") == "tool_result":
                        input_items.append({
                            "type": "function_call_output",
                            "call_id": block["tool_use_id"],
                            "output": block["content"] if isinstance(block["content"], str)
                                      else json.dumps(block["content"], ensure_ascii=False),
                        })

        kwargs = {
            "model": self.model,
            "input": input_items,
        }
        if system:
            kwargs["instructions"] = system
        if self.max_tokens:
            kwargs["max_output_tokens"] = self.max_tokens
        if tools:
            kwargs["tools"] = self._convert_tools_to_responses(tools)

        response = self._client.responses.create(**kwargs)

        # Parse output items
        content = None
        tool_calls = None
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if part.type == "output_text":
                        content = (content or "") + part.text
            elif item.type == "function_call":
                if tool_calls is None:
                    tool_calls = []
                args = item.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                tool_calls.append(ToolCall(
                    id=item.call_id,
                    name=item.name,
                    arguments=args,
                ))

        # Parse usage
        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens or 0,
                completion_tokens=response.usage.output_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=response.status or "",
        )

    def _convert_tools_to_responses(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool schemas to OpenAI Responses API function format."""
        result = []
        for tool in tools:
            result.append({
                "type": "function",
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            })
        return result

    # ── Shared OpenAI format converters ───────────────────────────────────────

    def _convert_message_to_openai(self, msg: dict) -> dict | list:
        """Convert Anthropic-style messages to OpenAI format."""
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            return {"role": role, "content": content}

        if isinstance(content, list):
            if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                return self._convert_tool_results_to_openai(content)
            if role == "assistant":
                return self._convert_assistant_content_to_openai(content)

        return {"role": role, "content": str(content)}

    def _convert_assistant_content_to_openai(self, content: list) -> dict:
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
        messages = []
        for block in content:
            messages.append({
                "role": "tool",
                "tool_call_id": block["tool_use_id"],
                "content": block["content"] if isinstance(block["content"], str) else json.dumps(block["content"]),
            })
        return messages

    def _convert_tools_to_openai(self, tools: list[dict]) -> list[dict]:
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

    # ── Gemini (/v1beta/models/{model}:generateContent) ───────────────────────

    def _call_gemini(
        self,
        messages: list[dict],
        system: str = None,
        tools: list[dict] = None,
    ) -> LLMResponse:
        from google.genai import types as genai_types

        # Build contents from Anthropic-style messages
        contents = self._build_gemini_contents(messages)

        # Build config
        config = genai_types.GenerateContentConfig(
            max_output_tokens=self.max_tokens,
        )
        if system:
            config.system_instruction = system
        if tools:
            config.tools = [genai_types.Tool(
                function_declarations=self._build_gemini_tools(tools),
            )]

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        # Parse response
        content = None
        tool_calls = None

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text and not part.thought:
                        content = (content or "") + part.text
                    elif part.function_call:
                        if tool_calls is None:
                            tool_calls = []
                        tool_calls.append(ToolCall(
                            id=part.function_call.id or f"gemini_tc_{len(tool_calls)}",
                            name=part.function_call.name,
                            arguments=part.function_call.args or {},
                        ))

            finish_reason = str(candidate.finish_reason) if candidate.finish_reason else ""
        else:
            finish_reason = ""

        # Parse usage
        usage = TokenUsage()
        if response.usage_metadata:
            um = response.usage_metadata
            usage = TokenUsage(
                prompt_tokens=um.prompt_token_count or 0,
                completion_tokens=um.candidates_token_count or 0,
                total_tokens=um.total_token_count or 0,
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
        )

    def _build_gemini_contents(self, messages: list[dict]) -> list:
        """Convert Anthropic-style messages to Gemini Content objects."""
        from google.genai import types as genai_types

        # Build tool_use_id → name mapping so tool_result blocks get correct names
        tc_id_to_name: dict[str, str] = {}
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tc_id_to_name[block["id"]] = block["name"]

        contents = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content")
            gemini_role = "model" if role == "assistant" else "user"

            if isinstance(content, str):
                contents.append(genai_types.Content(
                    role=gemini_role,
                    parts=[genai_types.Part(text=content)],
                ))
                continue

            if isinstance(content, list):
                parts = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type")
                    if block_type == "text":
                        parts.append(genai_types.Part(text=block["text"]))
                    elif block_type == "tool_use":
                        parts.append(genai_types.Part(
                            function_call=genai_types.FunctionCall(
                                name=block["name"],
                                args=block.get("input", {}),
                            ),
                        ))
                    elif block_type == "tool_result":
                        result_content = block.get("content", "")
                        if isinstance(result_content, list):
                            text_parts = [b.get("text", "") for b in result_content if isinstance(b, dict)]
                            result_content = "\n".join(text_parts)
                        tool_use_id = block.get("tool_use_id", "")
                        func_name = tc_id_to_name.get(tool_use_id, block.get("name", "unknown"))
                        parts.append(genai_types.Part(
                            function_response=genai_types.FunctionResponse(
                                name=func_name,
                                response={"result": result_content},
                            ),
                        ))
                if parts:
                    contents.append(genai_types.Content(role=gemini_role, parts=parts))
                continue

            contents.append(genai_types.Content(
                role=gemini_role,
                parts=[genai_types.Part(text=str(content))],
            ))

        return contents

    def _build_gemini_tools(self, tools: list[dict]) -> list:
        """Convert Anthropic tool schemas to Gemini FunctionDeclaration objects."""
        from google.genai import types as genai_types

        declarations = []
        for tool in tools:
            declarations.append(genai_types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=tool.get("input_schema", {}),
            ))
        return declarations