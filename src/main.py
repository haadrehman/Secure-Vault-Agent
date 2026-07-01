import asyncio
import httpx
import sys
import os

# Ensure the project root is in sys.path so 'app' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from opentelemetry import trace
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.apps import App, ResumabilityConfig
from google.adk.models.lite_llm import LiteLlm
from google.genai.types import FunctionResponse

from app.agent import root_agent
from src.core.telemetry import get_tracer

tracer = get_tracer()

app = App(
    name="app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True)
)

async def main():
    runner = InMemoryRunner(app=app)
    
    print("Welcome to the Sovereign Vault Agent CLI.")
    print("Type your query or 'exit' to quit.\n")
    
    user_id = "local_user"
    
    while True:
        try:
            user_input = input("User> ")
            if user_input.lower() in ["exit", "quit"]:
                break
            
            with tracer.start_as_current_span("llm_inference") as span:
                span.set_attribute("query", user_input)
                
                try:
                    # Run the agent
                    async for event in runner.run_async(
                        new_message=user_input,
                        user_id=user_id,
                        session_id="local_session"
                    ):
                        if event.text:
                            print(f"\nVault> {event.text}")
                            
                        # Check for HITL pause
                        if hasattr(event, "long_running_tool_ids") and event.long_running_tool_ids:
                            for tool_id in event.long_running_tool_ids:
                                # Extract raw_preview and redacted_preview from tool calls if available
                                raw_preview = "Not provided"
                                redacted_preview = "Not provided"
                                
                                tool_calls = getattr(event, "tool_calls", [])
                                for tc in tool_calls:
                                    # tc might be a FunctionCall object
                                    tc_id = getattr(tc, "id", getattr(tc, "function_call_id", None))
                                    if tc_id == tool_id:
                                        args = getattr(tc, "args", {})
                                        if isinstance(args, dict):
                                            raw_preview = args.get("raw_preview", raw_preview)
                                            redacted_preview = args.get("redacted_preview", redacted_preview)
                                            
                                print("\n[HITL SAFETY GATE] Redaction Approval Required")
                                print("Please review the following redaction:")
                                print("Raw Preview -> Redacted Preview")
                                print("--------------------------------")
                                print(f"{raw_preview} -> {redacted_preview}")
                                print("--------------------------------")
                                
                                with tracer.start_as_current_span("hitl_wait_latency") as hitl_span:
                                    approval = input("Approve redaction? (y/n): ")
                                    
                                    # Fetch invocation_id from event for resuming
                                    invoc_id = getattr(event, "invocation_id", getattr(event, "id", None))
                                    
                                    if approval.lower() == 'y':
                                        print("Approval granted. Resuming...")
                                        resume_response = FunctionResponse(
                                            id=tool_id,
                                            name="request_redaction_approval",
                                            response={"status": "approved"}
                                        )
                                        # Resume the runner
                                        async for resume_event in runner.run_async(
                                            new_message=[resume_response],
                                            user_id=user_id,
                                            session_id="local_session",
                                            invocation_id=invoc_id
                                        ):
                                            if resume_event.text:
                                                print(f"Vault> {resume_event.text}")
                                    else:
                                        print("Approval denied. Query cancelled.")
                                        resume_response = FunctionResponse(
                                            id=tool_id,
                                            name="request_redaction_approval",
                                            response={"status": "denied"}
                                        )
                                        async for resume_event in runner.run_async(
                                            new_message=[resume_response],
                                            user_id=user_id,
                                            session_id="local_session",
                                            invocation_id=invoc_id
                                        ):
                                            if resume_event.text:
                                                print(f"Vault> {resume_event.text}")
                
                except (httpx.RequestError, TimeoutError, Exception) as e:
                    # Log OpenTelemetry span event at WARNING level
                    span.add_event(
                        "LLM Network Error", 
                        attributes={"exception.type": type(e).__name__, "exception.message": str(e)}
                    )
                    span.set_status(status=trace.Status(trace.StatusCode.ERROR))
                    print(f"\n[WARNING] Network unavailable or LLM failed: {e}")
                    print("Falling back to local Ollama — network unavailable")
                    
                    # Fallback to local Ollama instance
                    from google.adk.agents import Agent
                    fallback_agent = Agent(
                        name="fallback",
                        model=LiteLlm(model="ollama_chat/gemma2:2b"),
                        instruction="You are a fallback responder. Provide a concise, helpful answer to the user."
                    )
                    fallback_runner = InMemoryRunner(agent=fallback_agent, app_name="app")
                    async for fb_event in fallback_runner.run_async(
                        new_message=user_input, 
                        user_id=user_id,
                        session_id="local_session"
                    ):
                        if fb_event.text:
                            print(f"\nVault (Fallback)> {fb_event.text}")
                            
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    asyncio.run(main())
