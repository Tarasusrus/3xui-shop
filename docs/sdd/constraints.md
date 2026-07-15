# Architectural Constraints: Полный клиентский флоу VPN-бота

---

## 0. Контекст использования

Активные методы оплаты: СБП (ручной), TON (ручной).
Cryptomus, YooKassa, YooMoney — отключены, код не трогать.
Существующий `cancel_expired_transactions` (15-минутный таймер) рефакторится под `expires_at`.

---

## 1. DB Schema

### TransactionStatus

**MUST** добавить в `TransactionStatus` (`app/bot/utils/constants.py`):
```python
EXPIRED = "expired"
REJECTED = "rejected"
```

### PaymentType

**MUST** добавить:
```python
class PaymentType(Enum):
    SBP_MANUAL = "sbp_manual"
    TON_MANUAL = "ton_manual"
```

### Transaction table — новые колонки

**MUST** добавить через `batch_alter_table` (Alembic, SQLite):
- `expires_at: Mapped[datetime | None]` — TTL для PENDING-оплат
- `payment_type: Mapped[str | None]` — тип метода оплаты
- `retry_notified: Mapped[bool]` (default False, `server_default=false()`, NOT NULL) — флаг «юзер/dev уже уведомлены о задержке активации». Гейтит failure-уведомления в `_on_payment_succeeded`, чтобы поллер (ре-poll PENDING каждые 60с) не спамил. Миграция `d3e4f5a6b7c8`. См. 3xui-shop-67.

**MUST** `subscription` оставить NOT NULL; для ручных оплат писать фиктивный JSON `'{"type":"manual"}'`.

### Новые classmethod в Transaction

**MUST** добавить:
- `get_pending_manual(session, tg_id)` — ищет PENDING с `payment_type IN (sbp_manual, ton_manual)` для юзера (для блокировки повторного «Я оплатил»)
- `get_pending_for_admin(session, limit=10)` — **все** PENDING оплаты (СБП + TON), `ORDER BY created_at DESC`
- `get_user_history(session, tg_id, limit=5)` — последние 5 транзакций юзера

### User table

**MUST NOT** изменять. Поля `subscription_end` и `server_id` уже достаточны.

---

## 2. Config

**MUST** добавить в `ShopConfig`:
```python
SBP_PHONE: str          # SHOP_SBP_PHONE, default "+79039189074"
SBP_BANK: str           # SHOP_SBP_BANK, default "Цифра банк"
TON_ADDRESS: str        # SHOP_TON_ADDRESS, default ""
TON_ACCOUNT: str        # SHOP_TON_ACCOUNT, default "@Tapac1990"
TON_PRICE_USDT: float   # SHOP_TON_PRICE_USDT, default 1.0
PAYMENT_SBP_ENABLED: bool       # SHOP_PAYMENT_SBP_ENABLED, default False
PAYMENT_TON_ENABLED: bool       # SHOP_PAYMENT_TON_ENABLED, default False
PAYMENT_PERIOD_DAYS: int        # SHOP_PAYMENT_PERIOD_DAYS, default 30
PENDING_PAYMENT_TTL_DAYS: int   # SHOP_PENDING_PAYMENT_TTL_DAYS, default 3
```

**MUST** изменить `DEFAULT_SHOP_REFERRER_LEVEL_ONE_PERIOD` с 10 на 30.

---

## 3. Ручные оплаты (СБП + TON) — общий хэндлер

**MUST** создать `app/bot/routers/payment_manual/handler.py` — единый роутер для обоих методов.

**MUST** callback «Я оплатил» (для любого ручного метода):
1. Проверить `Transaction.get_pending_manual(session, user.tg_id)` — если есть, заблокировать.
2. `payment_id = uuid4().hex`.
3. `Transaction.create(status=PENDING, payment_type=<метод>, expires_at=now()+TTL, subscription='{"type":"manual"}')`.
4. Вызвать `services.vpn.extend_subscription(user, devices=1, duration=PAYMENT_PERIOD_DAYS)`.
5. Ответить пользователю.

**MUST NOT** вызывать `extend_subscription` повторно при подтверждении — уже выдано оптимистично.

**MUST** step 4: если `user.server_id is None` — вызывать `services.vpn.create_subscription(user, devices=1, duration=PAYMENT_PERIOD_DAYS)`, иначе `services.vpn.extend_subscription(...)`.

---

## 5. Admin Panel

**MUST** команда `/admin_payments` — фильтр `IsAdmin` (уже существует).
**MUST** показывать максимум 10 PENDING-оплат (MVP, без пагинации).
**MUST** callback-данные кнопок: `confirm_payment:<transaction_id>` и `reject_payment:<transaction_id>`.

### Подтверждение

**MUST** guard: `if transaction.status != PENDING: log WARNING; return`.
**MUST** вызвать `add_referrers_rewards_on_payment` если `REFERRER_REWARD_ENABLED`.

### Отклонение

**MUST** `remaining = min(PAYMENT_PERIOD_DAYS, max(0, (user.subscription_end - now()).days))`.
**MUST** `new_end = max(now(), subscription_end - timedelta(days=remaining))`.

---

## 6. Фоновые задачи

### Истечение pending-оплат (рефакторинг `cancel_expired_transactions`)

**MUST** изменить логику: вместо `created_at + 15 min` использовать `expires_at <= now()`.
- `payment_type IN (sbp_manual, ton_manual)` → статус `EXPIRED` + уведомление пользователя.
- `payment_type IS NULL` → статус `CANCELED` (старое поведение, обратная совместимость).

**MUST** передавать `bot: Bot` в задачу для отправки уведомлений.

### Напоминания об истечении подписки

**MUST** добавить новую задачу в `app/bot/tasks/subscription_reminders.py`.
**MUST** интервал: 60 минут.
**MUST** логика: найти пользователей, у которых `subscription_end` через 7 или 3 дня (±30 мин) и не было отправлено соответствующее напоминание.
**MUST** хранить факт отправки напоминания: добавить поля `reminded_7d_at` и `reminded_3d_at` в таблицу `users` (nullable DateTime).
**MUST** при продлении подписки (`extend_subscription` И `create_subscription` в `services/vpn.py`) сбросить оба поля в `NULL`.
**MUST NOT** слать повторно если `reminded_Xd_at IS NOT NULL`.

### Реферальные вознаграждения

**MUST NOT** изменять существующую `reward_pending_referrals_after_payment` (работает каждые 15 мин).
**MUST** добавить отправку уведомления рефереру после `process_referrer_rewards_after_payment`.
**MUST** при `TelegramAPIError` логировать WARNING, дни не откатывать.

---

## 7. Новые разделы (роутеры)

### Инструкции

**MUST** создать `app/bot/routers/instructions/handler.py`.
**MUST** устройство выбирается через `NavOnboarding` (уже существует: ANDROID, IPHONE, MAC, WINDOWS).
**MUST** для каждого устройства: ссылка на приложение (из `constants.py`), ссылка подписки (`vpn_service.get_key(user)`), текст из i18n.

### Поддержка

**MUST** создать `app/bot/routers/support/handler.py`.
**MUST** FSM State `waiting_support_message`.
**MUST** пересылать текст пользователя через `bot.send_message(config.bot.SUPPORT_ID, ...)`.
**MUST** при ошибке отправки — логировать ERROR, пользователю ответить «Не удалось отправить».

---

## 8. Рефакторинг реферальной системы

**MUST** удалить блок второго уровня из `add_referrers_rewards_on_payment`.
**MUST NOT** удалять `REFERRER_LEVEL_TWO_PERIOD` из конфига.
**MUST** `REFERRER_LEVEL_ONE_PERIOD` = 30 (из конфига, не хардкод).

---

## 9. i18n

**MUST** все новые строки добавить в `ru/bot.po` и `en/bot.po`.
**MUST** пересобрать `.mo`: `pybabel compile -d app/locales -D bot`.
**MUST NOT** хардкодить текст в Python.

---

## 10. Code Style

**MUST** Handler → Service → Model. Никакого SQL в роутерах.
**MUST** Инъекции: `session: AsyncSession`, `services: ServicesContainer`, `config: Config` — через middleware.
**MUST** Новые роутеры: `router = Router(name=__name__)`.
**MUST** Регистрировать все новые роутеры в `app/bot/routers/__init__.py`.

---

## 11. CryptoPay авто-гейтвей (эпик 3xui-shop-62)

**MUST** приём оплаты — POLLING `getInvoices` (бот в polling, публичного HTTPS нет).
**MUST NOT** webhook, `app.router.add_post`, проверка подписи — статус только по авторизованному `getInvoices`.
**MUST** прайсинг: `currency_type='fiat'`, `fiat='RUB'`, `amount=data.price`. Новый `Currency` НЕ вводить.
**MUST** активация идемпотентна: `_on_payment_succeeded` пропускает уже `COMPLETED` (повторный poll не выдаёт подписку дважды).
**MUST** `payment_id` = `cryptopay_{invoice_id}` (связь транзакции с инвойсом для poller'а).
**MUST** `PAYMENT_CRYPTOPAY_ENABLED=true` + пустой `CRYPTOPAY_TOKEN` → fail-fast при старте.
**MUST** API-клиент — raw HTTP (aiohttp), без стороннего SDK (нет дрейфа импортов/сигнатур).
**MUST** `getInvoices` resilient — сетевая/API ошибка не роняет poller (возврат `[]`).
**MUST NOT** миграции БД — `payment_type`/`expires_at` уже существуют.
