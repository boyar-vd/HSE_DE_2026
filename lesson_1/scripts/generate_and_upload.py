import os
import io
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
lines = [header] + [f"{r['order_id']},{r['order_date']},{r['user_id']},{r['amount']},{r['status']}" for r in rows]
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