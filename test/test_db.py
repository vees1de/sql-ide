"""Test PostgreSQL dvdrental connection."""
import psycopg2

DSN = {
    "host": "localhost",
    "port": 5432,
    "dbname": "dvdrental",
    "user": "postgres",
    "password": "postgres",
}

print("Connecting to PostgreSQL...")
conn = psycopg2.connect(**DSN)
cur = conn.cursor()

cur.execute("SELECT version();")
pg_version = cur.fetchone()[0]
print(f"PostgreSQL: {pg_version}")

cur.execute("SELECT COUNT(*) FROM film;")
film_count = cur.fetchone()[0]
print(f"Films: {film_count}")

cur.execute("SELECT COUNT(*) FROM customer;")
customer_count = cur.fetchone()[0]
print(f"Customers: {customer_count}")

cur.close()
conn.close()
print("DB test PASSED")
