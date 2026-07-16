# app/bot/payment_gateways — контекст модуля

Платёжные гейтвеи. Все наследуют `PaymentGateway` (`_gateway.py`).

## Базовый класс (`_gateway.py`)

Атрибуты класса:
- `name` — отображаемое название (lazy_gettext)
- `currency` — `Currency` enum (RUB или USD)
- `callback` — строка из `NavSubscription`, используется как ключ в фабрике
- `is_manual` — False для авто-гейтвеев (CryptoPay), True для ручных (СБП)
- `payment_type` — строковое значение `PaymentType` (`sbp_manual` / `cryptopay`)

Абстрактные методы:
- `create_payment(data: SubscriptionData) -> str` — для автогейтвеев возвращает pay_url; для manual — возвращает payment_id
- `handle_payment_succeeded(payment_id)` / `handle_payment_canceled(payment_id)`

Общая логика в базовом классе:
- `_on_payment_succeeded` — **сначала** активирует VPN (`_activate_subscription`), и **только при успехе** переводит Transaction→COMPLETED, выдаёт реф-награды, уведомляет dev + юзера. См. инвариант «activation-before-COMPLETED» ниже (3xui-shop-64).
- `_activate_subscription(user, data) -> bool` — роутит на vpn.extend/change/create_subscription. Для create: `create_subscription` вернул True ИЛИ `is_client_exists(user)` → успех (различаем «уже создан» от «провал 3x-ui», сигнатуру vpn не меняем).
- `_notify_activation_success(user, data)` — success-уведомление по ветке (purchase/extend/change), вызывается только после COMPLETED.
- `_on_payment_canceled` — обновляет Transaction(CANCELED), уведомляет dev

## Фактический инвентарь гейтвеев (2026-07-14)

В форке реально существуют **только два** файла-гейтвея: `sbp_manual.py`, `cryptopay.py`.
Cryptomus/Heleket/Yookassa/Yoomoney/TonManual — **фантомы** из апстрима, файлов нет.

## Авто-гейтвеи (без ручного подтверждения)

| Класс | callback | currency | приём оплаты |
|-------|----------|----------|--------------|
| CryptoPayGateway | pay_cryptopay | RUB (fiat) | POLLING getInvoices |

### CryptoPayGateway (`cryptopay.py` + `cryptopay_api.py`) — эпик 3xui-shop-62

Первый авто-гейтвей форка. Приём криптооплаты через Crypto Pay API (@CryptoBot),
**без публичного HTTPS-вебхука** (бот в polling-режиме).

Флоу:
`create_payment` → `api.create_invoice(currency_type='fiat', fiat='RUB', amount=data.price)`
→ Transaction(PENDING, payment_type='cryptopay', expires_at, `payment_id=cryptopay_{invoice_id}`)
→ возвращает `bot_invoice_url` (URL-кнопка «Оплатить»)
→ фоновый поллер `tasks/cryptopay_poll.py` вызывает `getInvoices(status='paid')`
→ `handle_payment_succeeded` (идемпотентно через `_on_payment_succeeded` COMPLETED-skip).

- **Нет webhook, нет проверки подписи** — статус читается авторизованным `getInvoices`.
- **Прайсинг**: `fiat='RUB'`, `amount=data.price`. Новый `Currency` НЕ вводится.
- `payment_id` формат: `cryptopay_<invoice_id>`. Хелперы `make_payment_id` /
  `invoice_id_from_payment_id`.
- `api` (`CryptoPayAPI`) — raw aiohttp, без SDK (нет дрейфа импортов). `get_invoices`
  resilient (→ `[]` на сетевой/API ошибке), `create_invoice` кидает `CryptoPayAPIError`.
- base URL: mainnet `pay.crypt.bot/api`, testnet `testnet-pay.crypt.bot/api`;
  header `Crypto-Pay-API-Token`.

## Manual гейтвеи (ручное подтверждение)

| Класс | callback | currency | payment_type |
|-------|----------|----------|--------------|
| SbpManual | pay_sbp | RUB | sbp_manual |

Флоу: `create_payment` → Transaction(PENDING, payment_type, expires_at) → возвращает payment_id → показываем реквизиты → юзер жмёт "Я оплатил" → notify_admins → admin confirm → `handle_payment_succeeded`.

**payment_id формат**: `sbp_<16hex>`.
**expires_at**: `now() + config.shop.PENDING_PAYMENT_TTL_DAYS` (default 3 дня).

`get_requisites()` — возвращает dict с реквизитами из конфига:
- SBP: `{phone, bank}`

## GatewayFactory (`gateway_factory.py`)

Регистрирует гейтвеи по флагам конфига при старте. Ключ = `gateway.callback`.
`get_gateway(name)` — по callback-строке.
`get_gateways()` — все зарегистрированные (используется для отображения кнопок оплаты).

Порядок регистрации: SbpManual (if `PAYMENT_SBP_ENABLED`) → CryptoPayGateway (if `PAYMENT_CRYPTOPAY_ENABLED`).

## Конфигурация (ShopConfig)

```
SHOP_PAYMENT_SBP_ENABLED=true/false (default FALSE с 3xui-shop-69 — прод на CryptoPay-only)
SHOP_SBP_PHONE=+79001234567
SHOP_SBP_BANK=Сбербанк

SHOP_PAYMENT_CRYPTOPAY_ENABLED=true/false (default false)
SHOP_CRYPTOPAY_TOKEN=<Crypto Pay API token>   # ENABLED=true + пустой → fail-fast при старте
SHOP_CRYPTOPAY_TESTNET=true/false (default false)
SHOP_CRYPTOPAY_POLL_INTERVAL_SEC=60 (min 10)
```

## Зависимости

Гейтвеи получают через конструктор: `app, config, session, storage, bot, i18n, services`.
`services.vpn` — создание/продление/смена подписки.
`services.referral` — начисление реф-наград при успешной оплате.
`services.notification` — уведомления dev и юзера.

## Известные ограничения (MVP, не блокируют)

- **`_build_manual_payment_text` inline import** — `from sbp_manual import SbpManual` внутри функции как обход circular import. Рефакторинг: вынести функцию в отдельный модуль или использовать `payment_type` string вместо isinstance.
## CryptoPay — инварианты устойчивости (фикс 3xui-shop-65, ревью эпика 62)

- **Persistent `aiohttp.ClientSession`** — `CryptoPayAPI` держит одну сессию (lazy-init на первом вызове внутри loop, reused между poll'ами). `close()` вызывается в `on_shutdown` через `gateway.close()` (базовый `PaymentGateway.close()` — no-op, CryptoPay override закрывает api). Пересоздаётся, если была закрыта.
- **Poller re-check `status=='paid'`** — `poll_paid_invoices` активирует инвойс только если `invoice['status']=='paid'`, даже если `getInvoices` проигнорит фильтр при заданных `invoice_ids`. Защита от выдачи подписки за неоплаченный инвойс.
- **Grace-буфер БД vs invoice** — `expires_at` в БД = `now + invoice_ttl + _DB_EXPIRY_GRACE_SEC` (3600с). БД-транзакция живёт дольше инвойса → оплата в последнюю секунду ловится поллером до отмены cleanup-задачей. Оплата возможна только пока инвойс активен.
- **`create_payment` fail-loud** — если `Transaction.create` вернул None (нет PENDING-строки → поллер не активирует), кидается `RuntimeError`; хендлер `callback_payment_method_selected` ловит и показывает `payment:popup:error` вместо битого URL.
- **Expired TTL не блокирует confirm** — pending транзакция с истёкшим `expires_at` всё равно подтверждается. TTL сейчас только для cleanup-задачи, которая ещё не реализована.
- **Race condition частично закрыт** — `_on_payment_succeeded` теперь проверяет `status == COMPLETED` и выходит. Но check-and-update не атомарный (нет `SELECT FOR UPDATE`). Для малого числа админов приемлемо.
- **Идемпотентное продление на retry (3xui-shop-68)** — перед активацией проверяется `transaction.activation_applied`: если True (VPN уже выдан на прошлой попытке) — активация пропускается, сразу переход к COMPLETED. После успешной активации флаг персистится ДО COMPLETED-записи. Иначе окно «extend применён на 3x-ui, но COMPLETED-write упал» → поллер продлевал бы повторно (дни additive, устройства уже replace). `change` был идемпотентен и так (replace_duration=True). Durable-колонка `Transaction.activation_applied`, миграция `e4f5a6b7c8d9`. Регресс: `test_extend_not_double_applied_when_completed_write_fails`.
- **Notify-once на retry (3xui-shop-67)** — обе failure-ветки (`user is None` и `not activated`) шлют уведомления только если `not transaction.retry_notified`, после отправки выставляют флаг через `_mark_retry_notified` (`Transaction.update(retry_notified=True)`). Иначе поллер (ре-poll PENDING каждые 60с) спамил бы юзера/dev каждый цикл. Флаг durable (колонка `Transaction.retry_notified`, миграция `d3e4f5a6b7c8`), не сбрасывается — при восстановлении 3x-ui успешный путь всё равно шлёт `notify_purchase_success`. Регресс: `test_*_notifies_*_once_across_retries`.
- **Guard user=None (3xui-shop-66)** — `_on_payment_succeeded` при `User.get → None` (удалённый/рассинхронизированный аккаунт) НЕ дереференсит user: логирует, шлёт dev-алерт (plain text, без i18n), оставляет транзакцию PENDING и выходит. Иначе `user.tg_id` → AttributeError на каждом цикле поллера = вечный crash-loop. Регресс: `test_missing_user_does_not_crash_and_alerts_dev`.
- **Инвариант activation-before-COMPLETED (3xui-shop-64)** — VPN активируется ДО перевода Transaction→COMPLETED. Если 3x-ui недоступен / пул пуст → активация вернёт False, транзакция остаётся PENDING → CryptoPay поллер (`get_pending_cryptopay`, 60с) ретраит, SBP — админ повторно жмёт confirm. Юзеру шлётся `payment:message:activation_pending`, dev — `payment:event:activation_failed`. **Все exactly-once побочки** (COMPLETED, реф-награды, success-notify) — строго за успехом активации, иначе на ретрае поллера они бы задвоились. «Клиент уже существует» = идемпотентный успех (не провал), иначе вечный retry-loop. Регресс: `tests/test_payment_activation_ordering.py`. Новые локаль-ключи требуют `pybabel compile -d app/locales -D bot` (.mo gitignored, COPY в Docker).
