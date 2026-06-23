# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

_logger = logging.getLogger(__name__)

# Populated by each tool module at import time via register()
_REGISTRY: dict = {}


def register(tool_class):
    """Register a tool class. Use as a class decorator."""
    _REGISTRY[tool_class.name] = tool_class
    return tool_class


def get_tool(name: str):
    """Return tool class by name, or None."""
    return _REGISTRY.get(name)


def all_tools() -> list:
    """Return list of all registered tool classes."""
    return list(_REGISTRY.values())


def get_tools_schema() -> list:
    """Return MCP tools/list schema for all registered tools."""
    return [
        {
            "name": cls.name,
            "description": cls.description,
            "inputSchema": cls.input_schema,
        }
        for cls in _REGISTRY.values()
    ]
