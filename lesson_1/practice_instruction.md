# Практика занятия 1 — пошаговая инструкция (macOS + Windows)

**Цель:** поднять локальный стек Postgres + MinIO через Docker Compose, сгенерировать CSV с заказами, загрузить его в MinIO, затем переложить данные из MinIO в Postgres (схема `stg`), проверить результат в DBeaver.

**Что должно быть в итоге:**
- 2 контейнера `Up (healthy)` — `de_postgres` и `de_minio`.
- Bucket `landing-zone` в MinIO с файлом `orders/orders.csv` (1000 строк).
- Таблица `stg.orders` в Postgres с 1000 строками.
- DBeaver подключён и показывает данные.

**Что нужно установить заранее:** Docker Desktop, DBeaver Community, Python 3.10+.

> **Обозначения в инструкции:**
> - 🍎 — команда/путь для **macOS / Linux**
> - 🪟 — команда/путь для **Windows** (cmd или PowerShell — указано отдельно)
> - Если блок не помечен — команда одинаковая для обеих ОС.

---

## 📁 Структура проекта

```
lesson-1/
├── .venv/                        ← создаётся на шаге 6, не коммитится
├── .gitignore
├── .env                          ← создаётся на шаге 2, не коммитится
├── .env.example
├── docker-compose.yml
├── init/
│   └── init.sql
└── scripts/
    ├── generate_and_upload.py
    ├── load_to_postgres.py
    └── requirements.txt
```

---

## Шаг 1. Проверить, что Docker Desktop запущен

1. Откройте **Docker Desktop**.
   - 🍎 Launchpad → Docker.
   - 🪟 Пуск → Docker Desktop.
2. Дождитесь зелёного индикатора «Engine running» в левом нижнем углу (30–60 секунд при первом запуске).
3. В терминале проверьте:

```bash
docker --version
docker compose version
```

Обе команды должны вывести версии без ошибок. Если видите `Cannot connect to the Docker daemon` — Docker Desktop не запущен, вернитесь к пункту 1.

> 🪟 **Windows:** используйте **PowerShell** или **Windows Terminal**. Если `docker` не найден — перезапустите терминал после установки Docker Desktop (PATH обновляется только в новых сессиях). Убедитесь, что Docker Desktop настроен на **WSL 2 backend** (Settings → General → «Use the WSL 2 based engine»).

---

## Шаг 2. Создать `.env` из шаблона

🍎 **macOS / Linux:**
```bash
cd lesson-1
cp .env.example .env
```

🪟 **Windows (PowerShell):**
```powershell
cd lesson-1
Copy-Item .env.example .env
```

🪟 **Windows (cmd):**
```cmd
cd lesson-1
copy .env.example .env
```

Проверьте, что `.env` содержит:

```env
POSTGRES_USER=de_user
POSTGRES_PASSWORD=de_password
POSTGRES_DB=raw_data
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=minio_password
```

> **Важно:** `.env` содержит пароли и **не коммитится в Git**. В репозитории лежит только `.env.example`.

Убедитесь, что `.gitignore` содержит:

```
.venv/
.env
__pycache__/
*.pyc
```

> 🪟 **Windows:** если при `docker compose up` увидите ошибку про `\r` в `.env` — значит, файл сохранён с CRLF. Откройте `.env` в VS Code, в правом нижнем углу переключите **CRLF → LF** и сохраните.

---

## Шаг 3. Проверить `docker-compose.yml`

Файл должен содержать **три сервиса**: `postgres`, `minio`, `minio-init` (автосоздание бакета). Полное содержимое:

```yaml
services:
  postgres:
    image: postgres:15
    container_name: de_postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - de_network

  minio:
    image: pgsty/minio:RELEASE.2026-08-04T00-00-00Z
    container_name: de_minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - de_network

  minio-init:
    image: quay.io/minio/mc:latest
    container_name: de_minio_init
    depends_on:
      minio:
        condition: service_healthy
    networks:
      - de_network
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} &&
      mc mb --ignore-existing local/landing-zone &&
      echo 'Bucket landing-zone ready.'
      "

volumes:
  pg_data:
  minio_data:

networks:
  de_network:
    driver: bridge
```

> **Если `pgsty/minio` тоже перестанет работать** — используйте `cgr.dev/chainguard/minio:latest` и добавьте `user: "0:0"` в сервис `minio`. Это резервный вариант.

> 🪟 **Windows:** файл `docker-compose.yml` должен быть сохранён в **UTF-8 без BOM** и с окончаниями строк **LF**. В VS Code: правый нижний угол → `CRLF` → выбрать `LF`, затем сохранить. Иначе Docker Compose может выдать ошибку парсинга YAML.

---

## Шаг 4. Проверить `init/init.sql`

Файл должен создавать схему `stg` и таблицу `orders`:

```sql
CREATE SCHEMA IF NOT EXISTS stg;

CREATE TABLE IF NOT EXISTS stg.orders (
    id SERIAL PRIMARY KEY,
    order_id UUID UNIQUE NOT NULL,
    order_date TIMESTAMP NOT NULL,
    user_id INT NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP DEFAULT NOW()
);
```

> **Важно:** `init.sql` выполняется Postgres **только при первом старте** с пустым volume. Если вы меняете `init.sql` после первого запуска — изменения не применятся, пока не удалить volume (`docker compose down -v`).

> 🪟 **Windows:** сохраните `init.sql` в **UTF-8 без BOM** и с окончаниями строк **LF**. Иначе Postgres может пожаловаться на `syntax error at or near ""`.

---

## Шаг 5. Запустить инфраструктуру

```bash
docker compose up -d
```

Первый запуск скачивает образы (~1–2 минуты). Ожидаемый вывод:

```
[+] Running 4/4
 ✔ Network lesson-1_de_network  Created
 ✔ Container de_postgres        Healthy
 ✔ Container de_minio           Healthy
 ✔ Container de_minio_init      Exited (0)
```

> `minio-init` в статусе `Exited (0)` — это **нормально**. Контейнер создал бакет, завершился с кодом 0 и больше не нужен.

Проверьте статус:

```bash
docker compose ps
```

Должны быть `de_postgres` и `de_minio` в статусе `Up (healthy)`. `de_minio_init` — `Exited (0)`.

Проверьте, что бакет создался:

```bash
docker compose logs minio-init
```

Должно быть: `Bucket landing-zone ready.`

> 🪟 **Windows:** если `docker compose up -d` падает с ошибкой `Ports are not available: exposing port TCP 0.0.0.0:5432` — порт 5432 занят (часто локальным Postgres или другим контейнером). Освободите порт: `netstat -ano | findstr :5432`, найдите PID в последней колонке, `taskkill /PID <pid> /F`. Или поменяйте порт в compose на `"5433:5432"` и в DBeaver указывайте `5433`.

---

## Шаг 6. Создать виртуальное окружение и установить зависимости

### 🍎 macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r scripts/requirements.txt
```

### 🪟 Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r scripts/requirements.txt
```

> 🪟 **Если PowerShell блокирует активацию:** вы увидите ошибку `cannot be loaded because running scripts is disabled on this system`. Выполните один раз:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```
> Подтвердите `Y`, затем снова `.venv\Scripts\Activate.ps1`.

### 🪟 Windows (cmd)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r scripts/requirements.txt
```

> 🪟 Если `python` не найден — попробуйте `py -3 -m venv .venv` и далее `py -3 -m pip ...`. Или переустановите Python с галочкой «Add Python to PATH».

В начале строки терминала должен появиться префикс `(.venv)`:

```
(.venv) vladislavboyar@MacBook-Air lesson-1 %
(.venv) PS C:\Users\Vlad\lesson-1>
(.venv) C:\Users\Vlad\lesson-1>
```

Проверьте, что всё встало:

```bash
python -c "import boto3, psycopg2, faker, dotenv; print('OK')"
```

Должно вывести `OK`.

---

## Шаг 7. Проверить скрипты

### `scripts/requirements.txt`

```txt
boto3>=1.34.0
psycopg2-binary>=2.9.9
Faker>=22.0.0
python-dotenv>=1.0.0
```

### `scripts/generate_and_upload.py`

Генерирует 1000 заказов и загружает CSV в MinIO:

```python
import os
import uuid
import random
from datetime import datetime, timedelta

import boto3
from faker import Faker
from dotenv import load_dotenv

load_dotenv()
fake = Faker()

# 1. Генерация данных
statuses = ["new", "processing", "delivered", "cancelled"]
rows = []
for _ in range(1000):
    rows.append({
        "order_id": str(uuid.uuid4()),
        "order_date": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
        "user_id": random.randint(1, 100),
        "amount": round(random.uniform(10, 10000), 2),
        "status": random.choice(statuses),
    })

# 2. Формирование CSV в памяти
header = "order_id,order_date,user_id,amount,status"
lines = [header] + [
    f"{r['order_id']},{r['order_date']},{r['user_id']},{r['amount']},{r['status']}"
    for r in rows
]
csv_bytes = "\n".join(lines).encode("utf-8")

# 3. Загрузка в MinIO
s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id=os.environ["MINIO_ROOT_USER"],
    aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
)
s3.put_object(Bucket="landing-zone", Key="orders/orders.csv", Body=csv_bytes)

print(f"Uploaded {len(rows)} orders to s3://landing-zone/orders/orders.csv")
```

### `scripts/load_to_postgres.py`

Читает CSV из MinIO и вставляет строки в `stg.orders`:

```python
import os
import csv
import io

import boto3
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# 1. Чтение CSV из MinIO
s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id=os.environ["MINIO_ROOT_USER"],
    aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
)
obj = s3.get_object(Bucket="landing-zone", Key="orders/orders.csv")
content = obj["Body"].read().decode("utf-8")

reader = csv.DictReader(io.StringIO(content))
orders = []
for row in reader:
    orders.append((
        row["order_id"],
        row["order_date"],
        int(row["user_id"]),
        float(row["amount"]),
        row["status"],
    ))

# 2. Вставка в Postgres
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn, conn.cursor() as cur:
    execute_values(
        cur,
        """
        INSERT INTO stg.orders (order_id, order_date, user_id, amount, status)
        VALUES %s
        ON CONFLICT (order_id) DO NOTHING
        """,
        orders,
    )
conn.close()

print(f"Loaded {len(orders)} orders into stg.orders")
```

> **Обратите внимание:** `ON CONFLICT (order_id) DO NOTHING` делает скрипт идемпотентным — повторный запуск не создаёт дубли.

> 🪟 **Windows:** оба скрипта должны быть сохранены в **UTF-8** (без BOM). Если в CSV попадёт BOM (`\ufeff` в начале файла), `csv.DictReader` может включить его в имя первого столбца (`\ufefforder_id`), и `row["order_id"]` упадёт с `KeyError`. В VS Code: правый нижний угол → `UTF-8 with BOM` → выбрать `UTF-8`.

---

## Шаг 8. Подключить DBeaver к Postgres

1. Откройте **DBeaver** → «New Database Connection» (`Ctrl+Shift+N` / `Cmd+Shift+N`).
2. Выберите **PostgreSQL** → Next.
3. Заполните:
   - **Host:** `localhost`
   - **Port:** `5432`
   - **Database:** `raw_data`
   - **Username:** `de_user`
   - **Password:** `de_password`
   - ✅ **Save password locally**
4. «Test Connection» → должно быть «Connected» → Finish.
5. В дереве слева: `raw_data → Databases → raw_data → Schemas → stg → Tables → orders` (таблица существует, но пустая).

> Если DBeaver не подключается: проверьте, что `docker compose ps` показывает `de_postgres` в статусе `Up (healthy)`. Если контейнер `Restarting` — смотрите `docker compose logs postgres`.

> 🪟 **Windows:** если DBeaver выдаёт `Connection refused` при том, что контейнер `Up (healthy)` — проверьте, не занимает ли порт 5432 локальный Postgres (см. шаг 5). Также убедитесь, что в DBeaver host именно `localhost`, а не `127.0.0.1` (иногда помогает именно `localhost` из-за IPv6-резолвинга).

---

## Шаг 9. Сгенерировать данные и загрузить в MinIO

Убедитесь, что venv активирован (префикс `(.venv)`), и запустите:

🍎 **macOS / Linux:**
```bash
python scripts/generate_and_upload.py
```

🪟 **Windows (PowerShell / cmd):**
```powershell
python scripts\generate_and_upload.py
```

> 🪟 **Windows:** в PowerShell и cmd разделитель пути — `\`, а не `/`. Хотя `python scripts/generate_and_upload.py` (с прямым слэшем) тоже работает в большинстве случаев — Windows нормально воспринимает оба варианта.

Ожидаемый вывод:

```
Uploaded 1000 orders to s3://landing-zone/orders/orders.csv
```

> **Возможное предупреждение:** `PythonDeprecationWarning: Boto3 will no longer support Python 3.9 starting April 29, 2026`. Это **не ошибка**, а предупреждение. Скрипт отработал. Если хотите убрать — пересоздайте venv на Python 3.10+ (см. раздел «Типичные проблемы» ниже).

**Проверка:** откройте `http://localhost:9001`, войдите (`minio_admin` / `minio_password`), зайдите в `landing-zone → orders → orders.csv`. Файл должен быть на месте.

> 🪟 **Windows:** если браузер не открывает `localhost:9001` — попробуйте `http://127.0.0.1:9001`. Если и это не работает — проверьте `docker compose ps`, контейнер `de_minio` должен быть `Up (healthy)`.

---

## Шаг 10. Переложить данные из MinIO в Postgres

🍎 **macOS / Linux:**
```bash
python scripts/load_to_postgres.py
```

🪟 **Windows (PowerShell / cmd):**
```powershell
python scripts\load_to_postgres.py
```

Ожидаемый вывод:

```
Loaded 1000 orders into stg.orders
```

---

## Шаг 11. Проверить результат в DBeaver

В DBeaver откройте SQL Editor (`F3`) и выполните:

```sql
-- 1. Количество строк
SELECT COUNT(*) FROM stg.orders;
-- Ожидается: 1000

-- 2. Первые 5 заказов
SELECT * FROM stg.orders LIMIT 5;

-- 3. Распределение по статусам
SELECT status, COUNT(*) AS cnt
FROM stg.orders
GROUP BY status
ORDER BY cnt DESC;

-- 4. Проверка суммы
SELECT MIN(amount), MAX(amount), AVG(amount) FROM stg.orders;
```

Если `COUNT(*)` = 1000 — **практика завершена успешно**.

---

## Шаг 12. Проверить идемпотентность (бонус)

Запустите загрузку ещё раз:

🍎 **macOS / Linux:**
```bash
python scripts/load_to_postgres.py
```

🪟 **Windows:**
```powershell
python scripts\load_to_postgres.py
```

Снова увидите `Loaded 1000 orders into stg.orders`, но в БД по-прежнему **1000 строк**, а не 2000:

```sql
SELECT COUNT(*) FROM stg.orders;   -- всё ещё 1000
```

Это правильное поведение благодаря `ON CONFLICT (order_id) DO NOTHING`. Такой принцип называется **идемпотентностью** — повторный запуск не меняет результат. Это ключевой навык для DE, который пригодится в ДЗ и на следующих занятиях.

---

## ✅ Итог занятия 1

К концу практики у вас:
- 2 контейнера `Up (healthy)` — `de_postgres` и `de_minio`.
- Bucket `landing-zone` с файлом `orders/orders.csv` (1000 строк).
- Схема `stg` и таблица `stg.orders` в Postgres с 1000 строками.
- DBeaver подключён и показывает данные.
- Проверена идемпотентность загрузки.

На следующем занятии мы обернём эти два скрипта в **Airflow DAG**, и они будут запускаться по расписанию, а не вручную.

---

## ⚠️ Типичные проблемы и решения

| Симптом | Причина | Решение |
| :--- | :--- | :--- |
| `Top-level object must be a mapping` | В папке есть пустой/битый `docker-compose.override.yml`, или файл не сохранён | `ls -la` (🍎) / `dir` (🪟), удалить `docker-compose.override.yml`; проверить, что `docker-compose.yml` начинается с `services:` |
| `pull access denied for minio/minio` | Официальный образ MinIO удалён с Docker Hub | Использовать `pgsty/minio:RELEASE.2026-08-04T00-00-00Z` (или `cgr.dev/chainguard/minio`) |
| `unauthorized: access to the requested resource is not authorized` | Образ `quay.io/minio/minio` требует логина | Использовать `pgsty/minio` (форк на Docker Hub) |
| `port is already allocated` / `Ports are not available` | Порт занят другим контейнером или локальной БД | `docker ps` (🍎) / `netstat -ano \| findstr :5432` (🪟), остановить процесс или поменять порт в compose на `"5433:5432"` |
| `Cannot connect to the Docker daemon` | Docker Desktop не запущен | Открыть Docker Desktop, дождаться «Engine running» |
| `connection refused` в DBeaver | Postgres не `Up (healthy)` | `docker compose ps`, `docker compose logs postgres` |
| `password authentication failed` | Пароль в `.env` не совпадает с контейнером | `docker compose down -v && docker compose up -d` (пересоздаст БД) |
| `relation "stg.orders" does not exist` | `init.sql` не выполнился | Проверить `docker compose logs postgres`; пересоздать volume `docker compose down -v && docker compose up -d` |
| `NoSuchBucket: landing-zone` | `minio-init` не отработал | `docker compose logs minio-init`; создать бакет вручную в MinIO Console |
| `ModuleNotFoundError: No module named 'boto3'` | venv не активирован или зависимости не установлены | Активировать venv (шаг 6), `pip install -r scripts/requirements.txt` |
| `PythonDeprecationWarning: Boto3 will no longer support Python 3.9` | В venv стоит Python 3.9 | Игнорировать (работает) или пересоздать venv на Python 3.10+ |
| `psycopg2.OperationalError: could not connect to server` | В скрипте host = `postgres` вместо `localhost` | В скрипте на ноутбуке host должен быть `localhost` (внутри Docker — имена, снаружи — localhost) |
| 🪟 `cannot be loaded because running scripts is disabled` (PowerShell) | Execution policy блокирует активацию venv | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| 🪟 `python: command not found` | Python не в PATH | Переустановить Python с галочкой «Add Python to PATH» или использовать `py -3` |
| 🪟 `syntax error at or near ""` в Postgres | `init.sql` сохранён с BOM | Сохранить `init.sql` в UTF-8 **без BOM**, окончания строк LF |
| 🪟 `KeyError: 'order_id'` при чтении CSV | CSV сохранён с BOM, `\ufefforder_id` | Сохранить скрипт/CSV в UTF-8 без BOM; либо в скрипте открывать CSV с `encoding="utf-8-sig"` |
| 🪟 `docker compose` ругается на `\r` в `.env` / YAML | Файл сохранён с CRLF | В VS Code переключить CRLF → LF и сохранить |
| 🪟 `permission denied` при монтировании `init/` | Общий диск или OneDrive-папка | Переместить проект в локальную папку (например, `C:\projects\lesson-1`), не в OneDrive |

---

## 📌 Что важно запомнить

1. **Volumes** (`pg_data`, `minio_data`) сохраняют данные между `docker compose down` и `up`. `down -v` — удаляет.
2. **Внутри Docker** контейнеры видят друг друга по именам (`postgres`, `minio`). **Снаружи** (скрипты на ноутбуке, DBeaver) — по `localhost` и проброшенным портам (`5432`, `9000`).
3. **`.env`** хранит пароли, не коммитится. В Git — только `.env.example`.
4. **`init.sql`** выполняется только при **первом** старте с пустым volume. Меняете схему — пересоздайте volume.
5. **Идемпотентность** (`ON CONFLICT DO NOTHING`) — повторный запуск не создаёт дубли. Это основа надёжных пайплайнов.
6. 🪟 **Windows-специфика:** UTF-8 без BOM, окончания строк LF для файлов, которые читает Docker/Postgres; `\` в путях PowerShell/cmd; `Set-ExecutionPolicy` для активации venv.