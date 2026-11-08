CREATE SCHEMA IF NOT EXISTS stg;

CREATE TABLE IF NOT EXISTS stg.orders (
    id SERIAL PRIMARY KEY,
    order_id UUID UNIQUE NOT NULL,
    order_date TIMESTAMP NOT NULL,
    user_id INT NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    loaded_at TIMESTAMP DEFAULT now()
);