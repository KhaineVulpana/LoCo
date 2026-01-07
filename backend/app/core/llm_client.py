"""
LLM Client for interfacing with Ollama, vLLM, and LlamaCPP
"""

import aiohttp
import json
import re
from typing import AsyncGenerator, Dict, List, Optional, Any
import structlog

from app.core.config import settings

logger = structlog.get_logger()


def parse_xml_tool_calls(content: str) -> tuple[str, List[Dict[str, Any]]]:
    """
    Parse XML-style tool calls from model output.
    Returns (cleaned_content, tool_calls)
    """
    tool_calls = []

    # Pattern to match <function=name> <parameter=key> value </parameter> ... </function>
    pattern = r'<function=(\w+)>(.*?)</function>'

    matches = list(re.finditer(pattern, content, re.DOTALL))

    for match in matches:
        func_name = match.group(1)
        params_text = match.group(2)

        # Extract parameters
        params = {}
        param_pattern = r'<parameter=(\w+)>\s*(.*?)\s*</parameter>'
        for param_match in re.finditer(param_pattern, params_text, re.DOTALL):
            param_name = param_match.group(1)
            param_value = param_match.group(2).strip()

            # Try to parse as boolean or keep as string
            if param_value.lower() == 'true':
                params[param_name] = True
            elif param_value.lower() == 'false':
                params[param_name] = False
            else:
                params[param_name] = param_value

        tool_calls.append({
            "id": f"call_{len(tool_calls)}",
            "function": {
                "name": func_name,
                "arguments": params
            }
        })

    # Remove XML tool calls from content
    cleaned_content = content
    for match in reversed(matches):
        cleaned_content = cleaned_content[:match.start()] + cleaned_content[match.end():]

    # Also remove orphaned </tool_call> tags
    cleaned_content = re.sub(r'</tool_call>', '', cleaned_content)
    cleaned_content = cleaned_content.strip()

    return cleaned_content, tool_calls


class LLMClient:
    """Client for interacting with various LLM providers"""

    def __init__(
        self,
        provider: str = None,
        model_name: str = None,
        base_url: str = None
    ):
        self.provider = provider or settings.MODEL_PROVIDER
        self.model_name = model_name or settings.MODEL_NAME
        self.base_url = base_url or settings.MODEL_URL

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate streaming response from LLM

        Args:
            messages: Chat messages in OpenAI format
            tools: Optional tool definitions for function calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Chunks of the response
        """
        if self.provider == "ollama":
            async for chunk in self._ollama_stream(messages, tools, temperature, max_tokens):
                yield chunk
        elif self.provider == "vllm":
            async for chunk in self._vllm_stream(messages, tools, temperature, max_tokens):
                yield chunk
        elif self.provider == "llamacpp":
            async for chunk in self._llamacpp_stream(messages, tools, temperature, max_tokens):
                yield chunk
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _ollama_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream from Ollama API"""
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            }
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        # Ollama supports tools in newer versions
        if tools:
            payload["tools"] = tools
            logger.info("ollama_request",
                       model=self.model_name,
                       tool_count=len(tools),
                       has_system=any(m.get("role") == "system" for m in messages))

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("ollama_error", status=response.status, error=error_text)
                        raise Exception(f"Ollama API error: {error_text}")

                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line)

                                # Ollama response format
                                if "message" in data:
                                    message = data["message"]

                                    # Debug logging
                                    logger.debug("ollama_message",
                                               has_content=bool(message.get("content")),
                                               has_tool_calls=bool(message.get("tool_calls")),
                                               content_preview=message.get("content", "")[:100] if message.get("content") else None)

                                    # Check for XML-style tool calls in content
                                    content = message.get("content", "")
                                    xml_tool_calls = []
                                    if content and not message.get("tool_calls"):
                                        # Try parsing XML tool calls
                                        cleaned_content, xml_tool_calls = parse_xml_tool_calls(content)
                                        if xml_tool_calls:
                                            logger.info("xml_tool_calls_parsed", count=len(xml_tool_calls))
                                            content = cleaned_content

                                    # Regular text response
                                    if content:
                                        yield {
                                            "type": "content",
                                            "content": content
                                        }

                                    # Native tool calls
                                    if "tool_calls" in message:
                                        logger.info("tool_calls_received", count=len(message["tool_calls"]))
                                        for tool_call in message["tool_calls"]:
                                            yield {
                                                "type": "tool_call",
                                                "tool_call": tool_call
                                            }

                                    # XML tool calls
                                    for tool_call in xml_tool_calls:
                                        yield {
                                            "type": "tool_call",
                                            "tool_call": tool_call
                                        }

                                # Check if done
                                if data.get("done", False):
                                    yield {
                                        "type": "done",
                                        "metadata": {
                                            "total_duration": data.get("total_duration"),
                                            "load_duration": data.get("load_duration"),
                                            "prompt_eval_count": data.get("prompt_eval_count"),
                                            "eval_count": data.get("eval_count")
                                        }
                                    }

                            except json.JSONDecodeError as e:
                                logger.warning("json_decode_error", error=str(e), line=line)
                                continue

        except aiohttp.ClientError as e:
            logger.error("ollama_connection_error", error=str(e))
            raise Exception(f"Failed to connect to Ollama: {str(e)}")

    async def _vllm_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream from vLLM OpenAI-compatible API"""
        url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("vllm_error", status=response.status, error=error_text)
                        raise Exception(f"vLLM API error: {error_text}")

                    async for line in response.content:
                        if line:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith("data: "):
                                line_str = line_str[6:]

                            if line_str == "[DONE]":
                                break

                            if not line_str:
                                continue

                            try:
                                data = json.loads(line_str)

                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})

                                    # Text content
                                    if "content" in delta and delta["content"]:
                                        yield {
                                            "type": "content",
                                            "content": delta["content"]
                                        }

                                    # Tool calls
                                    if "tool_calls" in delta:
                                        for tool_call in delta["tool_calls"]:
                                            yield {
                                                "type": "tool_call",
                                                "tool_call": tool_call
                                            }

                                    # Finish reason
                                    finish_reason = data["choices"][0].get("finish_reason")
                                    if finish_reason:
                                        yield {
                                            "type": "done",
                                            "metadata": {
                                                "finish_reason": finish_reason
                                            }
                                        }

                            except json.JSONDecodeError as e:
                                logger.warning("json_decode_error", error=str(e))
                                continue

        except aiohttp.ClientError as e:
            logger.error("vllm_connection_error", error=str(e))
            raise Exception(f"Failed to connect to vLLM: {str(e)}")

    async def _llamacpp_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream from llama.cpp server"""
        url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # llama.cpp may support tools depending on version
        if tools:
            payload["tools"] = tools

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("llamacpp_error", status=response.status, error=error_text)
                        raise Exception(f"llama.cpp API error: {error_text}")

                    async for line in response.content:
                        if line:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith("data: "):
                                line_str = line_str[6:]

                            if line_str == "[DONE]":
                                break

                            if not line_str:
                                continue

                            try:
                                data = json.loads(line_str)

                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})

                                    if "content" in delta and delta["content"]:
                                        yield {
                                            "type": "content",
                                            "content": delta["content"]
                                        }

                                    finish_reason = data["choices"][0].get("finish_reason")
                                    if finish_reason:
                                        yield {
                                            "type": "done",
                                            "metadata": {
                                                "finish_reason": finish_reason
                                            }
                                        }

                            except json.JSONDecodeError as e:
                                logger.warning("json_decode_error", error=str(e))
                                continue

        except aiohttp.ClientError as e:
            logger.error("llamacpp_connection_error", error=str(e))
            raise Exception(f"Failed to connect to llama.cpp: {str(e)}")
