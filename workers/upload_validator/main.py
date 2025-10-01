"""Async worker validating shareholder uploads."""
from __future__ import annotations

import asyncio
import json
import logging

import boto3

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.uploads import (
    ShareholderUploadMessage,
    ShareholderUploadService,
    process_upload_message,
)

logger = logging.getLogger(__name__)


class UploadValidatorWorker:
    """Background worker that validates uploaded shareholder files."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._service = ShareholderUploadService(settings=self._settings)
        self._s3_client = boto3.client(
            "s3",
            region_name=self._settings.aws_region,
            endpoint_url=self._settings.s3_endpoint_url,
        )
        self._sqs_client = boto3.client(
            "sqs",
            region_name=self._settings.aws_region,
            endpoint_url=self._settings.sqs_endpoint_url,
        )

    async def run_forever(self) -> None:
        logger.info("upload validator worker started")
        while True:
            processed = await self._poll_once()
            if not processed:
                await asyncio.sleep(self._settings.upload_validator_poll_interval_seconds)

    async def _poll_once(self) -> bool:
        response = await asyncio.to_thread(
            self._sqs_client.receive_message,
            QueueUrl=self._settings.upload_queue_url,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=1,
        )
        messages = response.get("Messages", [])
        if not messages:
            return False

        for message in messages:
            body = message.get("Body", "")
            receipt = message.get("ReceiptHandle")
            try:
                payload = ShareholderUploadMessage.from_json(body)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("invalid upload message", extra={"body": body})
                await asyncio.to_thread(
                    self._sqs_client.send_message,
                    QueueUrl=self._settings.upload_dead_letter_queue_url,
                    MessageBody=json.dumps({"body": body, "error": str(exc)}),
                )
            else:
                try:
                    await asyncio.to_thread(
                        process_upload_message,
                        message=payload,
                        session_factory=SessionLocal,
                        service=self._service,
                        s3_client=self._s3_client,
                        sqs_client=self._sqs_client,
                        dead_letter_queue_url=self._settings.upload_dead_letter_queue_url,
                    )
                except Exception as exc:  # pragma: no cover - worker logs unexpected failures
                    logger.exception(
                        "failed to process upload",
                        extra={"upload_id": payload.upload_id, "error": str(exc)},
                    )
                    await asyncio.to_thread(
                        self._sqs_client.send_message,
                        QueueUrl=self._settings.upload_dead_letter_queue_url,
                        MessageBody=json.dumps(
                            {"upload_id": payload.upload_id, "error": str(exc)}
                        ),
                    )
            finally:
                if receipt:
                    await asyncio.to_thread(
                        self._sqs_client.delete_message,
                        QueueUrl=self._settings.upload_queue_url,
                        ReceiptHandle=receipt,
                    )
        return True


async def run() -> None:
    worker = UploadValidatorWorker()
    await worker.run_forever()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:  # pragma: no cover - CLI signal handling
        logger.info("upload validator worker stopped")


if __name__ == "__main__":
    main()
