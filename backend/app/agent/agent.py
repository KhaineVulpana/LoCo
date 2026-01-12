"""
Main agent implementation with agentic loop
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
import structlog
import pathspec

from sqlalchemy import text

from app.core.llm_client import LLMClient
from app.core.isolated_llm_client import IsolatedLLMClient
from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.core.model_manager import ModelManager
from app.retrieval.retriever import Retriever
from app.core.config import settings
from app.tools.base import ToolRegistry
from app.tools import ReadFileTool, WriteFileTool, ListFilesTool, ApplyPatchTool, RunCommandTool, RunTestsTool
from app.tools import ReportPlanTool, ProposePatchTool, ProposeDiffTool
from app.ace import Playbook, Reflector, Curator

logger = structlog.get_logger()


class Agent:
    """Main coding agent with tool calling capabilities"""

    def __init__(
        self,
        workspace_path: str,
        frontend_id: str = "vscode",  # Which frontend is using this agent
        workspace_id: Optional[str] = None,
        db_session_maker: Optional[Any] = None,
        model_manager: Optional[ModelManager] = None,
        embedding_manager: Optional[EmbeddingManager] = None,
        vector_store: Optional[VectorStore] = None,
        enable_ace: bool = True  # Re-enabled after fixing duplicate response issue with IsolatedLLMClient
    ):
        self.workspace_path = workspace_path
        self.frontend_id = frontend_id
        self.workspace_id = workspace_id
        self.db_session_maker = db_session_maker
        self.ace_collection = f"loco_ace_{frontend_id}"
        self.model_manager = model_manager
        self.tool_registry = ToolRegistry()
        self.conversation_history: List[Dict[str, str]] = []
        self.max_iterations = 10  # Prevent infinite loops

        # RAG components
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
        self.retriever = None

        if embedding_manager and vector_store:
            self.retriever = Retriever(
                frontend_id=frontend_id,
                embedding_manager=embedding_manager,
                vector_store=vector_store,
                db_session_maker=db_session_maker,
                workspace_path=workspace_path
            )
            logger.info("rag_enabled", frontend_id=frontend_id)
        else:
            logger.warning("rag_disabled", reason="No embedding manager or vector store provided")

        # ACE components
        self.enable_ace = enable_ace
        self.playbook = None
        if enable_ace:
            if embedding_manager and vector_store:
                try:
                    self.playbook = Playbook.load_from_vector_db(
                        vector_store=vector_store,
                        collection_name=self.ace_collection
                    )
                    logger.info("ace_playbook_loaded",
                               frontend_id=frontend_id,
                               bullets=self.playbook.get_bullet_count())
                except Exception as e:
                    logger.error("ace_playbook_load_failed",
                                frontend_id=frontend_id,
                                error=str(e))
                    self.playbook = Playbook()
            else:
                self.playbook = Playbook()

        # Note: Reflector and Curator are created per-interaction
        # because they need an LLMClient from the model_manager
        self._used_bullet_ids: List[str] = []
        self._ace_lock: Optional[asyncio.Lock] = None
        self._pending_approvals: Dict[str, asyncio.Future] = {}

        # Initialize and register tools
        self._init_tools()

        # System prompt - qwen3-coder doesn't support tool calling with system prompts
        # Keep empty for coding frontends; add 3d-gen guidance for mesh output.
        self.system_prompt = ""
        if self.frontend_id == "3d-gen":
            self.system_prompt = (
                "You are the LoCo 3D-Gen assistant. Use retrieved examples to derive geometry, "
                "and return a mesh preview plus optional Unity C# code. "
                "Respond with a short summary, then include a JSON code block with this shape:\n\n"
                "```json\n"
                "{\n"
                "  \"mesh\": {\n"
                "    \"vertices\": [[x, y, z], ...],\n"
                "    \"triangles\": [[i0, i1, i2], ...],\n"
                "    \"normals\": [[x, y, z], ...],\n"
                "    \"uvs\": [[u, v], ...]\n"
                "  },\n"
                "  \"csharp_code\": \"Unity C# script or empty string\",\n"
                "  \"notes\": \"brief constraints or next steps\"\n"
                "}\n"
                "```\n\n"
                "Rules: vertices are meters, triangles use zero-based indices, keep meshes compact, "
                "and include normals/uvs when possible."
            )

    def _get_llm_client(self) -> Optional[LLMClient]:
        """
        Get current LLM client from model manager

        Returns:
            LLMClient if model is loaded, None otherwise
        """
        if not self.model_manager:
            logger.error("no_model_manager", frontend_id=self.frontend_id)
            return None

        return self.model_manager.get_current_model()

    def _truncate_text(self, text: str, limit: int = 1000) -> str:
        """Truncate text for logging/trajectory summaries."""
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...(truncated)"

    async def _run_ace_learning(
        self,
        task: str,
        trajectory: str,
        outcome: Dict[str, Any],
        used_bullet_ids: Optional[List[str]]
    ) -> None:
        if self._ace_lock is None:
            self._ace_lock = asyncio.Lock()
        async with self._ace_lock:
            await self.learn_from_interaction(
                task=task,
                trajectory=trajectory,
                outcome=outcome,
                used_bullet_ids=used_bullet_ids
            )

    def _log_ace_task_error(self, task: asyncio.Task) -> None:
        """Log errors from background ACE tasks."""
        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return
        if exc:
            logger.error("ace_learning_failed", error=str(exc))

    def _schedule_ace_learning(
        self,
        task: str,
        trajectory: str,
        outcome: Dict[str, Any],
        used_bullet_ids: Optional[List[str]]
    ) -> None:
        """Schedule ACE learning without blocking the response stream."""
        if not self.enable_ace:
            return
        try:
            ace_task = asyncio.create_task(
                self._run_ace_learning(task, trajectory, outcome, used_bullet_ids)
            )
            ace_task.add_done_callback(self._log_ace_task_error)
        except Exception as e:
            logger.error("ace_learning_schedule_failed", error=str(e))

    async def _get_workspace_policy(self) -> Dict[str, Any]:
        default_policy = {
            "command_approval": "prompt",
            "allowed_commands": [],
            "blocked_commands": [],
            "auto_approve_tests": False,
            "auto_approve_simple_changes": False,
            "allowed_read_globs": ["**/*"],
            "allowed_write_globs": ["**/*"],
            "blocked_globs": [".git/**", "node_modules/**"],
            "network_enabled": False
        }
        if not self.db_session_maker or not self.workspace_id:
            default_policy["read_spec"] = self._build_glob_spec(default_policy["allowed_read_globs"])
            default_policy["write_spec"] = self._build_glob_spec(default_policy["allowed_write_globs"])
            default_policy["block_spec"] = self._build_glob_spec(default_policy["blocked_globs"])
            return default_policy

        async with self.db_session_maker() as session:
            result = await session.execute(text("""
                SELECT command_approval, allowed_commands, blocked_commands,
                       auto_approve_tests, auto_approve_simple_changes,
                       allowed_read_globs, allowed_write_globs, blocked_globs,
                       network_enabled
                FROM workspace_policies
                WHERE workspace_id = :workspace_id
            """), {"workspace_id": self.workspace_id})
            row = result.fetchone()

        if not row:
            return default_policy

        (
            command_approval,
            allowed_commands,
            blocked_commands,
            auto_tests,
            auto_simple,
            allowed_read_globs,
            allowed_write_globs,
            blocked_globs,
            network_enabled
        ) = row

        def _parse_list(value: Optional[str], fallback: List[str]) -> List[str]:
            if not value:
                return fallback
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else fallback
            except json.JSONDecodeError:
                return fallback

        policy = {
            "command_approval": command_approval or "prompt",
            "allowed_commands": _parse_list(allowed_commands, []),
            "blocked_commands": _parse_list(blocked_commands, []),
            "auto_approve_tests": bool(auto_tests),
            "auto_approve_simple_changes": bool(auto_simple),
            "allowed_read_globs": _parse_list(allowed_read_globs, default_policy["allowed_read_globs"]),
            "allowed_write_globs": _parse_list(allowed_write_globs, default_policy["allowed_write_globs"]),
            "blocked_globs": _parse_list(blocked_globs, default_policy["blocked_globs"]),
            "network_enabled": bool(network_enabled)
        }

        policy["read_spec"] = self._build_glob_spec(policy["allowed_read_globs"])
        policy["write_spec"] = self._build_glob_spec(policy["allowed_write_globs"])
        policy["block_spec"] = self._build_glob_spec(policy["blocked_globs"])

        return policy

    def _build_glob_spec(self, globs: List[str]) -> Optional[pathspec.PathSpec]:
        if not globs:
            return None
        return pathspec.PathSpec.from_lines("gitwildmatch", globs)

    def _is_path_allowed(self, rel_path: str, policy: Dict[str, Any], mode: str) -> Tuple[bool, Optional[str]]:
        if not rel_path:
            return True, None

        normalized = rel_path.replace("\\", "/").lstrip("./")
        block_spec = policy.get("block_spec")
        if block_spec and (block_spec.match_file(normalized) or block_spec.match_file(f"{normalized}/")):
            return False, f"Path blocked by policy: {rel_path}"

        allow_spec = policy.get("read_spec") if mode == "read" else policy.get("write_spec")
        if allow_spec and not (allow_spec.match_file(normalized) or allow_spec.match_file(f"{normalized}/")):
            return False, f"Path not allowed by policy: {rel_path}"

        return True, None

    def _filter_list_result(self, result: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
        if not result.get("success"):
            return result

        allow_spec = policy.get("read_spec")
        block_spec = policy.get("block_spec")

        def _allowed(item: str) -> bool:
            normalized = item.replace("\\", "/").lstrip("./")
            if block_spec and (block_spec.match_file(normalized) or block_spec.match_file(f"{normalized}/")):
                return False
            if allow_spec and not (allow_spec.match_file(normalized) or allow_spec.match_file(f"{normalized}/")):
                return False
            return True

        files = [item for item in result.get("files", []) if _allowed(item)]
        directories = [item for item in result.get("directories", []) if _allowed(item)]

        result["files"] = files
        result["directories"] = directories
        result["total_files"] = len(files)
        result["total_directories"] = len(directories)
        result["filtered"] = True
        return result

    def _check_command_allowed(self, command: str, policy: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        command = command or ""
        blocked = policy.get("blocked_commands", [])
        for entry in blocked:
            if entry and entry in command:
                return False, f"Command blocked by policy: {entry}"

        allowed = policy.get("allowed_commands", [])
        if allowed:
            if not any(command.strip().startswith(item) for item in allowed):
                return False, "Command not in allowlist"

        if not policy.get("network_enabled") and self._is_network_command(command):
            return False, "Command blocked by network policy"

        return True, None

    def _requires_command_approval(self, tool_name: str, policy: Dict[str, Any]) -> bool:
        command_approval = (policy.get("command_approval") or "prompt").lower()
        if command_approval in ("auto", "none"):
            return False
        if tool_name == "run_tests" and policy.get("auto_approve_tests"):
            return False
        return True

    def _is_network_command(self, command: str) -> bool:
        lowered = command.lower()
        network_tokens = [
            "curl ",
            "wget ",
            "invoke-webrequest",
            "iwr ",
            "http://",
            "https://",
            "pip install",
            "pip3 install",
            "npm install",
            "pnpm install",
            "yarn add",
            "git clone",
            "git fetch",
            "git pull"
        ]
        return any(token in lowered for token in network_tokens)

    def _create_approval_request(self) -> Tuple[str, asyncio.Future]:
        request_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending_approvals[request_id] = future
        return request_id, future

    async def _await_approval(self, request_id: str, timeout: int = 300) -> bool:
        future = self._pending_approvals.get(request_id)
        if not future:
            return False
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending_approvals.pop(request_id, None)

    def resolve_approval(self, request_id: str, approved: bool) -> None:
        future = self._pending_approvals.get(request_id)
        if future and not future.done():
            future.set_result(bool(approved))

    def _init_tools(self):
        """Initialize and register all tools"""
        self.tool_registry.register(ReadFileTool(self.workspace_path))
        self.tool_registry.register(WriteFileTool(self.workspace_path))
        self.tool_registry.register(ListFilesTool(self.workspace_path))
        self.tool_registry.register(ApplyPatchTool(self.workspace_path))
        self.tool_registry.register(RunCommandTool(self.workspace_path))
        self.tool_registry.register(RunTestsTool(self.workspace_path))
        self.tool_registry.register(ReportPlanTool())
        self.tool_registry.register(ProposePatchTool(self.workspace_path))
        self.tool_registry.register(ProposeDiffTool(self.workspace_path))

        logger.info("agent_tools_initialized",
                   tool_count=len(self.tool_registry.tools),
                   tools=list(self.tool_registry.tools.keys()))

    async def process_message(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message and yield response chunks

        Args:
            user_message: The user's message
            context: Optional context (file selection, diagnostics, etc.)

        Yields:
            Response events (thinking, tool_use, message, etc.)
        """
        try:
            trajectory_entries: List[str] = []
            rag_results_count = 0
            workspace_results_count = 0
            ace_bullets_used: List[str] = []
            test_loop_active = bool(context and isinstance(context, dict) and context.get("command") == "test")
            test_loop_attempts = 0
            test_loop_failed = False

            # Retrieve relevant knowledge from RAG
            rag_context = ""
            if self.retriever:
                logger.info("retrieving_knowledge", query=user_message[:100])

                try:
                    # Retrieve relevant documentation and training examples
                    results = await self.retriever.retrieve(
                        query=user_message,
                        limit=5,
                        score_threshold=0.6
                    )

                    if results:
                        rag_pack = self.retriever.build_context_pack(
                            title="Relevant Knowledge",
                            results=results,
                            token_budget=settings.RAG_CONTEXT_TOKENS
                        )
                        rag_results_count = len(rag_pack.items)
                        rag_context = rag_pack.text

                        logger.info("knowledge_retrieved", chunks=len(results))
                    else:
                        logger.info("no_knowledge_found")

                except Exception as e:
                    logger.error("retrieval_failed", error=str(e))
                    # Continue without RAG if it fails

            include_workspace_rag = True
            if context and isinstance(context, dict):
                include_workspace_rag = context.get("include_workspace_rag", True)

            # Retrieve workspace-specific knowledge
            workspace_context = ""
            if include_workspace_rag and self.retriever and self.workspace_id:
                try:
                    workspace_results = await self.retriever.retrieve_workspace_hybrid(
                        query=user_message,
                        workspace_id=self.workspace_id,
                        limit=5,
                        score_threshold=0.6
                    )

                    if workspace_results:
                        workspace_pack = self.retriever.build_context_pack(
                            title="Workspace Knowledge",
                            results=workspace_results,
                            token_budget=settings.WORKSPACE_CONTEXT_TOKENS
                        )
                        workspace_results_count = len(workspace_pack.items)
                        workspace_context = workspace_pack.text

                        logger.info("workspace_knowledge_retrieved",
                                   workspace_id=self.workspace_id,
                                   chunks=len(workspace_results))
                    else:
                        logger.info("no_workspace_knowledge_found", workspace_id=self.workspace_id)
                except Exception as e:
                    logger.error("workspace_retrieval_failed",
                                workspace_id=self.workspace_id,
                                error=str(e))

            # Retrieve relevant ACE bullets (semantic)
            ace_context = ""
            self._used_bullet_ids = []
            if self.enable_ace and self.retriever:
                try:
                    ace_results = await self.retriever.retrieve_ace_bullets(
                        query=user_message,
                        limit=5,
                        score_threshold=0.5
                    )

                    if ace_results:
                        def _format_ace(result):
                            payload = result.metadata or {}
                            bullet_id = payload.get("bullet_id", payload.get("id"))
                            section = payload.get("section", "unknown")
                            helpful = payload.get("helpful_count", 0)
                            harmful = payload.get("harmful_count", 0)
                            total = helpful + harmful
                            quality_score = helpful / total if total > 0 else 0.5
                            content = payload.get("content", result.content)

                            line = (
                                f"- [{section}] {content} "
                                f"(id: {bullet_id}, score: {quality_score:.2f}, relevance: {result.score:.2f})"
                            )
                            return line

                        ace_pack = self.retriever.build_context_pack(
                            title="ACE Playbook - Relevant Bullets",
                            results=ace_results,
                            token_budget=settings.ACE_CONTEXT_TOKENS,
                            item_formatter=_format_ace
                        )
                        ace_context = ace_pack.text

                        for result in ace_pack.items:
                            payload = result.metadata or {}
                            bullet_id = payload.get("bullet_id", payload.get("id"))
                            if bullet_id:
                                self._used_bullet_ids.append(bullet_id)

                        logger.info("ace_bullets_retrieved",
                                   frontend_id=self.frontend_id,
                                   bullets=len(ace_results))
                    else:
                        logger.info("no_ace_bullets_found", frontend_id=self.frontend_id)

                except Exception as e:
                    logger.error("ace_bullet_retrieval_failed",
                                frontend_id=self.frontend_id,
                                error=str(e))

            if rag_results_count:
                trajectory_entries.append(f"RAG results: {rag_results_count}")
            if workspace_results_count:
                trajectory_entries.append(f"Workspace RAG results: {workspace_results_count}")

            ace_bullets_used = list(self._used_bullet_ids)
            if ace_bullets_used:
                trajectory_entries.append(f"ACE bullets used: {', '.join(ace_bullets_used)}")

            # Add user message to conversation (with RAG context if available)
            user_content = self._format_user_message(user_message, context)
            if rag_context or workspace_context or ace_context:
                combined_context = rag_context + workspace_context + ace_context
                user_content = combined_context + "\n\n---\n\n" + user_content

            self.conversation_history.append({
                "role": "user",
                "content": user_content
            })

            # Get current LLM client from model manager
            llm_client = self._get_llm_client()
            if not llm_client:
                yield {
                    "type": "error",
                    "error": "No model loaded. Please load a model first."
                }
                return

            # Agentic loop
            iteration = 0
            total_tool_calls = 0
            while iteration < self.max_iterations:
                iteration += 1

                logger.info("agent_iteration", iteration=iteration)
                trajectory_entries.append(f"Iteration {iteration}")

                yield {
                    "type": "assistant.thinking",
                    "phase": "reasoning",
                    "message": f"Thinking... (step {iteration})"
                }

                # Get tools in OpenAI format
                tools = self.tool_registry.list_tools()

                # Build messages for LLM
                messages = self._build_messages()

                # Stream response from LLM
                current_content = ""
                current_tool_calls = []

                async for chunk in llm_client.generate_stream(
                    messages=messages,
                    tools=tools,
                    temperature=0.7
                ):
                    if chunk["type"] == "content":
                        current_content += chunk["content"]
                        # Stream content to user
                        yield {
                            "type": "assistant.message_delta",
                            "delta": chunk["content"]
                        }

                    elif chunk["type"] == "tool_call":
                        current_tool_calls.append(chunk["tool_call"])

                    elif chunk["type"] == "done":
                        # Response complete
                        logger.info("llm_response_complete",
                                  has_content=bool(current_content),
                                  tool_calls=len(current_tool_calls))

                # Add assistant response to history
                assistant_message = {"role": "assistant"}

                # Clean XML from content if tool calls were parsed
                display_content = current_content
                if current_content and current_tool_calls:
                    # Re-parse to get cleaned content without XML
                    from app.core.llm_client import parse_xml_tool_calls
                    cleaned_content, _ = parse_xml_tool_calls(current_content)
                    display_content = cleaned_content

                if display_content:
                    assistant_message["content"] = display_content
                else:
                    assistant_message["content"] = ""

                if current_tool_calls:
                    assistant_message["tool_calls"] = current_tool_calls

                self.conversation_history.append(assistant_message)

                if current_content:
                    trajectory_entries.append(
                        f"Assistant response ({iteration}): {self._truncate_text(current_content, 1000)}"
                    )

                # If no tool calls, we're done
                if not current_tool_calls:
                    if test_loop_active and test_loop_failed and test_loop_attempts < settings.TEST_LOOP_MAX_ATTEMPTS:
                        self.conversation_history.append({
                            "role": "user",
                            "content": "Tests failed. Fix the issues and rerun the tests."
                        })
                        continue

                    yield {
                        "type": "assistant.message_final",
                        "message": current_content,
                        "metadata": {
                            "iterations": iteration,
                            "success": True,
                            "test_attempts": test_loop_attempts
                        }
                    }
                    outcome = {
                        "success": True,
                        "iterations": iteration,
                        "final_message": self._truncate_text(current_content, 2000),
                        "tool_calls": total_tool_calls,
                        "test_attempts": test_loop_attempts
                    }
                    trajectory = "\n".join(trajectory_entries)
                    self._schedule_ace_learning(
                        task=user_message,
                        trajectory=trajectory,
                        outcome=outcome,
                        used_bullet_ids=ace_bullets_used
                    )
                    return

                # Execute tool calls
                tool_results = []
                policy = await self._get_workspace_policy()
                for tool_call in current_tool_calls:
                    total_tool_calls += 1
                    # Parse tool call
                    tool_name = tool_call.get("function", {}).get("name")
                    tool_args_str = tool_call.get("function", {}).get("arguments", "{}")

                    try:
                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    except json.JSONDecodeError:
                        tool_args = {}

                    logger.info("executing_tool_call", tool=tool_name, args=tool_args)
                    try:
                        args_summary = json.dumps(tool_args, ensure_ascii=True)
                    except TypeError:
                        args_summary = str(tool_args)
                    trajectory_entries.append(
                        f"Tool call ({iteration}): {tool_name} args={args_summary}"
                    )

                    yield {
                        "type": "assistant.tool_use",
                        "tool": tool_name,
                        "arguments": tool_args
                    }

                    # Execute tool with approval gating if required
                    tool = self.tool_registry.get(tool_name)
                    result: Dict[str, Any]

                    if tool_name in ("run_command", "run_tests"):
                        allowed, reason = self._check_command_allowed(tool_args.get("command", ""), policy)
                        if not allowed:
                            result = {
                                "success": False,
                                "error": reason or "Command blocked by policy",
                                "denied_by_policy": True
                            }
                        else:
                            approval_required = self._requires_command_approval(tool_name, policy)
                            if approval_required:
                                request_id, _future = self._create_approval_request()
                                prompt = tool.approval_prompt(tool_args) if tool else None
                                yield {
                                    "type": "command.request_approval",
                                    "request_id": request_id,
                                    "tool": tool_name,
                                    "arguments": tool_args,
                                    "message": prompt
                                }
                                approved = await self._await_approval(request_id)
                                if not approved:
                                    result = {
                                        "success": False,
                                        "error": "Command execution denied",
                                        "requires_approval": True
                                    }
                                else:
                                    result = await self.tool_registry.execute_tool(tool_name, tool_args)
                            else:
                                result = await self.tool_registry.execute_tool(tool_name, tool_args)
                    elif tool_name in ("read_file", "write_file", "apply_patch", "list_files", "propose_patch", "propose_diff"):
                        path_key = "file_path"
                        if tool_name == "list_files":
                            path_key = "directory"
                        target_path = tool_args.get(path_key) or ""
                        if target_path in (".", "./"):
                            target_path = ""
                        mode = "read" if tool_name in ("read_file", "list_files", "propose_patch", "propose_diff") else "write"
                        allowed, reason = self._is_path_allowed(target_path, policy, mode)
                        if not allowed:
                            result = {
                                "success": False,
                                "error": reason or "Path blocked by policy",
                                "denied_by_policy": True
                            }
                        else:
                            result = await self.tool_registry.execute_tool(tool_name, tool_args)
                            if tool_name == "list_files":
                                result = self._filter_list_result(result, policy)
                    elif tool and tool.requires_approval:
                        request_id, _future = self._create_approval_request()
                        prompt = tool.approval_prompt(tool_args)
                        yield {
                            "type": "tool.request_approval",
                            "request_id": request_id,
                            "tool": tool_name,
                            "arguments": tool_args,
                            "message": prompt
                        }
                        approved = await self._await_approval(request_id)
                        if not approved:
                            result = {
                                "success": False,
                                "error": "Tool execution denied",
                                "requires_approval": True
                            }
                        else:
                            result = await self.tool_registry.execute_tool(tool_name, tool_args)
                    else:
                        result = await self.tool_registry.execute_tool(tool_name, tool_args)

                    # Track test loop attempts
                    if test_loop_active and tool_name in ("run_tests", "run_command"):
                        command_value = tool_args.get("command", "")
                        if tool_name == "run_tests" or self._is_test_command(command_value):
                            test_loop_attempts += 1
                            test_loop_failed = not result.get("success", False)

                    # Send FULL result to conversation (model needs complete data)
                    tool_results.append({
                        "tool_call_id": tool_call.get("id", f"call_{iteration}"),
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(result)  # Full result for model
                    })

                    # Send truncated result to UI only (for user display)
                    yield {
                        "type": "assistant.tool_result",
                        "tool": tool_name,
                        "result": self._get_display_result(tool_name, result)
                    }
                    trajectory_entries.append(
                        f"Tool result ({iteration}): {self._summarize_tool_result(tool_name, result)}"
                    )

                    if tool_name == "report_plan" and result.get("success"):
                        yield {
                            "type": "agent.plan",
                            "steps": result.get("steps", []),
                            "rationale": result.get("rationale")
                        }
                    elif tool_name == "propose_patch" and result.get("success"):
                        yield {
                            "type": "patch.proposed",
                            "id": result.get("id"),
                            "file_path": result.get("file_path"),
                            "diff": result.get("diff"),
                            "base_hash": result.get("base_hash"),
                            "rationale": result.get("rationale")
                        }

                # Add tool results to conversation
                self.conversation_history.extend(tool_results)

                # Continue loop to process tool results

            # Max iterations reached
            yield {
                "type": "assistant.message_final",
                "message": current_content or "I've completed the maximum number of steps. Please let me know if you need anything else.",
                "metadata": {
                    "iterations": iteration,
                    "success": True,
                    "max_iterations_reached": True,
                    "test_attempts": test_loop_attempts
                }
            }
            outcome = {
                "success": False,
                "iterations": iteration,
                "final_message": self._truncate_text(current_content, 2000),
                "tool_calls": total_tool_calls,
                "max_iterations_reached": True,
                "test_attempts": test_loop_attempts
            }
            trajectory = "\n".join(trajectory_entries)
            self._schedule_ace_learning(
                task=user_message,
                trajectory=trajectory,
                outcome=outcome,
                used_bullet_ids=ace_bullets_used
            )

        except Exception as e:
            logger.error("agent_error", error=str(e))
            yield {
                "type": "server.error",
                "error": {
                    "code": "agent_error",
                    "message": str(e)
                }
            }

    def _build_messages(self) -> List[Dict[str, str]]:
        """Build message list for LLM with system prompt and ACE playbook"""
        system_content = self.system_prompt

        # Add ACE playbook if enabled
        if self.enable_ace and self.playbook and not self.retriever:
            playbook_text = self.playbook.to_text()
            if playbook_text.strip():
                system_content += f"\n\n## ACE Playbook - Learned Strategies\n{playbook_text}"

        messages = []

        # Only add system message if there's content
        if system_content.strip():
            messages.append({
                "role": "system",
                "content": system_content
            })

        messages.extend(self.conversation_history)
        return messages

    def _format_user_message(self, message: str, context: Optional[Dict[str, Any]]) -> str:
        """Format user message with context"""
        if not context:
            return message

        command = context.get("command") if isinstance(context, dict) else None
        message = self._apply_command(command, message)

        context_parts = [message]

        # Add active file context
        if context.get("active_file"):
            context_parts.append(f"\n\nActive file: {context['active_file'].get('file_path')}")
            if context['active_file'].get('selection'):
                sel = context['active_file']['selection']
                context_parts.append(f"Selected lines {sel.get('start')}-{sel.get('end')}")

        # Add diagnostics/errors
        if context.get("diagnostics"):
            diagnostics = context['diagnostics']
            if diagnostics:
                context_parts.append(f"\n\nCurrent errors/warnings:")
                for diag in diagnostics[:5]:  # Limit to 5
                    context_parts.append(
                        f"- {diag.get('file_path')}:{diag.get('line')} - {diag.get('message')}"
                    )

        # Add open editors
        if context.get("open_editors"):
            editors = context['open_editors']
            if editors:
                context_parts.append(f"\n\nOpen files: {', '.join(editors)}")

        # Add @mention context
        if context.get("mentions"):
            mentions = context.get("mentions", [])
            if mentions:
                context_parts.append("\n\nMentioned context:")
                for mention in mentions:
                    mention_type = mention.get("type")
                    if mention_type == "file":
                        path = mention.get("path", "unknown")
                        content = mention.get("content", "")
                        truncated = mention.get("truncated", False)
                        context_parts.append(f"\n@{path}")
                        if content:
                            context_parts.append("```")
                            context_parts.append(content)
                            if truncated:
                                context_parts.append("\n... (truncated)")
                            context_parts.append("```")
                    else:
                        name = mention.get("name")
                        if name:
                            context_parts.append(f"\n@{name}")

        return "\n".join(context_parts)

    def _apply_command(self, command: Optional[str], message: str) -> str:
        if not command:
            return message

        command_map = {
            "fix": "Fix the issue described below. Provide a clear summary and the exact changes to apply.",
            "explain": "Explain the code or issue described below in clear, concise terms.",
            "test": (
                "Run the relevant tests using the run_tests tool and fix failures iteratively "
                "until they pass or you reach a reasonable attempt limit. Include how to run them."
            ),
            "refactor": "Refactor the code described below while preserving behavior.",
            "review": "Review the code described below. List issues by severity and suggest fixes.",
            "doc": "Add or update documentation/comments for the request below.",
            "commit": "Prepare a commit message and summary for the changes described below. Do not run git commands."
        }

        instruction = command_map.get(command)
        if not instruction:
            return message

        if message.strip():
            return f"{instruction}\n\n{message}"
        return instruction

    def _is_test_command(self, command: str) -> bool:
        if not command:
            return False
        lowered = command.lower()
        return any(
            token in lowered
            for token in ("pytest", "npm test", "pnpm test", "yarn test", "go test", "dotnet test")
        )

    def _get_display_result(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Get user-friendly display version of tool result"""
        if not result.get("success"):
            return result

        # Handle read_file - show preview only
        if tool_name == "read_file":
            content = result.get("content", "")
            size = result.get("size", len(content))

            # Show first 50 lines or 2000 chars
            lines = content.split('\n')
            preview_lines = lines[:50]
            preview = '\n'.join(preview_lines)

            if len(preview) > 2000:
                preview = preview[:2000]

            return {
                "success": True,
                "file_path": result.get("file_path"),
                "preview": preview,
                "total_lines": len(lines),
                "total_size": size,
                "truncated": len(lines) > 50 or len(content) > 2000
            }

        # Handle list_files - already good
        if tool_name == "list_files":
            files = result.get("files", [])
            if len(files) > 20:
                return {
                    "success": True,
                    "directory": result.get("directory"),
                    "sample_files": files[:20],
                    "total_files": len(files),
                    "total_directories": len(result.get("directories", [])),
                    "truncated": True
                }

        # Default: return as-is for small results
        return result

    def _summarize_tool_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Summarize tool results to avoid context overflow"""
        if not result.get("success"):
            # Keep errors as-is
            return json.dumps(result)

        # Handle list_files specially
        if tool_name == "list_files":
            files = result.get("files", [])
            dirs = result.get("directories", [])
            total_files = len(files)
            total_dirs = len(dirs)

            # Show first 20 files
            if total_files > 20:
                sample_files = files[:20]
                summary = {
                    "success": True,
                    "directory": result.get("directory"),
                    "total_files": total_files,
                    "total_directories": total_dirs,
                    "sample_files": sample_files,
                    "note": f"Showing first 20 of {total_files} files. Full list available if needed."
                }
                return json.dumps(summary)

        # Handle read_file for large content
        if tool_name == "read_file":
            content = result.get("content", "")
            if len(content) > 10000:
                truncated = {
                    "success": True,
                    "file_path": result.get("file_path"),
                    "content": content[:10000],
                    "size": result.get("size"),
                    "note": f"Content truncated. Full file is {result.get('size')} chars."
                }
                return json.dumps(truncated)

        # Default: return as-is
        return json.dumps(result)

    def reset_conversation(self):
        """Reset conversation history"""
        self.conversation_history = []
        logger.info("conversation_reset")

    async def learn_from_interaction(
        self,
        task: str,
        trajectory: str,
        outcome: Dict[str, Any],
        ground_truth: Optional[Any] = None,
        used_bullet_ids: Optional[List[str]] = None
    ):
        """
        ACE learning loop: Reflect and curate after an interaction

        Args:
            task: The original task
            trajectory: Execution trajectory
            outcome: Outcome of the execution
            ground_truth: Optional ground truth for supervised learning
        """
        if not self.enable_ace:
            return

        # Get current model configuration
        if not self.model_manager:
            logger.warning("ace_learning_skipped", reason="No model manager available")
            return

        current_config = self.model_manager.get_current_config()
        if not current_config:
            logger.warning("ace_learning_skipped", reason="No model loaded")
            return

        logger.info("ace_learning_start", task=task[:100])

        # Create isolated LLM client for ACE operations
        # This prevents concurrent streaming conflicts with the main agent
        ace_client = IsolatedLLMClient(
            provider=current_config.provider,
            model_name=current_config.model_name,
            base_url=current_config.url,
            context_window=current_config.context_window,
            temperature=current_config.temperature
        )

        # Create Reflector and Curator with isolated LLM client
        reflector = Reflector(ace_client)
        curator = Curator(
            ace_client,
            embedding_manager=self.embedding_manager,
            vector_store=self.vector_store,
            collection_name=self.ace_collection
        )

        # Step 1: Reflect on the interaction
        reflection = await reflector.reflect(
            task=task,
            trajectory=trajectory,
            outcome=outcome,
            ground_truth=ground_truth,
            playbook_bullets=used_bullet_ids or self._used_bullet_ids or None
        )

        # Step 2: Curate insights into delta operations
        operations = await curator.curate(
            task=task,
            reflection=reflection,
            playbook=self.playbook
        )

        # Apply bullet feedback and persist updates
        bullet_feedback = reflection.get("bullet_feedback")
        if bullet_feedback:
            updated_ids = self.playbook.apply_bullet_feedback(bullet_feedback)

            if updated_ids and self.embedding_manager and self.vector_store:
                for bullet_id in updated_ids:
                    self.playbook.save_bullet_to_vector_db(
                        bullet_id=bullet_id,
                        vector_store=self.vector_store,
                        embedding_manager=self.embedding_manager,
                        collection_name=self.ace_collection
                    )

        # Step 3: Apply delta updates
        curator.apply_delta(self.playbook, operations)

        # Step 4: Grow-and-refine - deduplicate periodically
        if len(self.playbook.bullets) > 50:
            removed_ids, updated_ids = self.playbook.deduplicate()
            pruned_ids = self.playbook.prune_harmful()

            if self.embedding_manager and self.vector_store:
                for bullet_id in updated_ids:
                    self.playbook.save_bullet_to_vector_db(
                        bullet_id=bullet_id,
                        vector_store=self.vector_store,
                        embedding_manager=self.embedding_manager,
                        collection_name=self.ace_collection
                    )

                delete_ids = list({*removed_ids, *pruned_ids})
                if delete_ids:
                    self.vector_store.delete_points(
                        collection_name=self.ace_collection,
                        point_ids=delete_ids
                    )

        logger.info("ace_learning_complete",
                   operations_applied=len(operations),
                   total_bullets=len(self.playbook.bullets))

    def save_playbook(self, file_path: str):
        """Save playbook to file"""
        if not self.enable_ace:
            return

        import json
        with open(file_path, 'w') as f:
            json.dump(self.playbook.to_dict(), f, indent=2)

        logger.info("playbook_saved", path=file_path)

    def load_playbook(self, file_path: str):
        """Load playbook from file"""
        if not self.enable_ace:
            return

        import json
        with open(file_path, 'r') as f:
            data = json.load(f)

        self.playbook = Playbook.from_dict(data)
        logger.info("playbook_loaded",
                   path=file_path,
                   bullets=len(self.playbook.bullets))
