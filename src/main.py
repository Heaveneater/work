#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Файл для запуска Telegram-бота для студентов Пермского финансово-экономического колледжа.
Использует минимальное Flask-приложение для поддержки Replit.
"""

import logging
import os
import threading
from flask import Flask, render_template, jsonify

# Импортируем основные компоненты бота
from src.bot.bot import main as bot_main
from src.utils.constants import BOT_VERSION

# Создаем минимальное Flask-приложение для запуска бота в Replit
app = Flask(__name__, 
            template_folder='web/templates',
            static_folder='web/static')

@app.route('/')
def index():
    """Показывает статус бота и информацию о версии"""
    return render_template('index.html', version=BOT_VERSION)

@app.route('/api/status')
def api_status():
    """API-эндпоинт для проверки статуса бота"""
    return jsonify({
        "status": "running", 
        "version": BOT_VERSION,
        "message": "Telegram-бот для студентов Пермского финансово-экономического колледжа запущен"
    })

# Функция для запуска бота в отдельном потоке
def start_bot():
    try:
        logging.info("Запуск Telegram-бота в отдельном потоке")
        bot_main()
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")

def init_app():
    """Инициализация приложения"""
    # Инициализация логирования
    if not os.path.exists('logs'):
        os.makedirs('logs')

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler("logs/bot.log"),
            logging.StreamHandler()
        ]
    )

    # Запуск бота в отдельном потоке
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logging.info("Основной процесс запущен, бот работает в фоновом режиме")

    return app

# При запуске файла напрямую - инициализируем приложение
if __name__ == "__main__":
    app = init_app()
    app.run(host="0.0.0.0", port=5000, debug=True)