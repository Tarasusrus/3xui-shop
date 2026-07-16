# app/bot/routers/subscription — контекст модуля

Основной пользовательский флоу: подписка, оплата, промокод, триал.

## Файлы

### subscription_handler.py
Навигация по шагам покупки: MAIN → DEVICES → DURATION → PAY (выбор метода).

Флоу:
1. `callback_subscription` — показ текущей подписки + кнопки buy/extend/change
2. `callback_subscription_process` (state=PROCESS) — вход «Купить подписку» → сразу форма выбора длительности
3. `callback_devices_selected` — выбор кол-ва устройств
4. `callback_duration_selected` — выбор длительности → показ `payment_method_keyboard`
5. `payment_method_keyboard` получает `gateway_factory.get_gateways()` — все зарегистрированные гейтвеи включая manual

**Инвариант (3xui-shop-41):** выбор тарифа и оплата НЕ зависят от наличия сервера.
`callback_subscription_process` больше не вызывает `get_available_server()` — раньше
он падал popup'ом «нет доступных серверов» и блокировал форму оплаты. Сервер нужен
только при создании VPN-клиента (`VPNService.create_client → assign_server_to_user`,
`vpn.py:147`), который сам возвращает False если пул пуст. Регресс покрыт
`tests/test_subscription_process_no_server.py`.
Кнопка «Активировать промокод» в `subscription_keyboard` заменена на «Пригласить друга»
(`NavReferral.MAIN`); отдельной кнопки-входа в промокод из UI больше нет (handler жив
для `F.data == NavSubscription.PROMOCODE`).

### payment_handler.py
Обработка выбора метода оплаты.

- `callback_payment_method_selected` — ловит `F.state.startswith(PAY)` (pay_sbp, pay_cryptopay)
- Бранч по `gateway.is_manual`:
  - False (CryptoPay) → `gateway.create_payment()` → `bot_invoice_url` → `pay_keyboard` (URL-кнопка)
  - True (SBP) → `gateway.create_payment()` → payment_id → `_build_manual_payment_text` + `manual_pay_keyboard`
- `_build_manual_payment_text(gateway, data)` — форматирует реквизиты SBP (phone/bank/price/currency) через `gateway.get_requisites()`

Реальные гейтвеи: SbpManual (manual) + CryptoPayGateway (auto, poll-based, эпик 3xui-shop-62). TON — фантом, удалён.
- `I_PAID` handler — `F.data.startswith("i_paid")`, парсит payment_id из callback → notify_admins с `admin_confirm_payment_keyboard`
- Admin confirm/reject — в `admin_tools/payment_confirm_handler.py` ✅

### keyboard.py
- `payment_method_keyboard` — кнопки по всем гейтвеям (name | price currency)
- `pay_keyboard(pay_url, callback_data)` — URL-кнопка для автогейтвеев
- `manual_pay_keyboard(payment_id, callback_data)` — callback-кнопка "Я оплатил" + назад
- `admin_confirm_payment_keyboard(payment_id)` — confirm/reject для админа

### trial_handler.py
Выдача триала. `gift_trial` через `services.vpn`.

### promocode_handler.py
FSM ввод промокода. Применяет скидку к SubscriptionData.

## Изменения 2026-04-19

`subscription_handler.py:callback_subscription` — добавлен параметр `session: AsyncSession`.
После получения `client_data` вызывается `Transaction.get_user_history(session, tg_id, limit=5)`.
Результат передаётся в `show_subscription(history=...)`.
`show_subscription` форматирует историю через i18n ключ `subscription:message:history` и добавляет к основному тексту.
Пустая история → секция не отображается.

## SubscriptionData (models/subscription_data.py)
CallbackData с prefix="subscription". Поля: state, is_extend, is_change, user_id, devices, duration, price.
`pack()` / `unpack()` — сериализация в строку для хранения в Transaction.subscription.

## Навигация (NavSubscription)
```
MAIN → DEVICES → DURATION → PAY (выбор метода)
                           ├─ PAY_YOOKASSA / PAY_CRYPTOMUS / PAY_HELEKET / PAY_YOOMONEY
                           ├─ PAY_SBP → I_PAID → admin CONFIRM_PAYMENT / REJECT_PAYMENT
                           └─ PAY_TON → I_PAID → admin CONFIRM_PAYMENT / REJECT_PAYMENT
```
