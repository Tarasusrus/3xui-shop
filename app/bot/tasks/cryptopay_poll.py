"""Background poller for CryptoPay invoices.

The bot runs in polling mode with no public HTTPS endpoint, so there is no
webhook. Instead this task periodically lists our pending CryptoPay invoices via
the authorized getInvoices call and activates the ones marked 'paid'.

Activation is idempotent: it delegates to CryptoPayGateway.handle_payment_succeeded,
which routes to PaymentGateway._on_payment_succeeded — that method skips any
transaction already in status COMPLETED. So re-polling a still-processing invoice
can never grant a subscription twice.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.payment_gateways.cryptopay import (
    CryptoPayGateway,
    invoice_id_from_payment_id,
    make_payment_id,
)
from app.db.models import Transaction

logger = logging.getLogger(__name__)

_INVOICE_CHUNK = 100  # getInvoices max ids per request


def _chunk(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def poll_paid_invoices(
    session_factory: async_sessionmaker,
    gateway: CryptoPayGateway,
) -> None:
    async with session_factory() as session:
        pending = await Transaction.get_pending_cryptopay(session=session)

    if not pending:
        logger.debug("[CryptoPay poll] No pending invoices.")
        return

    invoice_ids: list[str] = []
    for transaction in pending:
        invoice_id = invoice_id_from_payment_id(transaction.payment_id)
        if invoice_id:
            invoice_ids.append(invoice_id)

    if not invoice_ids:
        return

    logger.info(f"[CryptoPay poll] Checking {len(invoice_ids)} pending invoice(s).")

    for chunk in _chunk(invoice_ids, _INVOICE_CHUNK):
        invoices = await gateway.api.get_invoices(status="paid", invoice_ids=chunk)
        for invoice in invoices:
            invoice_id = invoice.get("invoice_id")
            if invoice_id is None:
                continue
            # Defensive: only activate invoices Crypto Pay reports as paid. The
            # status filter is passed to getInvoices, but we re-check here so a
            # non-paid invoice can never grant a subscription even if the API
            # ignores the filter when invoice_ids is set.
            if invoice.get("status") != "paid":
                continue
            payment_id = make_payment_id(invoice_id)
            try:
                await gateway.handle_payment_succeeded(payment_id)
            except Exception:
                logger.exception(
                    f"[CryptoPay poll] Activation failed for {payment_id}"
                )


def start_scheduler(
    session_factory: async_sessionmaker,
    gateway: CryptoPayGateway,
    interval_sec: int,
) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_paid_invoices,
        "interval",
        seconds=interval_sec,
        args=[session_factory, gateway],
    )
    scheduler.start()
    logger.info(f"CryptoPay poller started (interval={interval_sec}s).")
