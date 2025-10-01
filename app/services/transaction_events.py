"""Kafka integration for transaction change events."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

try:  # pragma: no cover - optional dependency may be absent in tests
    from kafka import KafkaConsumer, KafkaProducer
except ModuleNotFoundError:  # pragma: no cover - fallback for optional dependency
    KafkaConsumer = None  # type: ignore[assignment]
    KafkaProducer = None  # type: ignore[assignment]
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import Transaction
from app.services.reporting import TransactionReportingService

logger = logging.getLogger(__name__)


class TransactionEvent(BaseModel):
    """Serializable representation of a transaction lifecycle change."""

    event_id: str
    event_type: str
    transaction_id: str
    tenant_id: str
    shareholder_id: str | None
    plan_id: str | None
    type: str
    status: str
    amount: str
    currency: str
    reference: str | None
    occurred_at: datetime

    @classmethod
    def from_transaction(
        cls,
        *,
        transaction: Transaction,
        event_type: str,
        occurred_at: datetime | None = None,
    ) -> "TransactionEvent":
        occurred = occurred_at or datetime.now(timezone.utc)
        return cls(
            event_id=uuid4().hex,
            event_type=event_type,
            transaction_id=transaction.id,
            tenant_id=transaction.tenant_id,
            shareholder_id=transaction.shareholder_id,
            plan_id=transaction.plan_id,
            type=transaction.type.value,
            status=transaction.status.value,
            amount=str(transaction.amount),
            currency=transaction.currency,
            reference=transaction.reference,
            occurred_at=occurred,
        )


class TransactionEventPublisher:
    """Publishes transaction change events to Kafka."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        producer_factory: Callable[[], KafkaProducer] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._producer_factory = producer_factory or self._default_factory
        self._producer: KafkaProducer | None = None

    def _default_factory(self) -> KafkaProducer:
        if KafkaProducer is None:  # pragma: no cover - guard for missing dependency
            raise RuntimeError("kafka-python is required to publish transaction events")
        return KafkaProducer(
            bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        )

    def _get_producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = self._producer_factory()
        return self._producer

    def publish(self, transaction: Transaction, *, event_type: str) -> None:
        event = TransactionEvent.from_transaction(transaction=transaction, event_type=event_type)
        payload = event.model_dump(mode="json")
        producer = self._get_producer()
        logger.debug(
            "publishing transaction event",
            extra={"transaction_id": transaction.id, "event_type": event_type},
        )
        producer.send(self._settings.transaction_events_topic, value=payload)
        producer.flush()


class TransactionEventConsumer:
    """Consumes transaction events and updates reporting projections."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        settings: Settings | None = None,
        consumer_factory: Callable[[], KafkaConsumer] | None = None,
        reporting_service_factory: Callable[[Session], TransactionReportingService] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._consumer_factory = consumer_factory or self._default_factory
        self._reporting_service_factory = reporting_service_factory or TransactionReportingService
        self._consumer: KafkaConsumer | None = None

    def _default_factory(self) -> KafkaConsumer:
        if KafkaConsumer is None:  # pragma: no cover - guard for missing dependency
            raise RuntimeError("kafka-python is required to consume transaction events")
        return KafkaConsumer(
            self._settings.transaction_events_topic,
            bootstrap_servers=self._settings.kafka_bootstrap_servers.split(","),
            value_deserializer=lambda data: json.loads(data.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            group_id=self._settings.transaction_consumer_group,
        )

    def _get_consumer(self) -> KafkaConsumer:
        if self._consumer is None:
            self._consumer = self._consumer_factory()
        return self._consumer

    def poll_once(self) -> bool:
        consumer = self._get_consumer()
        records = consumer.poll(timeout_ms=1000)
        if not records:
            return False

        session = self._session_factory()
        reporter = self._reporting_service_factory(session)
        processed = False
        try:
            for partition_records in records.values():
                for record in partition_records:
                    event = TransactionEvent.model_validate(record.value)
                    reporter.apply_event(event)
                    processed = True
            if processed:
                session.commit()
                consumer.commit()
            else:
                session.rollback()
        except Exception:
            session.rollback()
            logger.exception("failed to apply transaction events")
            raise
        finally:
            session.close()
        return processed


__all__ = [
    "TransactionEvent",
    "TransactionEventConsumer",
    "TransactionEventPublisher",
]
