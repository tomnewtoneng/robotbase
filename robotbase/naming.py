import re

def to_snake_identifier(name: str) -> str:
    """Convert a project name into a valid snake_case Python identifier."""
    snake = re.sub(r"[\s-]+", "_", name.strip().lower())
    snake = re.sub(r"[^a-z0-9_]", "", snake)
    if not snake or not snake.isidentifier():
        raise ValueError(f"Cannot derive a valid identifier from {name!r}")
    return snake
