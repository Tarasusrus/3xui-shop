# app/bot/tasks — контекст модуля

Background задачи на APScheduler (AsyncIOScheduler). Регистрируются в `app/__main__.py:on_startup`.

## Файлы

### transactions.py
Интервал: 15 мин. Отменяет просроченные транзакции:
- Manual (sbp/ton) с `expires_at <= utcnow()` → EXPIRED + notify пользователя
- NULL payment_type → CANCELED
Принимает: `session, bot, i18n`

### referral.py
Интервал: 15 мин. Обрабатывает pending ReferrerReward (rewarded_at IS NULL):
- `referral_service.process_referrer_rewards_after_payment(reward)` → если success → `bot.send_message` с `referral:ntf:bonus_received`
- TelegramAPIError → WARNING лог
Принимает: `session_factory, referral_service, bot, i18n`

### subscription_expiry.py
Интервал: 15 мин. Уведомляет пользователей у которых подписка истекает через ≤24ч.
Redis-дедупликация (ключ `user:notified:{tg_id}`, TTL 24ч).
Принимает: `session_factory, redis, i18n, vpn_service, notification_service`

### subscription_reminders.py (добавлен 2026-04-19)
Интервал: 60 мин. Напоминания за 7 и 3 дня до окончания подписки:
- 7±0.5 дней И `reminded_7d_at IS NULL` → отправить `subscription:ntf:reminder_7d`, записать `reminded_7d_at`
- 3±0.5 дней И `reminded_3d_at IS NULL` → отправить `subscription:ntf:reminder_3d`, записать `reminded_3d_at`
- Сброс reminded полей: `vpn.py:extend_subscription` после успешного `update_client`
Принимает: `session_factory, i18n, vpn_service, notification_service`

### cryptopay_poll.py (добавлен 2026-07-14, эпик 3xui-shop-62)
Интервал: `config.shop.CRYPTOPAY_POLL_INTERVAL_SEC` (default 60с). Запускается в
`on_startup` только если `PAYMENT_CRYPTOPAY_ENABLED`.
- `Transaction.get_pending_cryptopay()` → список PENDING cryptopay-транзакций
- извлекает `invoice_id` из `payment_id` (`cryptopay_{id}`), чанк по 100
- `gateway.api.get_invoices(status='paid', invoice_ids=chunk)` → **re-check `invoice['status']=='paid'`**
  (защита, если API проигнорит фильтр при invoice_ids) → `gateway.handle_payment_succeeded(make_payment_id(invoice_id))`
- Идемпотентно: `_on_payment_succeeded` пропускает уже COMPLETED. Повторный poll не
  выдаёт подписку дважды.
Принимает: `session_factory, gateway (CryptoPayGateway), interval_sec`

## Инварианты

- `subscription_end` не в User ORM — из `vpn_service.get_client_data(user)._expiry_time` (ms, -1=unlimited)
- Aware UTC (`datetime.now(timezone.utc)`) — в subscription tasks
- Naive UTC (`datetime.utcnow()`) — в transactions task (т.к. `expires_at` хранится naive)
- Каждый scheduler создаёт свой `AsyncIOScheduler` — не шарятся
