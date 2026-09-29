from fastmcp.exceptions import ToolError, ValidationError
from fastmcp.server.middleware import Middleware
from pydantic import ValidationError as PydanticValidationError


class SafeValidationMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except (ValidationError, PydanticValidationError):
            # Pydantic diagnostics include the rejected input. Do not echo it.
            raise ToolError("VALIDATION_ERROR: Invalid tool parameters.") from None
