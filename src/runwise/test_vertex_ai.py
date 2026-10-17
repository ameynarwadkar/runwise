"""
Standalone Smoke Test for Google Vertex AI Integration.

Verifies:
1. Direct official Google Gen AI SDK client initialized with Vertex AI and ADC.
2. Application tool-calling invocation path using LiteLLM Vertex AI bridge with TOOL_SCHEMAS.
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

# Ingest environment configuration from .env
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "research-agent-501111")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
MODEL_NAME = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")


def test_official_google_genai_sdk() -> bool:
    """Tests the official google-genai SDK using ADC."""
    print("\n--- [1/2] Testing Official google-genai SDK (Vertex AI + ADC) ---")
    try:
        from google import genai
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents="Say hello in one sentence.",
        )
        text = response.text or ""
        print(f"✅ Official SDK Response: {text.strip()}")
        assert len(text.strip()) > 0, "Response text was empty"
        return True
    except Exception as exc:
        print(f"❌ Official SDK Test Failed: {exc}")
        return False


def test_agent_model_invocation_and_tool_calling() -> bool:
    """Tests the agent's actual model invocation path with tool calling."""
    print("\n--- [2/2] Testing Agent Tool-Calling Invocation Path ---")
    try:
        import litellm
        from runwise.agent.dispatcher import TOOL_SCHEMAS

        # LiteLLM routes vertex_ai/* using VERTEXAI_PROJECT / VERTEXAI_LOCATION
        os.environ["VERTEXAI_PROJECT"] = PROJECT_ID
        os.environ["VERTEXAI_LOCATION"] = LOCATION

        model_identifier = f"vertex_ai/{MODEL_NAME}"
        print(f"📡 Invoking model: {model_identifier}")

        resp = litellm.completion(
            model=model_identifier,
            messages=[
                {"role": "user", "content": "What is the status of order ORD-101?"}
            ],
            tools=TOOL_SCHEMAS,
            temperature=0.0,
        )

        choice = resp.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None)

        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]
            func_name = tc.function.name
            func_args = tc.function.arguments
            print(f"✅ Agent Tool Call Succeeded: {func_name}({func_args})")
            assert func_name == "lookup_order", f"Unexpected tool invoked: {func_name}"
            return True
        else:
            print(f"⚠️ Model returned message without tool call: {choice.message.content}")
            return False

    except Exception as exc:
        print(f"❌ Agent Invocation Path Failed: {exc}")
        return False


def main() -> None:
    print(f"🚀 Running Vertex AI Integration Smoke Tests...")
    print(f"   Project:  {PROJECT_ID}")
    print(f"   Location: {LOCATION}")
    print(f"   Model:    {MODEL_NAME}")

    sdk_passed = test_official_google_genai_sdk()
    agent_path_passed = test_agent_model_invocation_and_tool_calling()

    if sdk_passed and agent_path_passed:
        print("\n🎉 ALL VERTEX AI SMOKE TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
