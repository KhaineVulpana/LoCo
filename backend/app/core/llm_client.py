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

# Default timeout for LLM requests (10 minutes for complex 3D mesh generation)
DEFAULT_LLM_TIMEOUT = 600


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
        max_tokens: Optional[int] = None,
        context_window: Optional[int] = None,
        response_format: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate streaming response from LLM

        Args:
            messages: Chat messages in OpenAI format
            tools: Optional tool definitions for function calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format hint (e.g., "json")

        Yields:
            Chunks of the response
        """
        if self.provider == "ollama":
            async for chunk in self._ollama_stream(messages, tools, temperature, max_tokens, context_window, response_format):
                yield chunk
        elif self.provider == "vllm":
            async for chunk in self._vllm_stream(messages, tools, temperature, max_tokens, context_window, response_format):
                yield chunk
        elif self.provider == "llamacpp":
            async for chunk in self._llamacpp_stream(messages, tools, temperature, max_tokens, context_window, response_format):
                yield chunk
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _ollama_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: Optional[int],
        context_window: Optional[int],
        response_format: Optional[str]
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
        if context_window:
            payload["options"]["num_ctx"] = context_window
        if response_format:
            payload["format"] = response_format

        # Ollama supports tools in newer versions
        if tools:
            payload["tools"] = tools
            logger.info("ollama_request",
                       model=self.model_name,
                       tool_count=len(tools),
                       has_system=any(m.get("role") == "system" for m in messages))

        # Use a long timeout for LLM responses (models can take minutes for complex tasks)
        timeout = aiohttp.ClientTimeout(total=DEFAULT_LLM_TIMEOUT, sock_read=DEFAULT_LLM_TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("ollama_error", status=response.status, error=error_text)
                        raise Exception(f"Ollama API error: {error_text}")

                    # Accumulate full content for XML parsing
                    accumulated_content = ""
                    has_native_tool_calls = False

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

                                    content = message.get("content", "")

                                    # Accumulate content for later XML parsing
                                    if content:
                                        accumulated_content += content
                                        # Stream raw content to user (will be cleaned up later if XML found)
                                        yield {
                                            "type": "content",
                                            "content": content
                                        }

                                    # Native tool calls (take precedence over XML)
                                    if "tool_calls" in message:
                                        has_native_tool_calls = True
                                        logger.info("tool_calls_received", count=len(message["tool_calls"]))
                                        for tool_call in message["tool_calls"]:
                                            yield {
                                                "type": "tool_call",
                                                "tool_call": tool_call
                                            }

                                # Check if done - parse XML here with full content
                                if data.get("done", False):
                                    # Try parsing XML tool calls from accumulated content
                                    if accumulated_content and not has_native_tool_calls:
                                        cleaned_content, xml_tool_calls = parse_xml_tool_calls(accumulated_content)
                                        if xml_tool_calls:
                                            logger.info("xml_tool_calls_parsed", count=len(xml_tool_calls))
                                            # Yield tool calls
                                            for tool_call in xml_tool_calls:
                                                yield {
                                                    "type": "tool_call",
                                                    "tool_call": tool_call
                                                }

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

        except aiohttp.ServerTimeoutError:
            logger.error("ollama_timeout", timeout=DEFAULT_LLM_TIMEOUT)
            raise Exception(f"Ollama request timed out after {DEFAULT_LLM_TIMEOUT} seconds")
        except aiohttp.ClientError as e:
            error_msg = str(e) if str(e) else type(e).__name__
            logger.error("ollama_connection_error", error=error_msg)
            raise Exception(f"Failed to connect to Ollama: {error_msg}")

    async def _vllm_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: Optional[int],
        context_window: Optional[int],
        response_format: Optional[str]
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

        timeout = aiohttp.ClientTimeout(total=DEFAULT_LLM_TIMEOUT, sock_read=DEFAULT_LLM_TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
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

        except aiohttp.ServerTimeoutError:
            logger.error("vllm_timeout", timeout=DEFAULT_LLM_TIMEOUT)
            raise Exception(f"vLLM request timed out after {DEFAULT_LLM_TIMEOUT} seconds")
        except aiohttp.ClientError as e:
            error_msg = str(e) if str(e) else type(e).__name__
            logger.error("vllm_connection_error", error=error_msg)
            raise Exception(f"Failed to connect to vLLM: {error_msg}")

    async def _llamacpp_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: Optional[int],
        context_window: Optional[int],
        response_format: Optional[str]
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

        timeout = aiohttp.ClientTimeout(total=DEFAULT_LLM_TIMEOUT, sock_read=DEFAULT_LLM_TIMEOUT)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
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

        except aiohttp.ServerTimeoutError:
            logger.error("llamacpp_timeout", timeout=DEFAULT_LLM_TIMEOUT)
            raise Exception(f"llama.cpp request timed out after {DEFAULT_LLM_TIMEOUT} seconds")
        except aiohttp.ClientError as e:
            error_msg = str(e) if str(e) else type(e).__name__
            logger.error("llamacpp_connection_error", error=error_msg)
            raise Exception(f"Failed to connect to llama.cpp: {error_msg}")
