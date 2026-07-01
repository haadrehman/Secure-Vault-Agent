import asyncio
import httpx
import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Must be set before LiteLLM is imported anywhere in the import chain
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["LITELLM_TELEMETRY"] = "False"

print("Booting up Sovereign Vault environment... (This may take a few seconds)")

import logging
import warnings

# Suppress noisy library loggers
for logger_name in [
    "google.adk", "google.genai", "google.auth",
    "tenacity", "chromadb", "opentelemetry"
]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# Suppress experimental feature warnings
warnings.filterwarnings("ignore", category=UserWarning)

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

import threading
import itertools
import time

class Spinner:
    def __init__(self, message="Thinking"):
        self.message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._spin, daemon=True
        )

    def _spin(self):
        frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        for frame in itertools.cycle(frames):
            if self._stop_event.is_set():
                break
            print(f"\r{frame} {self.message}...", end="", flush=True)
            time.sleep(0.1)
        # Clear the spinner line when done
        print("\r" + " " * (len(self.message) + 6) + "\r", end="", flush=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        if not self._stop_event.is_set():
            self._stop_event.set()
            self._thread.join()

app = App(
    name="app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True)
)

def run_hitl_gate(mapping: dict, redacted_text: str) -> bool:
    """
    # SECURITY INVARIANT: This function must be called on every
    # query that sends data to any external or local LLM.
    # Bypassing this gate is a zero-leakage boundary violation.

    Mandatory security gate. Fires on every query regardless
    of which LLM will handle the reasoning step.
    Returns True if approved, False if rejected.
    """
    if not mapping:
        # No PII detected — no approval needed
        return True

    print("\n╔══════════════════════════════════════════════╗")
    print("║  🔒 REDACTION APPROVAL REQUIRED              ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  The following PII was detected and hidden:  ║")  # nosemgrep: print-unredacted-pii
    print("╠══════════════════════════════════════════════╣")
    for token, real_value in mapping.items():
        # Format: [PERSON_1]  →  John Michael Carter
        # Take first line only to strip Presidio over-capture (e.g. "John Carter\nDate")
        display_value = real_value.split("\n")[0].split("\r")[0].strip()
        row = f"  {token:<20} →  {display_value}"
        print(f"║ {row:<44}║")
    print("╠══════════════════════════════════════════════╣")
    print("║  The LLM will ONLY see the redacted tokens.  ║")  # nosemgrep: print-unredacted-pii
    print("╚══════════════════════════════════════════════╝")

    while True:
        choice = input(
            "\n✋ Approve sending redacted data to LLM? (y/n): "
        ).strip().lower()
        if choice == 'y':
            print("✅ Approved — processing query securely.\n")
            return True
        elif choice == 'n':
            print("❌ Rejected — query cancelled. Your data stays local.\n")
            return False
        else:
            print("Please enter y or n.")

def print_redaction_report(token_map: dict, retrieved_context: str):
    """
    Prints a Vault Transparency Report showing exactly what the LLM will receive.
    Inverts the token_map (token→value) to display as (value→token) for clarity.
    Only shows entities actually present in the retrieved context.
    """
    if not token_map:
        return

    # Only include tokens that appear in the context being sent to the LLM
    visible_entries = [
        (token, val.split("\n")[0].split("\r")[0].strip())
        for token, val in token_map.items()
        if token in retrieved_context
    ]
    if not visible_entries:
        return

    print("\n╔══════════════════════════════════════════════════╗")
    print("║  🔒 REDACTION REPORT — What the LLM received    ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Original                →  Redacted token       ║")  # nosemgrep: print-unredacted-pii
    print("╠══════════════════════════════════════════════════╣")
    for token, display_value in visible_entries:
        # Truncate long values so the box stays fixed-width
        truncated = display_value[:22] + "…" if len(display_value) > 22 else display_value
        row = f"  {truncated:<24}  →  {token}"
        print(f"║ {row:<50}║")
    print("╚══════════════════════════════════════════════════╝")
    print("📤 Sending redacted context to LLM...\n")

async def main():
    runner = InMemoryRunner(app=app)
    
    # Forcibly clear all LiteLLM log handlers — setLevel() alone is insufficient
    # because logging_worker spawns its own handler list at import time.
    import logging as _logging
    for _litellm_logger_name in [
        "LiteLLM",
        "litellm",
        "litellm.litellm_core_utils.logging_worker",
        "litellm.proxy",
        "litellm.router",
    ]:
        _lg = _logging.getLogger(_litellm_logger_name)
        _lg.handlers = []
        _lg.addHandler(_logging.NullHandler())
        _lg.propagate = False
    
    print("Welcome to the Sovereign Vault Agent CLI.")
    print("Type your query or 'exit' to quit.\n")
    
    user_id = "local_user"
    
    # Initialize session
    await runner.session_service.create_session(
        app_name="app", user_id=user_id, session_id="local_session"
    )
    
    # Check MCP server connectivity
    import subprocess
    from src.mcp_client import command, args
    try:
        process = subprocess.Popen([command] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process.wait(timeout=2)
            if process.returncode != 0:
                print("ERROR: MCP server failed to start — check src/mcp_server/server.py")
                sys.exit(1)
        except subprocess.TimeoutExpired:
            process.terminate()
    except Exception:
        print("ERROR: MCP server failed to start — check src/mcp_server/server.py")
        sys.exit(1)
        
    while True:
        try:
            user_input = input("User> ")
            if user_input.lower() in ["exit", "quit"]:
                break
                
            is_ingestion = "ingest" in user_input.lower()
            if is_ingestion:
                path = user_input.split()[-1]
                from src.mcp_server.server import WORKSPACE_DIR
                if not os.path.abspath(path).startswith(WORKSPACE_DIR):
                    print("\n⛔ Security: That path is outside your authorized workspace. Please use a path inside your project folder.\n")
                    continue
            
            with tracer.start_as_current_span("llm_inference") as span:
                span.set_attribute("query", user_input)
                
                spinner_msg = "Ingesting and securing your document" if is_ingestion else "Searching vault and redacting PII"
                spinner = Spinner(spinner_msg).start()
                
                import io
                import contextlib
                stderr_capture = io.StringIO()
                llm_yielded_text = False
                
                try:
                    # Run the agent
                    with contextlib.redirect_stderr(stderr_capture):
                        async for event in runner.run_async(
                            new_message=Content(role="user", parts=[Part.from_text(text=user_input)]),
                            user_id=user_id,
                            session_id="local_session"
                        ):
                            if getattr(event, "content", None) and getattr(event.content, "parts", None):
                                text_parts = [p.text for p in event.content.parts if getattr(p, "text", None)]
                                if text_parts:
                                    spinner.stop()
                                    print(f"\nVault> {''.join(text_parts)}")
                                    llm_yielded_text = True
                            
                        # Check for HITL pause
                        if hasattr(event, "long_running_tool_ids") and event.long_running_tool_ids:
                            spinner.stop()
                            for tool_id in event.long_running_tool_ids:
                                # Extract raw_preview and redacted_preview from tool calls if available
                                raw_preview = "Not provided"
                                redacted_preview = "Not provided"
                                
                                tool_calls = []
                                if getattr(event, "content", None) and getattr(event.content, "parts", None):
                                    for p in event.content.parts:
                                        if getattr(p, "function_call", None):
                                            tool_calls.append(p.function_call)
                                
                                # Build a token_map from tool args if available for the report
                                gemini_token_map = {}
                                for tc in tool_calls:
                                    tc_id = getattr(tc, "id", getattr(tc, "function_call_id", None))
                                    if tc_id == tool_id:
                                        args = getattr(tc, "args", {})
                                        if isinstance(args, dict):
                                            raw_preview = args.get("raw_preview", raw_preview)
                                            redacted_preview = args.get("redacted_preview", redacted_preview)
                                            gemini_token_map = args.get("token_map", {})
                                
                                # Show transparency report before Gemini inference
                                if gemini_token_map:
                                    print_redaction_report(gemini_token_map, redacted_preview)
                                else:
                                    # Fallback: plain display when no structured map available
                                    print(f"\n🔒 REDACTION REPORT: {raw_preview} → {redacted_preview}\n")
                                    print("📤 Sending redacted context to LLM...\n")
                                
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
                                        spinner = Spinner("Searching vault and redacting PII").start()
                                        with contextlib.redirect_stderr(stderr_capture):
                                            async for resume_event in runner.run_async(
                                                new_message=Content(role="user", parts=[Part(function_response=resume_response)]),
                                                user_id=user_id,
                                                session_id="local_session",
                                                invocation_id=invoc_id
                                            ):
                                                if getattr(resume_event, "content", None) and getattr(resume_event.content, "parts", None):
                                                    r_text_parts = [p.text for p in resume_event.content.parts if getattr(p, "text", None)]
                                                    if r_text_parts:
                                                        spinner.stop()
                                                        print(f"Vault> {''.join(r_text_parts)}")
                                                        llm_yielded_text = True
                                    else:
                                        print("Approval denied. Query cancelled.")
                                        resume_response = FunctionResponse(
                                            id=tool_id,
                                            name="request_redaction_approval",
                                            response={"status": "denied"}
                                        )
                                        spinner = Spinner("Searching vault and redacting PII").start()
                                        with contextlib.redirect_stderr(stderr_capture):
                                            async for resume_event in runner.run_async(
                                                new_message=Content(role="user", parts=[Part(function_response=resume_response)]),
                                                user_id=user_id,
                                                session_id="local_session",
                                                invocation_id=invoc_id
                                            ):
                                                if getattr(resume_event, "content", None) and getattr(resume_event.content, "parts", None):
                                                    r_text_parts = [p.text for p in resume_event.content.parts if getattr(p, "text", None)]
                                                    if r_text_parts:
                                                        spinner.stop()
                                                        print(f"Vault> {''.join(r_text_parts)}")
                                                        llm_yielded_text = True
                
                except (httpx.RequestError, TimeoutError, Exception) as e:
                    span.add_event("LLM Network Error", attributes={"exception.type": type(e).__name__, "exception.message": str(e)})
                    span.set_status(status=trace.Status(trace.StatusCode.ERROR))
                finally:
                    spinner.stop()
                    
                    stderr_content = stderr_capture.getvalue()
                    if stderr_content:
                        if "ResourceExhaustedError" in stderr_content or "RetryError" in stderr_content or "429 RESOURCE_EXHAUSTED" in stderr_content or "Exception" in stderr_content:
                            llm_yielded_text = False
                        if "ResourceExhaustedError" not in stderr_content and "RetryError" not in stderr_content and "429 RESOURCE_EXHAUSTED" not in stderr_content:
                            print(stderr_content, file=sys.stderr)
                    
                if not llm_yielded_text:
                    print("\n⚠  Gemini quota reached — switching to local mode...\n")
                    
                    # Determine intent
                    is_ingestion = "ingest" in user_input.lower()
                    
                    from src.mcp_server.server import handle_call_tool
                    import json
                    
                    if is_ingestion:
                        # Extract the path (naive extraction for fallback: just take the last word assuming it's the path)
                        path = user_input.split()[-1]
                        try:
                            result = await handle_call_tool("ingest_document", {"path": path})
                            if result and len(result) > 0:
                                print(f"Vault (Local Mode)> Gemini unavailable, but document was ingested locally — querying will use local fallback until cloud access is restored.\nResult: {result[0].text}\n")
                        except Exception as ingest_e:
                            print(f"Vault (Local Mode)> Cloud LLM is currently unavailable and local ingestion failed: {ingest_e}\n")
                        continue
                        
                    # --- QUERY FALLBACK ---
                    retrieved_context = None
                    token_map = {}  # Holds PII token → real value mapping for de-anonymisation
                    
                    # 1. Try to extract from session history if Gemini already called the tool before crashing
                    try:
                        session = await runner.session_service.get_session(app_name="app", user_id=user_id, session_id="local_session")
                        for content in reversed(session.history):
                            if hasattr(content, "parts"):
                                for part in content.parts:
                                    fr = getattr(part, "function_response", None)
                                    if fr and fr.name == "search_vault":
                                        # Tool responses are usually passed back as strings or dicts
                                        raw = fr.response if isinstance(fr.response, str) else str(fr.response)
                                        try:
                                            parsed = json.loads(raw)
                                            retrieved_context = parsed.get("redacted_text", raw)
                                            token_map = parsed.get("token_map", {})
                                        except Exception:
                                            retrieved_context = raw
                                        break
                            if retrieved_context:
                                break
                    except Exception:
                        pass
                        
                    # 2. If no context found in history, run the MCP tool manually!
                    if not retrieved_context:
                        try:
                            result = await handle_call_tool("search_vault", {"query": user_input})
                            if result and len(result) > 0:
                                # The MCP server returns a JSON string containing redacted_text and token_map
                                res_json = json.loads(result[0].text)
                                retrieved_context = res_json.get("redacted_text", result[0].text)
                                token_map = res_json.get("token_map", {})
                        except Exception:
                            pass
                            
                    if not retrieved_context:
                        print("\nVault (Local Mode)> Cloud LLM is currently unavailable. Your vault is intact and documents can still be ingested locally, but I cannot answer questions until Gemini access is restored or Ollama is fully configured with vault access.")
                        continue

                    # Step 2: HITL gate (local, no LLM) — MANDATORY
                    # Must fire before data is sent to any LLM, including local Ollama.
                    approved = run_hitl_gate(token_map, retrieved_context)
                    if not approved:
                        # User rejected — abort without calling any LLM
                        continue
                        
                    # Step 3: Use Ollama as a grounded reasoning engine
                    # Only reaches here after explicit human approval.
                    from google.adk.agents import Agent
                    fallback_agent = Agent(
                        name="fallback",
                        model=LiteLlm(model="ollama_chat/gemma2:2b"),
                        instruction="You are a grounded local assistant. Answer the user's question using ONLY the provided local vault context."
                    )
                    fallback_runner = InMemoryRunner(agent=fallback_agent, app_name="app")
                    await fallback_runner.session_service.create_session(
                        app_name="app", user_id=user_id, session_id="local_session"
                    )
                    
                    grounded_prompt = f"Using ONLY the following context retrieved from the user's local vault, answer the question. Do not invent any information not present in the context.\n\nContext:\n{retrieved_context}\n\nQuestion: {user_input}"
                    
                    # Print transparency report showing exactly what is sent to Ollama
                    print_redaction_report(token_map, retrieved_context)
                    
                    fb_spinner = Spinner("Running on local Ollama model").start()
                    try:
                        async for fb_event in fallback_runner.run_async(
                            new_message=Content(role="user", parts=[Part.from_text(text=grounded_prompt)]), 
                            user_id=user_id,
                            session_id="local_session"
                        ):
                            if getattr(fb_event, "content", None) and getattr(fb_event.content, "parts", None):
                                fb_text_parts = [p.text for p in fb_event.content.parts if getattr(p, "text", None)]
                                if fb_text_parts:
                                    fb_spinner.stop()
                                    raw_response = ''.join(fb_text_parts)
                                    # SECURITY: always restore PII tokens before displaying to user
                                    # regardless of whether Gemini or Ollama generated the response
                                    if token_map:
                                        from src.mcp_server.server import get_redactor
                                        # Take only first line of each real value to strip Presidio
                                        # over-capture (e.g. "John Carter\nDate of Birth" → "John Carter")
                                        clean_map = {
                                            token: val.split("\n")[0].split("\r")[0].strip()
                                            for token, val in token_map.items()
                                        }
                                        raw_response = get_redactor().restore_text(raw_response, clean_map)
                                    print(f"Vault (Local Mode)> {raw_response}\n")
                    finally:
                        fb_spinner.stop()
                            
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    asyncio.run(main())
