"""Placeholder upload validation worker."""

import asyncio


async def run() -> None:
    """Simulate continuous upload validation tasks."""

    while True:
        await asyncio.sleep(60)


def main() -> None:
    """Entry point for the upload validator worker."""

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
