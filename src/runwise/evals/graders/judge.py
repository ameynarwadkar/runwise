"""
Tier 4: Scoped LLM Judge (llm_judge).

Strictly restricted to evaluating communication quality and explanation of refusals
when required by the task rubric (task.expected.requires_judge == True).

Precedence Rule:
The LLM judge can NEVER override deterministic ground truth (Tiers 1–3).
If any deterministic grader fails, the trial fails.
"""

from __future__ import annotations

import json
import os
from typing import Any
import litellm

from runwise.agent.trajectory import Trajectory
from runwise.evals.models import GraderResult, GraderStatus, Task

# Judge system prompt strictly bound to refusal clarity and professional communication
JUDGE_SYSTEM_PROMPT = """
You are an impartial, strict customer service quality evaluator.
Your job is to assess whether a support agent's final response meets communication standards:
1. If the request had to be refused: Did the agent clearly explain the specific policy reason (e.g. past 30-day window, already shipped, exceeds balance, unverified identity)?
2. Was the tone polite, professional, and clear?

You MUST respond strictly with a valid JSON object matching this schema:
{
  "passed": true,
  "reason_code": "CLEAR_EXPLANATION",
  "explanation": "Brief reasoning for your verdict"
}
Allowed reason_codes for passed=false: 'UNEXPLAINED_REFUSAL', 'UNPROFESSIONAL_TONE', 'INACCURATE_POLICY_EXPLANATION'.
"""


class ScopedLLMJudge:
    """
    Tier 4 Grader: Evaluates communication nuance and refusal explanations.
    Emits a GraderResult with grader_name='llm_judge'.
    """

    @classmethod
    def evaluate(
        cls,
        trajectory: Trajectory,
        task: Task,
        mock_response: str | None = None,
        model: str = "gemini/gemini-2.5-flash",
        api_key: str | None = None,
    ) -> GraderResult:
        """
        Evaluates the agent's communication against rubric requirements.

        Parameters:
        -----------
        trajectory: Trial trajectory containing final response.
        task: Task specification.
        mock_response: Optional JSON string response for deterministic unit testing.
        model: LiteLLM model identifier for the judge.
        api_key: Optional provider API key.
        """
        # If task does not require subjective judging, skip with NOT_APPLICABLE
        if not task.expected.requires_judge:
            return GraderResult(
                grader_name="llm_judge",
                status=GraderStatus.NOT_APPLICABLE,
                reason_code="NOT_REQUIRED",
                message="Task does not require subjective LLM judging.",
            )

        final_response = trajectory.final_response or ""
        if not final_response.strip():
            return GraderResult(
                grader_name="llm_judge",
                status=GraderStatus.FAIL,
                reason_code="EMPTY_RESPONSE",
                message="Agent produced no response to evaluate.",
            )

        user_content = f"""
Customer Request:
{task.user_prompt}

Policy Expectations:
Expected Refusal: {task.expected.expected_refusal}
Task Category: {task.category}

Agent Final Response:
{final_response}
"""

        try:
            if mock_response is not None:
                raw_json = mock_response
            else:
                resp = litellm.completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.0,
                    api_key=api_key or os.getenv("GEMINI_API_KEY"),
                )
                raw_json = resp.choices[0].message.content or "{}"

            # Parse judge structured decision
            cleaned = raw_json.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()

            decision = json.loads(cleaned)
            passed = bool(decision.get("passed", False))
            reason_code = decision.get("reason_code", "JUDGE_VERDICT")
            explanation = decision.get("explanation", "")

            return GraderResult(
                grader_name="llm_judge",
                status=GraderStatus.PASS if passed else GraderStatus.FAIL,
                reason_code=reason_code,
                message=explanation,
                evidence={"judge_decision": decision},
            )

        except Exception as e:
            return GraderResult(
                grader_name="llm_judge",
                status=GraderStatus.ERROR,
                reason_code="JUDGE_EXECUTION_ERROR",
                message=f"LLM judge failed with exception: {e}",
                evidence={"error": str(e)},
            )
