# app/bot/routers/admin_tools — контекст модуля

Административные инструменты: управление серверами, пользователями, промокодами, уведомлениями, подтверждение платежей.

## Файлы

### payment_confirm_handler.py (Phase-2, новый)
Ручное подтверждение/отклонение manual-платежей (СБП, TON).

- `callback_confirm_payment` — `F.data.startswith("confirm_payment")` + `IsAdmin()`
  - Достаёт Transaction по payment_id
  - Проверяет статус == PENDING (иначе popup "уже обработан")
  - Маппит `transaction.payment_type` → callback через `_PAYMENT_TYPE_TO_CALLBACK`
  - Вызывает `gateway.handle_payment_succeeded(payment_id)` → VPN создаётся/продлевается
- `callback_reject_payment` — `F.data.startswith("reject_payment")` + `IsAdmin()`
  - Обновляет Transaction(REJECTED)
  - `notify_by_id(chat_id=transaction.tg_id, ...)` — уведомляет пользователя

**_PAYMENT_TYPE_TO_CALLBACK**:
```python
{"sbp_manual": NavSubscription.PAY_SBP, "ton_manual": NavSubscription.PAY_TON}
```

### admin_tools_handler.py
Главное меню админ-панели. `NavAdminTools.MAIN`.

### backup_handler.py / restart_handler.py / maintenance_handler.py
Утилиты: бэкап БД, рестарт бота, режим обслуживания.

### server_handler.py
CRUD серверов: добавить, удалить, показать, синхронизировать.

### invites_handler.py
Управление инвайт-ссылками. FSM: имя → создание.

### notification_handler.py
Рассылка пользователям: одному или всем. FSM ввода текста.

### promocode_handler.py
CRUD промокодов. FSM создания/редактирования.

### statistics_handler.py
Показ статистики бота.

### user_handler.py
Редактирование пользователей.

## Фильтры
Все хендлеры используют `IsAdmin()` фильтр. Некоторые также `IsDev()`.

## Навигация (NavAdminTools)
Ключевые коллбэки для manual-оплаты:
- `CONFIRM_PAYMENT = "confirm_payment"` + `":{payment_id}"`
- `REJECT_PAYMENT = "reject_payment"` + `":{payment_id}"`
