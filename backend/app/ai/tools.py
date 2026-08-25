"""Phase 8: Tool & Function Calling Safety Boundary.

In accordance with Phase 8 security architecture:
Dynamic runtime tool execution is intentionally constrained and isolated.
Arbitrary shell/code execution is forbidden.
"""

import inspect
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel
from app.ai.exceptions import AISecurityError


class SafeToolRegistry:
    """Registry for safe, statically declared tools with validated inputs."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable[..., Any]
    ) -> None:
        """Register a strictly typed, authorized tool handler."""
        if not name or not callable(handler):
            raise ValueError("Tool name and callable handler required.")
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters_schema,
            "handler": handler
        }

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a registered tool with security boundary enforcement."""
        if name not in self._tools:
            raise AISecurityError(f"Unauthorized tool invocation: '{name}' is not in safe registry.")
        
        tool = self._tools[name]
        handler = tool["handler"]
        if inspect.iscoroutinefunction(handler):
            return await handler(**arguments)
        return handler(**arguments)
