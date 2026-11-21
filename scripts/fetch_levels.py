#!/usr/bin/env python3
"""Fetch water levels from Niv'eau API and store in SQLite."""
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")

# Add parent to path for config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

DB_PATH = os.path.abspath(config.DB_PATH)
EXPORT_DIR = os.path.abspath(config.EXPORT_DIR)
ALERT_STATE_PATH = os.path.abspath(config.ALERT_STATE_PATH)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            ts TEXT PRIMARY KEY,
            value REAL NOT NULL,
            unit TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def parse_api_date(d, h):
    """Parse API date 'DD-MM-YYYY' and time 'HH:MM' into UTC ISO string."""
    dt = datetime.strptime(f"{d} {h}", "%d-%m-%Y %H:%M")
    # API times are in Europe/Paris (UTC+1 or +2). For simplicity, store as naive local
    # but mark as ISO without tz to keep it simple. We'll treat as local time.
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def fetch_period(nb_days):
    """Fetch data for the last nb_days days. Returns list of (ts, value)."""
    today = datetime.now(PARIS_TZ)
    date_str = today.strftime("%d-%m-%Y")
    url = config.API_URL.format(date=date_str, nb=nb_days)
    req = urllib.request.Request(url, headers=config.API_HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    points = []
    for c in data.get("chroniques", []):
        ts = parse_api_date(c["date"], c["heure"])
        points.append((ts, float(c["valeur"]), c.get("unite", config.UNIT)))
    return points


def store_points(conn, points):
    """Insert points, ignoring duplicates."""
    inserted = 0
    for ts, value, unit in points:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO measurements (ts, value, unit) VALUES (?, ?, ?)",
                (ts, value, unit),
            )
            inserted += conn.total_changes  # approximate
        except Exception:
            pass
    conn.commit()
    # Count actual new
    return inserted


def get_latest(conn):
    row = conn.execute(
        "SELECT ts, value, unit FROM measurements ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if row:
        return {"ts": row[0], "value": row[1], "unit": row[2]}
    return None


def aggregate(conn, hours):
    """Return aggregated data for the last `hours` hours."""
    now_local = datetime.now(PARIS_TZ).replace(tzinfo=None)
    cutoff = (now_local - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = conn.execute(
        "SELECT ts, value FROM measurements WHERE ts >= ? ORDER BY ts ASC",
        (cutoff,),
    ).fetchall()
    return rows


def export_json(conn):
    """Export aggregated JSON files for GitHub Pages."""
    os.makedirs(EXPORT_DIR, exist_ok=True)

    periods = {
        "24h": 24,
        "7d": 24 * 7,
        "30d": 24 * 30,
        "365d": 24 * 365,
    }

    # Bucket sizes (in minutes) for aggregation
    bucket_minutes = {
        "24h": 20,
        "7d": 60,
        "30d": 360,
        "365d": 1440,
    }

    for name, hours in periods.items():
        rows = aggregate(conn, hours)
        bucket = bucket_minutes[name]
        # Aggregate into buckets
        buckets = {}
        for ts_str, value in rows:
            dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
            # data timestamps are local Europe/Paris (naive); make tz-aware for stable bucketing
            dt_aware = dt.replace(tzinfo=PARIS_TZ)
            bucket_sec = bucket * 60
            epoch = dt_aware.timestamp()
            bucket_key = int(epoch // bucket_sec) * bucket_sec
            bdt = datetime.fromtimestamp(bucket_key, tz=PARIS_TZ).replace(tzinfo=None)
            key = bdt.strftime("%Y-%m-%dT%H:%M:%S")
            if key not in buckets:
                buckets[key] = []
            buckets[key].append(value)

        data_points = []
        for key in sorted(buckets.keys()):
            vals = buckets[key]
            data_points.append({
                "ts": key,
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
                "avg": round(sum(vals) / len(vals), 2),
                "last": round(vals[-1], 2),
                "count": len(vals),
            })

        out_path = os.path.join(EXPORT_DIR, f"{name}.json")
        with open(out_path, "w") as f:
            json.dump({"period": name, "points": data_points}, f, indent=2)

    # Latest
    latest = get_latest(conn)
    with open(os.path.join(EXPORT_DIR, "latest.json"), "w") as f:
        json.dump(latest or {}, f, indent=2)

    print(f"Exported {len(periods)} period files + latest.json")


def check_alerts(conn):
    """Check thresholds and send email if needed."""
    latest = get_latest(conn)
    if not latest:
        return

    value = latest["value"]
    ts = latest["ts"]

    # Load alert state
    state = {}
    if os.path.exists(ALERT_STATE_PATH):
        with open(ALERT_STATE_PATH) as f:
            state = json.load(f)

    high_alerted = state.get("high", False)
    low_alerted = state.get("low", False)

    new_high = value > config.THRESHOLD_HIGH
    new_low = value < config.THRESHOLD_LOW

    send_high = new_high and not high_alerted
    send_low = new_low and not low_alerted

    if send_high or send_low:
        send_email(value, ts, send_high, send_low)

    # Update state
    state["high"] = new_high
    state["low"] = new_low
    state["last_value"] = value
    state["last_ts"] = ts
    os.makedirs(os.path.dirname(ALERT_STATE_PATH), exist_ok=True)
    with open(ALERT_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def send_email(value, ts, high, low):
    """Send alert email via SMTP."""
    import smtplib
    from email.message import EmailMessage

    if not config.SMTP_HOST or not config.SMTP_USER or not config.ALERT_EMAIL:
        print("Email not configured, skipping alert.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Alerte niveau d'eau Puech des Ouilhes - {value} mNGF"
    msg["From"] = config.SMTP_USER
    msg["To"] = config.ALERT_EMAIL

    body = f"Niveau actuel : {value} mNGF (mesure du {ts})\n"
    if high:
        body += f"⚠️ Le niveau a dépassé le seuil haut de {config.THRESHOLD_HIGH} mNGF.\n"
    if low:
        body += f"⚠️ Le niveau est descendu sous le seuil bas de {config.THRESHOLD_LOW} mNGF.\n"
    body += f"\nConsultez le dashboard : https://<user>.github.io/niveau-puech-ouilhes/\n"
    msg.set_content(body)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.send_message(msg)
        print("Alert email sent.")
    except Exception as e:
        print(f"Failed to send email: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="Fetch 30 and 365 days for initial backfill")
    args = parser.parse_args()

    conn = init_db()

    periods_to_fetch = [1, 7]
    if args.backfill:
        periods_to_fetch = [1, 7, 30, 365]

    for nb in periods_to_fetch:
        try:
            points = fetch_period(nb)
            print(f"Fetched {len(points)} points for last {nb}d")
            store_points(conn, points)
        except Exception as e:
            print(f"Error fetching {nb}d data: {e}")

    export_json(conn)
    check_alerts(conn)
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()