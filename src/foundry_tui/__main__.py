"""Entry point for Foundry TUI."""

import io
import logging
import sys

# Suppress hashlib blake2 errors from pyenv Python builds
# These are printed during import before we can configure logging
_stderr = sys.stderr
sys.stderr = io.StringIO()

# Now do imports that trigger the hashlib errors
from foundry_tui.app import FoundryApp  # noqa: E402
from foundry_tui.config import load_config, ConfigError  # noqa: E402

# Restore stderr
sys.stderr = _stderr

# Configure logging properly
logging.basicConfig(level=logging.WARNING)


def main() -> int:
    """Run the Foundry TUI application."""
    try:
        config = load_config()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    app = FoundryApp(config)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
