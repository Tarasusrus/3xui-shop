# Constraints: Меню v2

---

## C-1: Реиспользование существующих механизмов

**C-1.1** `_try_auto_gift_trial()` — уже реализована в `subscription/trial_handler.py`. Вызывать её из `/start` handler'а, не дублировать логику.

**C-1.2** FSM онбординга (device → email → +4д) — реализован в `app/bot/routers/onboarding/`. Кнопка «Заполнить профиль» должна вызывать этот флоу, а не новый.

**C-1.3** `ReferralService.add_referrers_rewards_on_payment()` — реализован. Вызывать из admin confirm handler, не трогать сервис.

**C-1.4** Subscription reminders — реализованы в `subscription_reminders.py`. Не изменять.

**C-1.5** Admin confirm/reject (NavAdminTools.CONFIRM_PAYMENT / REJECT_PAYMENT) — реализован в phase-2. Проверить работоспособность, не переписывать.

---

## C-2: Меню

**C-2.1** `main_menu_keyboard()` в `app/bot/routers/main_menu/keyboard.py` — переработать под новую структуру 6 кнопок. Удалить условные кнопки триала («Получить триал», «Получить реферальный триал») из главного меню.

**C-2.2** Кнопка «💳 Оплатить» — новая в главном меню. Callback: `NavSubscription.PAY` (уже существует в navigation.py).

**C-2.3** Кнопка «📖 Инструкции» — callback: `NavDownload.MAIN` (уже существует). Handler должен возвращать заглушку вместо полного контента.

**C-2.4** Порядок кнопок фиксирован (REQ-1.2). Не меняется в зависимости от состояния пользователя. Кнопка «Admin Tools» — отдельная, видна только admin.

---

## C-3: Платёжные методы

**C-3.1** Не удалять код YooKassa, Cryptomus, YooMoney, Heleket, Stars из репозитория. Только выставить env-флаги в `False` в `.env` на сервере.

**C-3.2** `SHOP_PAYMENT_SBP_ENABLED=True`, `SHOP_PAYMENT_TON_ENABLED=True`. Все остальные `*_ENABLED=False`.

**C-3.3** Payment gateway router (`subscription/handler.py`) уже фильтрует методы по конфигу — не обходить эту логику.

---

## C-4: Multi-admin

**C-4.1** `IsAdmin` и `Config.bot.ADMINS` уже поддерживают список. Не переписывать фильтр.

**C-4.2** Добавить `403809728` в `BOT_ADMINS` в `.env` на сервере: `BOT_ADMINS=420229961,403809728`.

**C-4.3** `register(dispatcher, developer_id, admins_ids)` в `filters/__init__.py` — уже принимает список. Ничего не менять.

---

## C-5: 3x-ui подключение

**C-5.1** Диагностика: проверить таблицу `Server` (SQLite) — если пустая, сервер не добавлен.

**C-5.2** Добавить сервер через Admin Tools → Server Management (/admin_server), а не напрямую в БД.

**C-5.3** Параметры сервера: host `172.86.95.214`, port `37521`, username `vpnFran`, password из `.env`.

**C-5.4** Если XUI_HOST/XUI_PASSWORD неправильные в `.env` — исправить там, не хардкодить в коде.

---

## C-6: Архитектурные ограничения

**C-6.1** Все реквизиты оплаты берутся из `config.shop.*` — не хардкодить.

**C-6.2** Не создавать новых payment gateway классов — использовать `SbpManualGateway` и `TonManualGateway`.

**C-6.3** i18n: все пользовательские тексты через `gettext as _`. Добавлять ключи в локализационные файлы, не вставлять строки напрямую.

**C-6.4** Не делать alembic миграций если схема БД не меняется (меню — это только UI-изменения).

---

## C-7: Что точно не трогать

- `app/bot/services/referral.py` — реф-логика в скопе не меняется
- `app/bot/routers/subscription/trial_handler.py` — триал-логика рабочая
- `subscription_reminders.py` — фоновые напоминания рабочие
- Alembic migrations — новых не нужно (если только не потребуется поле для onboarding bonus guard)
