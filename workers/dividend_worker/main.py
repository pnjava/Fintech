"""Placeholder dividend processing worker."""

import asyncio


async def run() -> None:
    """Simulate long running dividend distribution processing."""

    while True:
        await asyncio.sleep(60)


def main() -> None:
    """Entry point for the dividend worker."""

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
