"""
ACE Curator - Integrates insights into structured context updates
"""

import json
from typing import Dict, List, Any, Optional, Union
import structlog

from app.core.llm_client import LLMClient
from app.ace.playbook import Playbook
from app.ace.json_utils import extract_json_object
from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore

logger = structlog.get_logger()


class Curator:
    """
    Curator component of ACE

    Synthesizes reflections into compact delta updates and merges them
    into the existing playbook using deterministic logic.
    """

    def __init__(
        self,
        llm_client: Optional[Union[LLMClient, "IsolatedLLMClient"]] = None,
        embedding_manager: Optional[EmbeddingManager] = None,
        vector_store: Optional[VectorStore] = None,
        collection_name: Optional[str] = None
    ):
        self.llm_client = llm_client or LLMClient()
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
        self.collection_name = collection_name

        logger.info("curator_initialized",
                   has_vector_storage=self._has_vector_storage(),
                   collection=collection_name)

    async def curate(
        self,
        task: str,
        reflection: Dict[str, Any],
        playbook: Playbook
    ) -> List[Dict[str, Any]]:
        """
        Curate insights from reflection into delta updates

        Args:
            task: The original task
            reflection: Reflection output from Reflector
            playbook: Current playbook

        Returns:
            List of delta operations to apply
        """
        # Build curation prompt
        prompt = self._build_curation_prompt(task, reflection, playbook)

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        # Get curation from LLM
        response_text = ""
        async for chunk in self.llm_client.generate_stream(
            messages=messages,
            temperature=0.7,
            response_format="json"
        ):
            if chunk["type"] == "content":
                response_text += chunk["content"]

        # Parse delta operations
        curation_result = extract_json_object(response_text)
        if not curation_result:
            preview = response_text[:200].replace("\n", "\\n")
            logger.error(
                "curation_json_parse_error",
                error="invalid_json",
                response_length=len(response_text),
                response_preview=preview
            )
            return []

        operations = curation_result.get("operations", [])

        logger.info("curation_complete",
                   operations_count=len(operations))

        return operations

    def apply_delta(
        self,
        playbook: Playbook,
        operations: List[Dict[str, Any]]
    ):
        """
        Apply delta operations to the playbook

        Args:
            playbook: Playbook to update
            operations: List of operations from curator
        """
        for op in operations:
            op_type = op.get("type")
            section = op.get("section")
            content = op.get("content")

            if op_type == "ADD":
                bullet_id = playbook.add_bullet(section, content)
                if self._has_vector_storage():
                    playbook.save_bullet_to_vector_db(
                        bullet_id=bullet_id,
                        vector_store=self.vector_store,
                        embedding_manager=self.embedding_manager,
                        collection_name=self.collection_name
                    )

            elif op_type == "UPDATE":
                bullet_id = op.get("bullet_id")
                if bullet_id:
                    playbook.update_bullet(bullet_id, content=content)
                    if self._has_vector_storage():
                        playbook.save_bullet_to_vector_db(
                            bullet_id=bullet_id,
                            vector_store=self.vector_store,
                            embedding_manager=self.embedding_manager,
                            collection_name=self.collection_name
                        )

            elif op_type == "REMOVE":
                bullet_id = op.get("bullet_id")
                if bullet_id:
                    playbook.remove_bullet(bullet_id)
                    if self._has_vector_storage():
                        playbook.delete_bullet_from_vector_db(
                            bullet_id=bullet_id,
                            vector_store=self.vector_store,
                            collection_name=self.collection_name
                        )

        logger.info("delta_applied", operations_count=len(operations))

    def _has_vector_storage(self) -> bool:
        """Check if vector storage is configured"""
        return (
            self.embedding_manager is not None and
            self.vector_store is not None and
            self.collection_name is not None
        )

    def _build_curation_prompt(
        self,
        task: str,
        reflection: Dict[str, Any],
        playbook: Playbook
    ) -> str:
        """Build the curation prompt"""
        playbook_text = playbook.to_text()

        return f"""You are curating a coding agent's playbook. Based on a reflection, identify what NEW insights should be added.

**Task Context:**
{task}

**Current Playbook:**
{playbook_text}

**Reflection:**
{json.dumps(reflection, indent=2)}

**Your Task:**
Identify ONLY NEW insights, strategies, or corrections that are MISSING from the current playbook.

**Rules:**
1. Avoid redundancy - only add content that complements existing bullets
2. Be specific and actionable
3. Focus on quality over quantity
4. For code-related insights, include actual code patterns or API schemas

**Output Format (JSON only, no markdown or code fences):**
{{
    "reasoning": "Your analysis of what needs to be added",
    "operations": [
        {{
            "type": "ADD",
            "section": "strategies_and_hard_rules",
            "content": "Specific strategy or rule to add"
        }}
    ]
}}

**Available Sections:**
- strategies_and_hard_rules: General strategies and important rules
- useful_code_snippets: Code patterns and templates
- troubleshooting_and_pitfalls: Common errors and how to avoid them
- apis_and_schemas: API usage patterns and response schemas
- domain_knowledge: Domain-specific concepts and facts

**Operation Types:**
- ADD: Create new bullet point
- UPDATE: Modify existing bullet (requires bullet_id)
- REMOVE: Delete bullet (requires bullet_id)
"""

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Curator"""
        return """You are a master curator of knowledge for coding agents.

Your role is to:
1. Synthesize reflections into actionable insights
2. Avoid redundancy with existing knowledge
3. Create structured, incremental updates
4. Maintain playbook quality and organization

Focus on:
- Concrete, specific insights
- Actionable strategies
- Clear corrections to errors
- Reusable patterns and principles

Output ONLY valid JSON with the specified structure. Do not include markdown or code fences."""
