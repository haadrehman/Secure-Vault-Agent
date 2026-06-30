import json
import importlib
from pprint import pprint

try:
    from google.adk.tools import LongRunningFunctionTool
    print("Found LongRunningFunctionTool in google.adk.tools")
except ImportError as e:
    print(f"Error importing LongRunningFunctionTool: {e}")

try:
    from google.adk.events import AgentEvent
    print(f"AgentEvent attributes: {dir(AgentEvent)}")
except Exception as e:
    print(e)
    
try:
    from google.adk.events import Event
    print(f"Event attributes: {dir(Event)}")
except Exception as e:
    print(e)
    
try:
    from google.genai import types
    print("genai.types:")
    for name in dir(types):
        if 'Function' in name:
            print(f" - {name}")
except Exception as e:
    print(e)
