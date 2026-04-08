"""
database.py — Neon PostgreSQL persistence layer
------------------------------------------------
All reads/writes to the database go through this file.
Tables created automatically on first run.

Secrets setup (Streamlit Cloud):
  In your app's Secrets (Settings → Secrets), add:
    DATABASE_URL = "postgresql://user:password@host/dbname?sslmode=require"

Local development:
  Create .streamlit/secrets.toml and add the same line.
"""

import streamlit as st
import pandas as pd
import psycopg2
import psycopg2.extras
import json
import io
from datetime import datetime


# ── Connection ─────────────────────────────────────────────────────────────

@st.cache_resource
def get_connection():
    """Return a cached psycopg2 connection to Neon PostgreSQL."""
    try:
        url = st.secrets["DATABASE_URL"]
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn
    except KeyError:
        st.error(
            "⚠️ **DATABASE_URL not set.** "
            "Go to your Streamlit Cloud app → Settings → Secrets and add:\n\n"
            "```\nDATABASE_URL = \"postgresql://user:password@host/dbname?sslmode=require\"\n```"
        )
        st.stop()
    except Exception as e:
        st.error(f"❌ Could not connect to Neon PostgreSQL: {e}")
        st.stop()


def _conn():
    """Get connection, reconnect if dropped."""
    conn = get_connection()
    try:
        conn.cursor().execute("SELECT 1")
    except Exception:
        get_connection.clear()
        conn = get_connection()
    return conn


# ── Schema bootstrap ───────────────────────────────────────────────────────

def init_database():
    """Create all tables if they don't exist. Safe to call on every startup."""
    conn = _conn()
    cur = conn.cursor()
    try:
        # Raw uploaded CSV data — stored as JSONB for full flexibility
        cur.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_data (
                id          SERIAL PRIMARY KEY,
                data_type   TEXT NOT NULL UNIQUE,   -- 'invoice','wms','cust_bal','po','bill_hdr','bill_lines'
                rows        JSONB NOT NULL,
                row_count   INTEGER NOT NULL,
                uploaded_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Item master — one row per SKU
        cur.execute("""
            CREATE TABLE IF NOT EXISTS item_master (
                sku         TEXT PRIMARY KEY,
                name        TEXT,
                cogs        NUMERIC(12,2) DEFAULT 0,
                dead_weight NUMERIC(8,3)  DEFAULT 0.5,
                vol_weight  NUMERIC(8,3)  DEFAULT 0.5,
                updated_at  TIMESTAMP DEFAULT NOW()
            )
        """)

        # Customer registry — one row per customer name
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer_registry (
                customer_name  TEXT PRIMARY KEY,
                type           TEXT DEFAULT 'B2C',
                channel        TEXT DEFAULT 'D2C',
                credit_days    INTEGER DEFAULT 30,
                is_marketplace BOOLEAN DEFAULT FALSE,
                updated_at     TIMESTAMP DEFAULT NOW()
            )
        """)

        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Database init error: {e}")
    finally:
        cur.close()


# ── Uploaded CSV data ──────────────────────────────────────────────────────

def save_dataframe(data_type: str, df: pd.DataFrame):
    """
    Save (upsert) a DataFrame to the uploaded_data table.
    data_type must be one of: invoice, wms, cust_bal, po, bill_hdr, bill_lines
    """
    conn = _conn()
    cur = conn.cursor()
    try:
        rows_json = df.to_json(orient="records", date_format="iso", default_handler=str)
        cur.execute("""
            INSERT INTO uploaded_data (data_type, rows, row_count, uploaded_at)
            VALUES (%s, %s::jsonb, %s, NOW())
            ON CONFLICT (data_type)
            DO UPDATE SET rows = EXCLUDED.rows,
                          row_count = EXCLUDED.row_count,
                          uploaded_at = NOW()
        """, (data_type, rows_json, len(df)))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving {data_type}: {e}")
        return False
    finally:
        cur.close()


def load_dataframe(data_type: str) -> pd.DataFrame | None:
    """Load a previously saved DataFrame from the database. Returns None if not found."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT rows FROM uploaded_data WHERE data_type = %s", (data_type,))
        row = cur.fetchone()
        if row is None:
            return None
        return pd.read_json(io.StringIO(json.dumps(row[0])), orient="records")
    except Exception as e:
        st.error(f"Error loading {data_type}: {e}")
        return None
    finally:
        cur.close()


def delete_dataframe(data_type: str):
    """Delete a specific dataset from the database."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM uploaded_data WHERE data_type = %s", (data_type,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Error deleting {data_type}: {e}")
    finally:
        cur.close()


def get_data_status() -> dict:
    """Return {data_type: {row_count, uploaded_at}} for all stored datasets."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT data_type, row_count, uploaded_at FROM uploaded_data")
        rows = cur.fetchall()
        return {r[0]: {"row_count": r[1], "uploaded_at": r[2]} for r in rows}
    except Exception:
        return {}
    finally:
        cur.close()


# ── Item Master ────────────────────────────────────────────────────────────

def save_item_master(im: dict):
    """Upsert the full item master dict into the database."""
    if not im:
        return
    conn = _conn()
    cur = conn.cursor()
    try:
        for sku, data in im.items():
            cur.execute("""
                INSERT INTO item_master (sku, name, cogs, dead_weight, vol_weight, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (sku)
                DO UPDATE SET name        = EXCLUDED.name,
                              cogs        = EXCLUDED.cogs,
                              dead_weight = EXCLUDED.dead_weight,
                              vol_weight  = EXCLUDED.vol_weight,
                              updated_at  = NOW()
            """, (
                str(sku),
                data.get("name", ""),
                float(data.get("cogs", 0)),
                float(data.get("dead_weight", 0.5)),
                float(data.get("vol_weight", 0.5)),
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving item master: {e}")
    finally:
        cur.close()


def load_item_master() -> dict:
    """Load item master from database. Returns {} if empty."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT sku, name, cogs, dead_weight, vol_weight FROM item_master")
        rows = cur.fetchall()
        return {
            r[0]: {
                "name": r[1],
                "cogs": float(r[2]),
                "dead_weight": float(r[3]),
                "vol_weight": float(r[4]),
            }
            for r in rows
        }
    except Exception:
        return {}
    finally:
        cur.close()


def delete_item(sku: str):
    """Delete a single SKU from item master."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM item_master WHERE sku = %s", (sku,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Error deleting item {sku}: {e}")
    finally:
        cur.close()


# ── Customer Registry ──────────────────────────────────────────────────────

def save_customer_registry(registry: dict):
    """Upsert the full customer registry into the database."""
    if not registry:
        return
    conn = _conn()
    cur = conn.cursor()
    try:
        for name, data in registry.items():
            cur.execute("""
                INSERT INTO customer_registry
                    (customer_name, type, channel, credit_days, is_marketplace, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (customer_name)
                DO UPDATE SET type           = EXCLUDED.type,
                              channel        = EXCLUDED.channel,
                              credit_days    = EXCLUDED.credit_days,
                              is_marketplace = EXCLUDED.is_marketplace,
                              updated_at     = NOW()
            """, (
                str(name),
                data.get("type", "B2C"),
                data.get("channel", "D2C"),
                int(data.get("credit_days", 30)),
                bool(data.get("is_marketplace", False)),
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving customer registry: {e}")
    finally:
        cur.close()


def load_customer_registry() -> dict:
    """Load customer registry from database. Returns {} if empty."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT customer_name, type, channel, credit_days, is_marketplace
            FROM customer_registry
        """)
        rows = cur.fetchall()
        return {
            r[0]: {
                "type": r[1],
                "channel": r[2],
                "credit_days": int(r[3]),
                "is_marketplace": bool(r[4]),
            }
            for r in rows
        }
    except Exception:
        return {}
    finally:
        cur.close()


def clear_all_data():
    """Nuclear option — wipe all uploaded data. Master data is preserved."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM uploaded_data")
        conn.commit()
    except Exception as e:
        conn.rollback()
        st.error(f"Error clearing data: {e}")
    finally:
        cur.close()
