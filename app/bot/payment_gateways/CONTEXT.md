# app/bot/payment_gateways — контекст модуля

Платёжные гейтвеи. Все наследуют `PaymentGateway` (`_gateway.py`).

## Базовый класс (`_gateway.py`)

Атрибуты класса:
- `name` — отображаемое название (lazy_gettext)
- `currency` — `Currency` enum (RUB или USD)
- `callback` — строка из `NavSubscription`, используется как ключ в фабрике
- `is_manual` — False для автогейтвеев, True для ручных (СБП, TON)
- `payment_type` — None для автогейтвеев, строковое значение PaymentType для ручных

Абстрактные методы:
- `create_payment(data: SubscriptionData) -> str` — для автогейтвеев возвращает pay_url; для manual — возвращает payment_id
- `handle_payment_succeeded(payment_id)` / `handle_payment_canceled(payment_id)`

Общая логика в базовом классе:
- `_on_payment_succeeded` — обновляет Transaction(COMPLETED), выдаёт реф-награды, уведомляет dev, вызывает vpn.create/extend/change_subscription
- `_on_payment_canceled` — обновляет Transaction(CANCELED), уведомляет dev

## Автогейтвеи (webhook-based)

| Класс | callback | currency | webhook |
|-------|----------|----------|---------|
| Cryptomus | pay_cryptomus | USD | /cryptomus |
| Heleket | pay_heleket | USD | /heleket |
| Yookassa | pay_yookassa | RUB | /yookassa |
| Yoomoney | pay_yoomoney | RUB | /yoomoney |

Флоу: `create_payment` → Transaction(PENDING) → возвращает URL → пользователь платит → webhook → `handle_payment_succeeded`.

## Manual гейтвеи (ручное подтверждение)

| Класс | callback | currency | payment_type |
|-------|----------|----------|--------------|
| SbpManual | pay_sbp | RUB | sbp_manual |
| TonManual | pay_ton | USD | ton_manual |

Флоу: `create_payment` → Transaction(PENDING, payment_type, expires_at) → возвращает payment_id → показываем реквизиты → юзер жмёт "Я оплатил" → notify_admins → admin confirm → `handle_payment_succeeded`.

**payment_id формат**: `sbp_<16hex>` / `ton_<16hex>`.
**expires_at**: `now() + config.shop.PENDING_PAYMENT_TTL_DAYS` (default 3 дня).

`get_requisites()` — возвращает dict с реквизитами из конфига:
- SBP: `{phone, bank}`
- TON: `{address, account, price_usdt}`

## GatewayFactory (`gateway_factory.py`)

Регистрирует гейтвеи по флагам конфига при старте. Ключ = `gateway.callback`.
`get_gateway(name)` — по callback-строке.
`get_gateways()` — все зарегистрированные (используется для отображения кнопок оплаты).

Порядок регистрации: Cryptomus → Heleket → Yookassa → Yoomoney → SbpManual → TonManual.

## Конфигурация (ShopConfig)

```
PAYMENT_SBP_ENABLED=true/false (default false)
SHOP_SBP_PHONE=+79001234567
SHOP_SBP_BANK=Сбербанк

PAYMENT_TON_ENABLED=true/false (default false)
SHOP_TON_ADDRESS=UQ...
SHOP_TON_ACCOUNT=@username
SHOP_TON_PRICE_USDT=1.0
```

## Зависимости

Гейтвеи получают через конструктор: `app, config, session, storage, bot, i18n, services`.
`services.vpn` — создание/продление/смена подписки.
`services.referral` — начисление реф-наград при успешной оплате.
`services.notification` — уведомления dev и юзера.

## Известные ограничения (MVP, не блокируют)

- **`_build_manual_payment_text` inline import** — `from sbp_manual import SbpManual` внутри функции как обход circular import. Рефакторинг: вынести функцию в отдельный модуль или использовать `payment_type` string вместо isinstance.
- **Silent TON fallthrough** — `_build_manual_payment_text` рендерит TON-шаблон для любого неизвестного manual гейтвея. При добавлении третьего manual гейтвея — добавить явную ветку или raise.
- **Expired TTL не блокирует confirm** — pending транзакция с истёкшим `expires_at` всё равно подтверждается. TTL сейчас только для cleanup-задачи, которая ещё не реализована.
- **Race condition частично закрыт** — `_on_payment_succeeded` теперь проверяет `status == COMPLETED` и выходит. Но check-and-update не атомарный (нет `SELECT FOR UPDATE`). Для малого числа админов приемлемо.
