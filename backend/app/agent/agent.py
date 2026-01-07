"""
Main agent implementation with agentic loop
"""

import json
from typing import Dict, List, Any, Optional, AsyncGenerator
import structlog

from app.core.llm_client import LLMClient
from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.core.model_manager import ModelManager
from app.retrieval.retriever import Retriever
from app.tools.base import ToolRegistry
from app.tools import ReadFileTool, WriteFileTool, ListFilesTool, RunCommandTool
from app.ace import Playbook, Reflector, Curator

logger = structlog.get_logger()


class Agent:
    """Main coding agent with tool calling capabilities"""

    def __init__(
        self,
        workspace_path: str,
        frontend_id: str = "vscode",  # Which frontend is using this agent
        model_manager: Optional[ModelManager] = None,
        embedding_manager: Optional[EmbeddingManager] = None,
        vector_store: Optional[VectorStore] = None,
        enable_ace: bool = True
    ):
        self.workspace_path = workspace_path
        self.frontend_id = frontend_id
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
                vector_store=vector_store
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

    def _init_tools(self):
        """Initialize and register all tools"""
        self.tool_registry.register(ReadFileTool(self.workspace_path))
        self.tool_registry.register(WriteFileTool(self.workspace_path))
        self.tool_registry.register(ListFilesTool(self.workspace_path))
        self.tool_registry.register(RunCommandTool(self.workspace_path))

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
                        rag_context = "\n\n## Relevant Knowledge\n"
                        for i, result in enumerate(results, 1):
                            rag_context += f"\n### {result.source} (score: {result.score:.2f})\n"
                            rag_context += f"{result.content}\n"

                        logger.info("knowledge_retrieved", chunks=len(results))
                    else:
                        logger.info("no_knowledge_found")

                except Exception as e:
                    logger.error("retrieval_failed", error=str(e))
                    # Continue without RAG if it fails

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
                        ace_context = "\n\n## ACE Playbook - Relevant Bullets\n"
                        for result in ace_results:
                            payload = result.metadata or {}
                            bullet_id = payload.get("bullet_id", payload.get("id"))
                            section = payload.get("section", "unknown")
                            helpful = payload.get("helpful_count", 0)
                            harmful = payload.get("harmful_count", 0)
                            total = helpful + harmful
                            quality_score = helpful / total if total > 0 else 0.5
                            content = payload.get("content", result.content)

                            ace_context += (
                                f"\n- [{section}] {content} "
                                f"(id: {bullet_id}, score: {quality_score:.2f}, relevance: {result.score:.2f})"
                            )

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

            # Add user message to conversation (with RAG context if available)
            user_content = self._format_user_message(user_message, context)
            if rag_context or ace_context:
                combined_context = rag_context + ace_context
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
            while iteration < self.max_iterations:
                iteration += 1

                logger.info("agent_iteration", iteration=iteration)

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

                if current_content:
                    assistant_message["content"] = current_content
                else:
                    assistant_message["content"] = ""

                if current_tool_calls:
                    assistant_message["tool_calls"] = current_tool_calls

                self.conversation_history.append(assistant_message)

                # If no tool calls, we're done
                if not current_tool_calls:
                    yield {
                        "type": "assistant.message_final",
                        "message": current_content,
                        "metadata": {
                            "iterations": iteration,
                            "success": True
                        }
                    }
                    return

                # Execute tool calls
                tool_results = []
                for tool_call in current_tool_calls:
                    # Parse tool call
                    tool_name = tool_call.get("function", {}).get("name")
                    tool_args_str = tool_call.get("function", {}).get("arguments", "{}")

                    try:
                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    except json.JSONDecodeError:
                        tool_args = {}

                    logger.info("executing_tool_call", tool=tool_name, args=tool_args)

                    yield {
                        "type": "assistant.tool_use",
                        "tool": tool_name,
                        "arguments": tool_args
                    }

                    # Execute tool
                    result = await self.tool_registry.execute_tool(tool_name, tool_args)

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
                    "max_iterations_reached": True
                }
            }

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

        return "\n".join(context_parts)

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
        ground_truth: Optional[Any] = None
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

        # Get current LLM client
        llm_client = self._get_llm_client()
        if not llm_client:
            logger.warning("ace_learning_skipped", reason="No LLM client available")
            return

        logger.info("ace_learning_start", task=task[:100])

        # Create Reflector and Curator with current LLM client
        reflector = Reflector(llm_client)
        curator = Curator(
            llm_client,
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
            playbook_bullets=self._used_bullet_ids or None
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
            self.playbook.apply_bullet_feedback(bullet_feedback)

            if self.embedding_manager and self.vector_store:
                if isinstance(bullet_feedback, list):
                    bullet_ids = [
                        item.get("bullet_id")
                        for item in bullet_feedback
                        if item.get("bullet_id")
                    ]
                elif isinstance(bullet_feedback, dict):
                    bullet_ids = list(bullet_feedback.keys())
                else:
                    bullet_ids = []

                for bullet_id in bullet_ids:
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
            self.playbook.deduplicate()
            self.playbook.prune_harmful()

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
