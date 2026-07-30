import os
import sys

bot_type = os.environ.get("BOT_TYPE", "")

if bot_type == "ops":
    from ops_bot import run_ops_bot

    run_ops_bot()
elif bot_type == "driver":
    from driver_bot import run_driver_bot

    run_driver_bot()
else:
    print(
        f"ERROR: BOT_TYPE must be 'ops' or 'driver', got: {bot_type!r}", file=sys.stderr
    )
    sys.exit(1)
