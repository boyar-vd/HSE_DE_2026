# Введение в Data Engineering

Курс для магистратуры ИИ ФКН НИУ ВШЭ: 8 занятий.

---

## Занятие 1. Архитектуры и контейнеризация

**Тема:** Введение в Data Engineering. Архитектуры хранилищ: DWH, Data Lake, Lakehouse. Схемы «звезда» и «снежинка». ETL vs ELT. Контейнеризация (Docker, Docker Compose).

**Что делаем на занятии:**
- Разбираем эволюцию архитектур: DWH → Data Lake → Lakehouse.
- Учимся различать «звезду» и «снежинку», ETL и ELT.
- Поднимаем локальный стек Postgres + MinIO через Docker Compose.
- Генерируем 1000 заказов, загружаем CSV в MinIO, затем перекладываем данные в Postgres (схема `stg`).
- Проверяем результат в DBeaver и проверяем идемпотентность загрузки.

**Что должно быть в итоге:**
- 2 контейнера `Up (healthy)` — `de_postgres` и `de_minio`.
- Bucket `landing-zone` в MinIO с файлом `orders/orders.csv` (1000 строк).
- Таблица `stg.orders` в Postgres с 1000 строками.
- DBeaver подключён и показывает данные.

**Стек занятия:**

| Компонент | Роль |
| :--- | :--- |
| **PostgreSQL 15** | Сырой слой (STG), транзакционная БД |
| **MinIO (S3)** | Объектное хранилище для CSV |
| **DBeaver** | Локальный клиент к БД |
| **Docker Compose** | Воспроизводимость окружения |

**Структура папки занятия:**

```
lesson-1/
├── docker-compose.yml
├── .env.example
├── init/
│   └── init.sql
├── scripts/
│   ├── generate_and_upload.py
│   ├── load_to_postgres.py
│   └── requirements.txt
└── README.md
```

---

## Требования к окружению

Перед первым занятием установите:

1. **Docker Desktop** (Windows/macOS) или **Docker Engine + compose plugin** (Linux).
2. **DBeaver Community** — https://dbeaver.io/download/ (бесплатно, все ОС).
3. **Python 3.10+** и `pip`.
4. **Git**.

Проверьте в терминале:

```bash
docker --version
docker compose version
python3 --version        # Windows: python --version
git --version
```

Все команды должны вывести версии без ошибок. Если что-то не работает — напишите преподавателю **до** занятия.

**Windows:** используйте PowerShell или Windows Terminal. Docker Desktop должен быть настроен на **WSL 2 backend** (Settings → General → «Use the WSL 2 based engine»).

---

## Как начать работу с занятием 1

```bash
# 1. Клонировать репозиторий (один раз)
git clone <repo-url>
cd <repo-name>

# 2. Перейти в папку занятия
cd lesson-1

# 3. Создать .env из шаблона
cp .env.example .env          # Windows: Copy-Item .env.example .env

# 4. Поднять инфраструктуру
docker compose up -d

# 5. Проверить статус
docker compose ps             # ждём 2 контейнера Up (healthy)

# 6. Создать venv и установить зависимости
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r scripts/requirements.txt

# 7. Сгенерировать данные и загрузить в MinIO
python scripts/generate_and_upload.py

# 8. Переложить данные из MinIO в Postgres
python scripts/load_to_postgres.py
```

Подробная пошаговая инструкция (macOS + Windows) — в `lesson-1/README.md`.

---

## Как воспроизвести занятие с нуля

Если что-то сломалось или нужно начать заново:

```bash
# 1. Остановить и удалить контейнеры + volumes (данные удалятся)
docker compose down -v

# 2. Удалить venv (если нужно переустановить зависимости)
rm -rf .venv                  # Windows: Remove-Item -Recurse -Force .venv

# 3. Удалить .env (если нужно пересоздать)
rm .env                       # Windows: del .env

# 4. Поднять стек заново
cp .env.example .env
docker compose up -d
docker compose ps

# 5. Пересоздать venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

> ⚠️ Флаг `-v` удаляет volumes (`pg_data`, `minio_data`). Без `-v` данные сохранятся, но `init.sql` **не выполнится заново** (Postgres пропускает init при непустом volume).

---

## Формула оценки

```
Итог = 0.3 × ДЗ1 + 0.3 × ДЗ2 + 0.4 × ДЗ3
```

---