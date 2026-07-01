import asyncio
from google.genai.types import FunctionResponse, Content, Part

try:
    c = Content(role="user", parts=[Part.from_function_response(FunctionResponse(name="t", response={"a": "b"}))])
    print("Content creation works")
except Exception as e:
    print(e)
