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