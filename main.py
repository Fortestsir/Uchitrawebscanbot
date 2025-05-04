import os
import sqlite3
import telebot
from datetime import datetime, timedelta
import subprocess

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(BOT_TOKEN)

def init_db():
    conn = sqlite3.connect("db/users.db")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        plan TEXT DEFAULT 'free',
        plan_expiry TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS scans (
        user_id INTEGER,
        url TEXT,
        timestamp TEXT
    )""")
    conn.commit()
    conn.close()

init_db()

@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(msg.chat.id, "Welcome to WebScan Pro Bot! Use /scan <url> to begin.")

@bot.message_handler(commands=["scan"])
def scan(msg):
    user_id = msg.from_user.id
    parts = msg.text.split()
    if len(parts) != 2:
        bot.send_message(msg.chat.id, "Usage: /scan <url>")
        return

    scan_url = parts[1]
    conn = sqlite3.connect("db/users.db")
    cur = conn.cursor()
    cur.execute("SELECT plan, plan_expiry FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    if row:
        plan, expiry = row
        if expiry and datetime.fromisoformat(expiry) < datetime.utcnow():
            bot.send_message(msg.chat.id, "Your Pro plan has expired. Please renew via /buypro.")
            return
    else:
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

    bot.send_message(msg.chat.id, f"Scanning {scan_url}... please wait.")
    try:
        result = subprocess.check_output(["perl", "WhatWeb/whatweb", scan_url], stderr=subprocess.DEVNULL).decode("utf-8")
    except Exception:
        result = "Scan failed or invalid URL."

    cur.execute("INSERT INTO scans (user_id, url, timestamp) VALUES (?, ?, ?)", (user_id, scan_url, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    bot.send_message(msg.chat.id, f"Scan result:

{result[:4000]}")

@bot.message_handler(commands=["buypro"])
def buy_pro(msg):
    text = """**Pro Plan – ₹99/month**

Pay via UPI:
`uchitraxop@fam`

After payment, send screenshot to @WebScan_Probot.
Admin will approve your plan shortly."""
    bot.send_message(
        msg.chat.id,
        text,
        parse_mode="Markdown"
    )
def buy_pro(msg):
    bot.send_message(
        msg.chat.id,
        "**Pro Plan – ₹99/month**\n\n"
        "Pay via UPI:\n`uchitraxop@fam`\n\n"
        "After payment, send screenshot to @WebScan_Probot.\n"
        "Admin will approve your plan shortly.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["approve"])
def approve_user(msg):
    if msg.from_user.id != ADMIN_ID:
        return

    try:
        _, user_id, days = msg.text.split()
        user_id = int(user_id)
        days = int(days)
    except:
        bot.reply_to(msg, "Usage: /approve <user_id> <days>")
        return

    expiry = datetime.utcnow() + timedelta(days=days)
    conn = sqlite3.connect("db/users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cur.fetchone():
        cur.execute("UPDATE users SET plan = ?, plan_expiry = ? WHERE user_id = ?", ("pro", expiry.isoformat(), user_id))
    else:
        cur.execute("INSERT INTO users (user_id, plan, plan_expiry) VALUES (?, ?, ?)", (user_id, "pro", expiry.isoformat()))
    conn.commit()
    conn.close()

    bot.send_message(user_id, f"Your Pro plan is now active for {days} days.")
    bot.reply_to(msg, f"Approved user {user_id} for {days} days.")

@bot.message_handler(commands=["myplan"])
def my_plan(msg):
    conn = sqlite3.connect("db/users.db")
    cur = conn.cursor()
    cur.execute("SELECT plan, plan_expiry FROM users WHERE user_id = ?", (msg.from_user.id,))
    row = cur.fetchone()
    conn.close()

    if row:
        plan, expiry = row
        bot.send_message(msg.chat.id, f"Plan: {plan.capitalize()}\nExpires: {expiry}")
    else:
        bot.send_message(msg.chat.id, "You are on the Free plan.")

bot.polling(none_stop=True, interval=0, timeout=20)
