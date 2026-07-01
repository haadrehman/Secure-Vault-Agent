import asyncio
import httpx
import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Ensure the project root is in sys.path so 'app' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from opentelemetry import trace
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.apps import App, ResumabilityConfig
from google.adk.models.lite_llm import LiteLlm
from google.genai.types import FunctionResponse, Content, Part

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
    
    # Initialize session
    await runner.session_service.create_session(
        app_name="app", user_id=user_id, session_id="local_session"
    )
    
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
                        new_message=Content(role="user", parts=[Part.from_text(text=user_input)]),
                        user_id=user_id,
                        session_id="local_session"
                    ):
                        if getattr(event, "content", None) and getattr(event.content, "parts", None):
                            text_parts = [p.text for p in event.content.parts if getattr(p, "text", None)]
                            if text_parts:
                                print(f"\nVault> {''.join(text_parts)}")
                            
                        # Check for HITL pause
                        if hasattr(event, "long_running_tool_ids") and event.long_running_tool_ids:
                            for tool_id in event.long_running_tool_ids:
                                # Extract raw_preview and redacted_preview from tool calls if available
                                raw_preview = "Not provided"
                                redacted_preview = "Not provided"
                                
                                tool_calls = []
                                if getattr(event, "content", None) and getattr(event.content, "parts", None):
                                    for p in event.content.parts:
                                        if getattr(p, "function_call", None):
                                            tool_calls.append(p.function_call)
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
                                            new_message=Content(role="user", parts=[Part(function_response=resume_response)]),
                                            user_id=user_id,
                                            session_id="local_session",
                                            invocation_id=invoc_id
                                        ):
                                            if getattr(resume_event, "content", None) and getattr(resume_event.content, "parts", None):
                                                r_text_parts = [p.text for p in resume_event.content.parts if getattr(p, "text", None)]
                                                if r_text_parts:
                                                    print(f"Vault> {''.join(r_text_parts)}")
                                    else:
                                        print("Approval denied. Query cancelled.")
                                        resume_response = FunctionResponse(
                                            id=tool_id,
                                            name="request_redaction_approval",
                                            response={"status": "denied"}
                                        )
                                        async for resume_event in runner.run_async(
                                            new_message=Content(role="user", parts=[Part(function_response=resume_response)]),
                                            user_id=user_id,
                                            session_id="local_session",
                                            invocation_id=invoc_id
                                        ):
                                            if getattr(resume_event, "content", None) and getattr(resume_event.content, "parts", None):
                                                r_text_parts = [p.text for p in resume_event.content.parts if getattr(p, "text", None)]
                                                if r_text_parts:
                                                    print(f"Vault> {''.join(r_text_parts)}")
                
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
                    await fallback_runner.session_service.create_session(
                        app_name="app", user_id=user_id, session_id="local_session"
                    )
                    async for fb_event in fallback_runner.run_async(
                        new_message=Content(role="user", parts=[Part.from_text(text=user_input)]), 
                        user_id=user_id,
                        session_id="local_session"
                    ):
                        if getattr(fb_event, "content", None) and getattr(fb_event.content, "parts", None):
                            fb_text_parts = [p.text for p in fb_event.content.parts if getattr(p, "text", None)]
                            if fb_text_parts:
                                print(f"\nVault (Fallback)> {''.join(fb_text_parts)}")
                            
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    asyncio.run(main())
