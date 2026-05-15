# Raccoon Card Gallery Bot

Telegram-бот-галерея карточек на `aiogram 3.x` с локальным JSON-хранилищем и поддержкой SOCKS5-прокси.

## Возможности
- Админ-загрузка карточек (`photo` и `document`-изображения).
- Админ-галерея `/raccoonadmin` и `/galleryadmin` (одинаковое поведение).
- Выдача случайной включённой карточки по текстовому триггеру (без учёта регистра).
- Статистика выдачи карточек и триггеров в JSON.

## Структура проекта
См. файлы в корне репозитория, `data/`, `arts/`, `systemd/`.

## Подготовка сервера (Ubuntu 24.04)
### 1) Создать пользователя
```bash
sudo adduser --disabled-password --gecos "" botuser
sudo usermod -aG sudo botuser
```

### 2) Клонировать репозиторий
```bash
sudo -u botuser -H bash -lc 'cd ~ && git clone <YOUR_GITHUB_URL> Raccoon'
```

### 3) Создать venv
```bash
sudo -u botuser -H bash -lc 'cd ~/Raccoon && python3.12 -m venv .venv'
```

### 4) Установить зависимости
```bash
sudo -u botuser -H bash -lc 'cd ~/Raccoon && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt'
```

### 5) Создать `.env`
```bash
sudo -u botuser -H bash -lc 'cd ~/Raccoon && cp .env.example .env'
```
Заполнить:
- `BOT_TOKEN=<ваш токен>`
- `PROXY_URL=socks5://127.0.0.1:1080`
- `ADMIN_IDS=111111111,222222222`

## Проверка прокси
Проверка curl:
```bash
curl -I -x socks5h://127.0.0.1:1080 https://api.telegram.org
```

Проверка скриптом:
```bash
cd ~/Raccoon
. .venv/bin/activate
python proxy_check.py
```
Ожидаемый формат:
- `DIRECT: OK/FAIL`
- `PROXY: OK/FAIL`

## Запуск бота вручную
```bash
cd ~/Raccoon
. .venv/bin/activate
python main.py
```

## Установка systemd service
```bash
sudo cp ~/Raccoon/systemd/raccoon-card-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable raccoon-card-bot.service
sudo systemctl start raccoon-card-bot.service
```

## Диагностика
```bash
systemctl status raccoon-card-bot.service
journalctl -u raccoon-card-bot.service -f
```

## Быстрый деплой на сервер
```bash
sudo adduser --disabled-password --gecos "" botuser
sudo -u botuser -H bash -lc 'cd ~ && git clone <YOUR_GITHUB_URL> Raccoon && cd Raccoon && python3.12 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt && cp .env.example .env'
# отредактируйте /home/botuser/Raccoon/.env и заполните BOT_TOKEN/ADMIN_IDS
sudo cp /home/botuser/Raccoon/systemd/raccoon-card-bot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable raccoon-card-bot.service && sudo systemctl start raccoon-card-bot.service
```


## Новые команды Stage 2
- `/mygallery` — личная галерея найденных карточек.
- `/broadcast` — рассылка (только для ADMIN_IDS, строго через подтверждение).
- `/userstats` — статистика пользователей и карточек.
- `/raccoonadmin` — админка набора «Енотя».
- `/galleryadmin` — админка набора «Лися».
- `/addraccoon` — добавление с дефолтами Еноти.
- `/addfox` — добавление с дефолтами Лиси.

## Безопасное обновление на сервере
```bash
cd ~/Raccoon
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart raccoon-card-bot.service
sudo journalctl -u raccoon-card-bot.service -f
```
