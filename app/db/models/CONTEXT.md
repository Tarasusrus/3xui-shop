# app/db/models — контекст модуля

SQLAlchemy async ORM модели. База — `_base.py` (`Base = DeclarativeBase`). Все модели импортируются через `__init__.py`.

## Модели

### User (`user.py`)
Основная запись пользователя бота.

Ключевые поля:
- `tg_id` — уникальный Telegram ID, используется как FK везде
- `vpn_id` — UUID строка (36 символов), ключ клиента в 3x-ui панели
- `server_id` — FK на Server, SET NULL при удалении сервера
- `is_trial_used` — флаг использования триала
- `language_code` — язык интерфейса (default: "en")
- `source_invite_name` — имя инвайта через который пришёл пользователь

**Нет поля subscription_end** — дата окончания подписки хранится только в 3x-ui панели, не локально. Это блокирует локальные reminders.

Связи: `transactions`, `activated_promocodes`, `server`, `referrals_sent`, `referral`.

### Transaction (`transaction.py`)
Запись о платеже.

Ключевые поля:
- `payment_id` — уникальный ID платежа (String 64), ключ для всех операций
- `subscription` — сериализованный `SubscriptionData.pack()` — содержит user_id, devices, duration, price, is_extend, is_change
- `status` — `TransactionStatus` enum: pending/completed/canceled/refunded/expired/rejected
- `payment_type` — String 32, nullable: `"sbp_manual"` / `"ton_manual"` / NULL для автогейтвеев
- `expires_at` — DateTime nullable: TTL для pending manual платежей (now + PENDING_PAYMENT_TTL_DAYS)

**Инвариант**: `payment_id` для manual платежей генерируется в гейтвее с префиксом: `sbp_<16hex>` / `ton_<16hex>`.

Classmethods:
- `get_by_id(payment_id)` — по payment_id (не по id PK)
- `get_pending_manual(tg_id)` — последний pending manual платёж пользователя
- `get_pending_for_admin()` — все pending manual (для очереди подтверждений)
- `get_user_history(tg_id, limit=20)` — история платежей пользователя

### Server (`server.py`)
3x-ui сервер. Связан с User через FK.

### Referral / ReferrerReward (`referral.py`, `referrer_reward.py`)
Реф-система 2 уровня. Схема +10/+3 дня подлежит замене на +30 за оплату.

### Promocode (`promocode.py`)
Промокоды. FK на activated_user.

### Invite (`invite.py`)
Инвайт-ссылки. `source_invite_name` в User ссылается на имя инвайта.

## Миграции

Путь: `app/db/migration/versions/`. Движок: Alembic.
**SQLite constraint**: enum changes и column renames требуют recreate-table паттерна (`CREATE new → INSERT SELECT → DROP old → RENAME`). Пример: `9aa6ddb8e352_update_transaction_status_enum.py`, `a1b2c3d4e5f6_transaction_manual_payments.py`.

Текущий head: `a1b2c3d4e5f6` (добавлены payment_type, expires_at в transactions + enum +expired/rejected).

## Паттерн classmethods

Все модели используют единый паттерн:
- `create(**kwargs)` — проверяет существование, добавляет, commit, rollback при IntegrityError
- `update(key, **kwargs)` — get → execute UPDATE → commit
- Методы принимают `session: AsyncSession` явно, не создают сессию внутри
