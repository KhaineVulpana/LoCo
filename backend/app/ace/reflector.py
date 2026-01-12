"""
ACE Reflector - Analyzes trajectories and extracts insights
"""

import json
from typing import Dict, List, Any, Optional, Union
import structlog

from app.core.llm_client import LLMClient

logger = structlog.get_logger()


class Reflector:
    """
    Reflector component of ACE

    Analyzes execution traces, outcomes, and errors to extract:
    - Concrete insights from successes
    - Diagnosis of failure modes
    - Missing heuristics or rules
    """

    def __init__(self, llm_client: Optional[Union[LLMClient, "IsolatedLLMClient"]] = None):
        self.llm_client = llm_client or LLMClient()
        self.max_refinement_rounds = 5

    async def reflect(
        self,
        task: str,
        trajectory: str,
        outcome: Dict[str, Any],
        ground_truth: Optional[Any] = None,
        playbook_bullets: Optional[List[str]] = None,
        max_rounds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Reflect on a trajectory and extract insights

        Args:
            task: The original task/query
            trajectory: The execution trajectory (reasoning steps, tool calls, etc.)
            outcome: The outcome (success/failure, output, errors)
            ground_truth: Optional ground truth for comparison
            playbook_bullets: Bullets from playbook that were used
            max_rounds: Maximum refinement rounds

        Returns:
            Reflection containing insights and analysis
        """
        max_rounds = max_rounds or self.max_refinement_rounds

        # Build reflection prompt
        prompt = self._build_reflection_prompt(
            task, trajectory, outcome, ground_truth, playbook_bullets
        )

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        # Iterative refinement
        reflection = None
        for round_num in range(max_rounds):
            logger.info("reflection_round", round=round_num + 1)

            # Get reflection from LLM
            response_text = ""
            async for chunk in self.llm_client.generate_stream(
                messages=messages,
                temperature=0.7
            ):
                if chunk["type"] == "content":
                    response_text += chunk["content"]

            # Parse JSON response
            try:
                reflection = json.loads(response_text)

                # Validate reflection has required fields
                required_fields = [
                    "reasoning",
                    "error_identification",
                    "root_cause_analysis",
                    "correct_approach",
                    "key_insight"
                ]

                if all(field in reflection for field in required_fields):
                    logger.info("reflection_complete", rounds=round_num + 1)
                    break

            except json.JSONDecodeError:
                logger.warning("reflection_json_parse_error", round=round_num + 1)

            # If refinement needed, add feedback
            if round_num < max_rounds - 1:
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": "Please provide a valid JSON response with all required fields."
                })

        return reflection or self._default_reflection()

    def _build_reflection_prompt(
        self,
        task: str,
        trajectory: str,
        outcome: Dict[str, Any],
        ground_truth: Optional[Any],
        playbook_bullets: Optional[List[str]]
    ) -> str:
        """Build the reflection prompt"""
        prompt_parts = [
            "Analyze the following task execution and provide insights.\n",
            f"\n**Task:**\n{task}\n",
            f"\n**Execution Trajectory:**\n{trajectory}\n",
            f"\n**Outcome:**\n{json.dumps(outcome, indent=2)}\n"
        ]

        if ground_truth is not None:
            prompt_parts.append(f"\n**Ground Truth:**\n{ground_truth}\n")

        if playbook_bullets:
            prompt_parts.append("\n**Playbook Bullets Used:**\n")
            for bullet in playbook_bullets:
                prompt_parts.append(f"- {bullet}\n")

        prompt_parts.append("""
\n**Your Task:**
Provide a detailed reflection analyzing what went wrong (or what went right).

**Output Format (JSON):**
```json
{
    "reasoning": "Your detailed analysis of the execution",
    "error_identification": "What specifically went wrong",
    "root_cause_analysis": "Why this error occurred and what was misunderstood",
    "correct_approach": "What should have been done instead",
    "key_insight": "The key principle or strategy to remember",
    "bullet_feedback": [
        {"bullet_id": "str-00001", "tag": "helpful"},
        {"bullet_id": "api-00002", "tag": "harmful"}
    ]
}
```

Tags: "helpful", "harmful", or "neutral"
""")

        return "".join(prompt_parts)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Reflector"""
        return """You are an expert code analyst and educator. Your role is to:

1. Analyze execution traces to identify errors and successes
2. Extract concrete, actionable insights
3. Diagnose root causes, not just symptoms
4. Provide specific corrections and strategies

Focus on:
- What went wrong and why
- What conceptual misunderstandings occurred
- What should be done differently
- What principles should be remembered

Be specific, concrete, and actionable in your insights."""

    def _default_reflection(self) -> Dict[str, Any]:
        """Return a default reflection if parsing fails"""
        return {
            "reasoning": "Unable to generate detailed reflection",
            "error_identification": "Unknown error",
            "root_cause_analysis": "Unable to determine root cause",
            "correct_approach": "Review the execution trace manually",
            "key_insight": "Ensure proper error handling and validation",
            "bullet_feedback": []
        }
