#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Основной файл Telegram-бота для студентов Пермского финансово-экономического колледжа.
Бот предоставляет информацию о расписании, преподавателях, мероприятиях, общежитиях и др.
"""

import logging
import os
import sys
import telebot
from telebot import types
from src.utils.constants import TOKEN, MENU_BUTTONS, WELCOME_MESSAGE, ERROR_MESSAGES, USER_AGREEMENT, LICENSE_AGREEMENT
from src.database.database_manager import DatabaseManager
from src.bot.nlp_processor import NLPProcessor
from src.utils import sanitize_input, split_long_message

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Создаем директорию для логов, если она не существует
if not os.path.exists('logs'):
    os.makedirs('logs')

# Настраиваем логирование в файл
file_handler = logging.FileHandler('logs/bot.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)

class CollegeBot:
    """Основной класс бота для колледжа"""

    def __init__(self, token):
        """Инициализация бота"""
        self.token = token
        self.bot = telebot.TeleBot(token)

        # Инициализация базы данных
        self.db = DatabaseManager('data/database.db')

        # Инициализация NLP-процессора
        self.nlp = NLPProcessor()

        # Словарь для хранения состояния пользователей
        self.user_states = {}
        # Словарь для хранения ID сообщений с информацией о преподавателях
        self.teacher_display_messages = {}
        # Загружаем список преподавателей для NLP
        try:
            teachers = self.db.get_teachers()
            # Передаем напрямую список кортежей из БД в NLP-процессор
            self.nlp.set_teacher_surnames(teachers)
            logger.info(f"Инициализированы данные о преподавателях: {len(teachers)} записей")
            for teacher in teachers:
                logger.debug(f"Преподаватель: {teacher}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации данных о преподавателях: {e}")
            # Продолжаем работу даже при ошибке инициализации

        # Настройка обработчиков команд
        self.setup_handlers()

        logger.info("Бот инициализирован")

    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        # Обработчики команд
        self.bot.message_handler(commands=['start'])(self.start_command)
        self.bot.message_handler(commands=['help'])(self.help_command)
        self.bot.message_handler(commands=['menu'])(self.menu_command)
        self.bot.message_handler(commands=['terms'])(self.terms_command)
        self.bot.message_handler(commands=['license'])(self.license_command)

        # Обработчик для кнопок меню
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_button)

        # Обработчик для текстовых сообщений (вопросов)
        self.bot.message_handler(func=lambda message: True, content_types=['text'])(self.handle_text_message)

        logger.info("Обработчики команд настроены")

    def start_command(self, message):
        """Обработчик команды /start"""
        user_id = message.from_user.id
        logger.info(f"Пользователь {user_id} запустил бота")

        # Отправляем файлы соглашений
        try:
            with open('src/agreements/User Agreement.txt', 'rb') as user_agreement:
                self.bot.send_document(
                    message.chat.id,
                    user_agreement,
                    caption="Пользовательское соглашение"
                )
            with open('src/agreements/License Agreement.txt', 'rb') as license_agreement:
                self.bot.send_document(
                    message.chat.id,
                    license_agreement,
                    caption="Лицензионное соглашение"
                )
        except Exception as e:
            logger.error(f"Error sending agreement files: {e}")

        # Показываем приветственное сообщение с соглашением
        agreement_keyboard = types.InlineKeyboardMarkup()
        agreement_keyboard.row(
            types.InlineKeyboardButton("✅ Я согласен", callback_data='accept_agreement'),
            types.InlineKeyboardButton("❌ Не согласен", callback_data='decline_agreement')
        )

        agreement_text = """
👋 Добро пожаловать!

Прежде чем начать использовать бота, пожалуйста, ознакомьтесь с пользовательским и лицензионным соглашениями, которые были отправлены выше.

• Этот бот предоставляет информацию о колледже
• Все данные предоставляются "как есть"
• Используя бота, вы соглашаетесь с правилами использования

Вы согласны с условиями использования?
"""

        self.bot.send_message(
            message.chat.id,
            agreement_text,
            reply_markup=agreement_keyboard,
            parse_mode='HTML'
        )

    def help_command(self, message):
        """Обработчик команды /help"""
        help_text = """
📚 <b>Справка по использованию бота</b>

Этот бот поможет вам найти информацию о колледже.

<b>Доступные команды:</b>
/start - Запустить бота и показать главное меню
/help - Показать эту справку
/menu - Вернуться в главное меню

Вы также можете просто написать свой вопрос, и я постараюсь найти ответ.
Например: "Где находится библиотека?" или "Кто преподаёт информатику?"
"""
        self.bot.send_message(message.chat.id, help_text, parse_mode='HTML')

    def terms_command(self, message):
        """Обработчик команды /terms"""
        try:
            with open('src/agreements/User Agreement.txt', 'rb') as doc:
                self.bot.send_document(
                    message.chat.id,
                    doc,
                    caption="Пользовательское соглашение"
                )
        except Exception as e:
            logger.error(f"Error sending agreement file: {e}")
            self.bot.send_message(
                message.chat.id,
                "К сожалению, не удалось отправить файл соглашения. Попробуйте позже."
            )

    def license_command(self, message):
        """Обработчик команды /license"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )
        self.bot.send_message(
            message.chat.id,
            LICENSE_AGREEMENT,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def menu_command(self, message):
        """Обработчик команды /menu"""
        # Создаем клавиатуру для главного меню
        keyboard = types.InlineKeyboardMarkup()

        # Добавляем кнопки в меню
        keyboard.row(
            types.InlineKeyboardButton(MENU_BUTTONS['teachers'], callback_data='teachers'),
            types.InlineKeyboardButton(MENU_BUTTONS['schedule'], callback_data='schedule')
        )
        keyboard.row(
            types.InlineKeyboardButton(MENU_BUTTONS['resources'], callback_data='resources'),
            types.InlineKeyboardButton(MENU_BUTTONS['navigation'], callback_data='navigation')
        )
        keyboard.row(
            types.InlineKeyboardButton(MENU_BUTTONS['sections'], callback_data='sections'),
            types.InlineKeyboardButton(MENU_BUTTONS['dormitory'], callback_data='dormitory')
        )
        keyboard.row(
            types.InlineKeyboardButton(MENU_BUTTONS['events'], callback_data='events'),
            types.InlineKeyboardButton(MENU_BUTTONS['documents'], callback_data='documents')
        )
        keyboard.row(
            types.InlineKeyboardButton(MENU_BUTTONS['faq'], callback_data='faq')
        )

        # Отправляем сообщение с меню
        self.bot.send_message(
            message.chat.id,
            WELCOME_MESSAGE,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_button(self, call):
        """Обработчик нажатий на кнопки меню"""
        callback_data = call.data
        user_id = call.from_user.id

        logger.info(f"Пользователь {user_id} нажал кнопку с callback_data: {callback_data}")

        try:
            # Обработка возврата в главное меню
            if callback_data == 'back_to_menu':
                # Сбрасываем состояние пользователя
                if user_id in self.user_states:
                    del self.user_states[user_id]

                # Создаем клавиатуру для главного меню
                keyboard = types.InlineKeyboardMarkup()

                # Добавляем кнопки в меню
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['teachers'], callback_data='teachers'),
                    types.InlineKeyboardButton(MENU_BUTTONS['schedule'], callback_data='schedule')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['resources'], callback_data='resources'),
                    types.InlineKeyboardButton(MENU_BUTTONS['navigation'], callback_data='navigation')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['sections'], callback_data='sections'),
                    types.InlineKeyboardButton(MENU_BUTTONS['dormitory'], callback_data='dormitory')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['events'], callback_data='events'),
                    types.InlineKeyboardButton(MENU_BUTTONS['documents'], callback_data='documents')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['faq'], callback_data='faq')
                )

                # Отправляем сообщение с меню
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=WELCOME_MESSAGE,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return

            # Обработка разделов
            if callback_data == 'teachers':
                self.handle_teachers(call)
            elif callback_data == 'schedule':
                self.handle_schedule(call)
            elif callback_data == 'resources':
                self.handle_resources(call)
            elif callback_data == 'navigation':
                self.handle_navigation(call)
            elif callback_data == 'sections':
                self.handle_sections(call)
            elif callback_data == 'dormitory':
                self.handle_dormitory(call)
            elif callback_data == 'events':
                self.handle_events(call)
            elif callback_data == 'documents':
                self.handle_documents(call)
            elif callback_data == 'faq':
                self.handle_faq(call)
            elif callback_data == 'terms':
                # Показываем пользовательское соглашение
                keyboard = types.InlineKeyboardMarkup()
                keyboard.row(
                    types.InlineKeyboardButton("« Назад", callback_data='back_to_menu')
                )
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=USER_AGREEMENT,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            elif callback_data.startswith('faq_page_'):
                # Обработка постраничной навигации для FAQ
                try:
                    page_num = int(callback_data.split('_')[-1])
                    self.handle_faq(call, page=page_num)
                except (ValueError, IndexError) as e:
                    logger.error(f"Ошибка при обработке страницы FAQ: {e}")
                    self.handle_faq(call, page=0)
            elif callback_data.startswith('teacher_page_'):
                # Обработка постраничной навигации для списка преподавателей
                try:
                    # Формат: teacher_page_номер-страницы_поисковый-запрос
                    parts = callback_data.split('_', 3)
                    if len(parts) >= 3:
                        page_num = int(parts[2])
                        search_text = parts[3] if len(parts) > 3 else ""
                        self.show_teacher_page(call, page_num, search_text)
                    else:
                        logger.error(f"Неверный формат callback_data для навигации по преподавателям: {callback_data}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Ошибка при обработке страницы преподавателей: {e}")
            elif callback_data == 'teacher_search':
                self.handle_teacher_search(call)
            elif callback_data.startswith('teacher_'):
                teacher_id = callback_data.split('_')[1]
                self.show_teacher_info(call, teacher_id)
            elif callback_data == 'accept_agreement':
                # Создаем клавиатуру для главного меню
                keyboard = types.InlineKeyboardMarkup()

                # Добавляем кнопки в меню
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['teachers'], callback_data='teachers'),
                    types.InlineKeyboardButton(MENU_BUTTONS['schedule'], callback_data='schedule')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['resources'], callback_data='resources'),
                    types.InlineKeyboardButton(MENU_BUTTONS['navigation'], callback_data='navigation')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['sections'], callback_data='sections'),
                    types.InlineKeyboardButton(MENU_BUTTONS['dormitory'], callback_data='dormitory')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['events'], callback_data='events'),
                    types.InlineKeyboardButton(MENU_BUTTONS['documents'], callback_data='documents')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['faq'], callback_data='faq')
                )

                # Сначала подтверждаем принятие соглашения
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="✅ Спасибо! Вы приняли условия пользовательского соглашения.",
                    parse_mode='HTML'
                )

                # Затем отправляем новым сообщением главное меню
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text=WELCOME_MESSAGE,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            elif callback_data == 'decline_agreement':
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="❌ К сожалению, без принятия условий использования бот недоступен.\n\nДля начала работы используйте команду /start и примите условия использования.",
                    parse_mode='HTML'
                )
            else:
                logger.warning(f"Неизвестный callback_data: {callback_data}")
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Извините, данная функция находится в разработке.",
                    parse_mode='HTML'
                )

        except Exception as e:
            logger.error(f"Ошибка при обработке кнопки {callback_data}: {e}")
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="Произошла ошибка. Пожалуйста, попробуйте позже.",
                parse_mode='HTML'
            )

    def handle_text_message(self, message):
        """Обработчик текстовых сообщений (вопросов от пользователей)"""
        text = sanitize_input(message.text)
        user_id = message.from_user.id

        logger.info(f"Получено сообщение от пользователя {user_id}: {text}")

        # Проверяем, находится ли пользователь в режиме поиска преподавателя
        if user_id in self.user_states and self.user_states[user_id] == 'waiting_for_teacher_name':
            logger.info(f"Пользователь {user_id} в режиме поиска преподавателя, пропускаем обработку NLP")
            return

        try:
            # Обрабатываем текстовый запрос через NLP
            response = self.nlp.process_query(text.lower(), self.db)

            if response:
                # Если получили ответ от NLP, отправляем его
                logger.info(f"Sending NLP response to user {user_id}")

                # Добавляем кнопку "Назад в меню"
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu'))

                # Разбиваем длинное сообщение, если нужно
                message_parts = split_long_message(response, 4000)

                for part in message_parts:
                    self.bot.send_message(
                        message.chat.id,
                        part,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
            else:
                # Если NLP не справился, отправляем кнопки меню
                logger.info(f"No NLP response, showing generic message to user {user_id}")

                keyboard = types.InlineKeyboardMarkup()
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['teachers'], callback_data='teachers'),
                    types.InlineKeyboardButton(MENU_BUTTONS['schedule'], callback_data='schedule')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['resources'], callback_data='resources'),
                    types.InlineKeyboardButton(MENU_BUTTONS['navigation'], callback_data='navigation')
                )
                keyboard.row(
                    types.InlineKeyboardButton(MENU_BUTTONS['faq'], callback_data='faq')
                )

                self.bot.send_message(
                    message.chat.id,
                    "Извините, я не смог понять ваш запрос. Пожалуйста, попробуйте переформулировать вопрос "
                    "или воспользуйтесь кнопками меню:",
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения '{text}': {e}")
            self.bot.send_message(
                message.chat.id,
                ERROR_MESSAGES['nlp_error']
            )

    # Базовые обработчики разделов
    def handle_teachers(self, call):
        """Обрабатывает раздел преподавателей"""
        # Сбрасываем состояние пользователя
        user_id = call.from_user.id
        if user_id in self.user_states:
            del self.user_states[user_id]

        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("🔍 Поиск по фамилии", callback_data='teacher_search')
        )
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        try:
            # Пробуем отредактировать существующее сообщение
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="👨‍🏫 <b>Информация о преподавателях</b>\n\nВы можете найти информацию о преподавателях колледжа по фамилии.",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            # Если не получается отредактировать, отправляем новое сообщение
            self.bot.send_message(
                chat_id=call.message.chat.id,
                text="👨‍🏫 <b>Информация о преподавателях</b>\n\nВы можете найти информацию о преподавателях колледжа по фамилии.",
                reply_markup=keyboard,
                parse_mode='HTML'
            )



    def handle_schedule(self, call):
        """Обрабатывает раздел расписания"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🕒 <b>Расписание занятий</b>\n\nРасписание занятий доступно на официальном сайте колледжа: https://pfek.ru/schedule/",
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_resources(self, call):
        """Обрабатывает раздел полезных ресурсов"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        resources_text = """🔗 <b>Полезные ресурсы</b>

<b>Официальные ресурсы колледжа:</b>
• Сайт колледжа: https://pfek.ru/
• Группа ВКонтакте: https://vk.com/pfekperm
• Телеграм-канал: https://t.me/pfekperm

<b>Образовательные ресурсы:</b>
• Электронная библиотека: https://pfek.ru/library/
• Учебные материалы: https://pfek.ru/students/
"""

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=resources_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_navigation(self, call):
        """Обрабатывает раздел навигации по колледжу"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        # Получаем информацию о навигации из базы данных
        navigations = self.db.get_navigation()

        if not navigations:
            text = "🏢 <b>Навигация по колледжу</b>\n\nИнформация о расположении аудиторий и кабинетов временно недоступна."
        else:
            text = "🏢 <b>Навигация по колледжу</b>\n\n"
            for nav in navigations[:10]:  # Ограничиваем количество результатов
                # Предполагаем, что первые поля - название места и описание
                location = nav[1] if len(nav) > 1 else "Неизвестное место"
                description = nav[2] if len(nav) > 2 else "Описание отсутствует"
                text += f"<b>{location}</b>: {description}\n\n"

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_sections(self, call):
        """Обрабатывает раздел спортивных секций"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        # Получаем информацию о секциях из базы данных
        sections = self.db.get_sections()

        if not sections:
            text = "🏆 <b>Спортивные секции</b>\n\nИнформация о спортивных секциях временно недоступна."
        else:
            text = "🏆 <b>Спортивные секции</b>\n\n"
            for section in sections:
                # Предполагаем, что первые поля - название секции, расписание, тренер
                name = section[1] if len(section) > 1 else "Секция без названия"
                schedule = section[2] if len(section) > 2 else "Расписание не указано"
                coach = section[3] if len(section) > 3 else "Тренер не указан"

                text += f"<b>{name}</b>\n"
                text += f"🕒 Расписание: {schedule}\n"
                text += f"👨‍🏫 Тренер: {coach}\n\n"

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_dormitory(self, call):
        """Обрабатывает раздел информации об общежитиях"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        # Получаем информацию об общежитиях из базы данных
        dorms = self.db.get_dormitories()
        logger.debug(f"Получены данные об общежитиях: {dorms}")

        if not dorms:
            text = "🏠 <b>Общежития</b>\n\nИнформация об общежитиях временно недоступна."
        else:
            text = "🏠 <b>Общежития</b>\n\n"
            for dorm in dorms:
                # Структура таблицы: id, number, warden, address, phone, info
                number = dorm[1] if len(dorm) > 1 else "Номер не указан"
                warden = dorm[2] if len(dorm) > 2 else "Комендант не указан"
                address = dorm[3] if len(dorm) > 3 else "Адрес не указан"
                phone = dorm[4] if len(dorm) > 4 else "Телефон не указан"
                info = dorm[5] if len(dorm) > 5 else ""

                text += f"<b>Общежитие №{number}</b>\n"
                text += f"👤 Комендант: {warden}\n"
                text += f"📍 Адрес: {address}\n"
                text += f"📞 Телефон: {phone}\n"
                if info:
                    text += f"ℹ️ Информация: {info}\n"
                text += "\n"

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_events(self, call):
        """Обрабатывает раздел информации о мероприятиях"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        # Получаем информацию о мероприятиях из базы данных
        events = self.db.get_events()
        logger.debug(f"Получены данные о мероприятиях: {events}")

        if not events:
            text = "🎉 <b>Мероприятия</b>\n\nИнформация о предстоящих мероприятиях временно недоступна."
        else:
            text = "🎉 <b>Предстоящие мероприятия</b>\n\n"
            for event in events:
                # Структура таблицы: id, date, title, location
                date = event[1] if len(event) > 1 else "Дата не указана"
                title = event[2] if len(event) > 2 else "Мероприятие без названия"
                location = event[3] if len(event) > 3 else "Место не указано"

                text += f"<b>{title}</b>\n"
                text += f"📅 Дата: {date}\n"
                text += f"📍 Место: {location}\n\n"

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_documents(self, call):
        """Обрабатывает раздел информации о документах"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        # Получаем информацию о документах из базы данных
        docs = self.db.get_documents()

        if not docs:
            text = "📄 <b>Документы</b>\n\nИнформация о документах временно недоступна."
        else:
            text = "📄 <b>Документы</b>\n\n"
            for doc in docs:
                # Предполагаем, что поля - название документа, описание, ссылка
                name = doc[1] if len(doc) > 1 else "Документ"
                description = doc[2] if len(doc) > 2 else "Без описания"
                link = doc[3] if len(doc) > 3 else None

                text += f"<b>{name}</b>\n"
                text += f"{description}\n"
                if link:
                    text += f"🔗 <a href='{link}'>Скачать</a>\n"
                text += "\n"

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_agreements(self, call):
        """Обработчик раздела соглашений"""
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("Пользовательское соглашение", callback_data='terms')
        )
        keyboard.row(
            types.InlineKeyboardButton("Лицензионное соглашение", callback_data='license')
        )
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        text = "📋 <b>Соглашения</b>\n\nВыберите соглашение для просмотра:"

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

    def handle_faq(self, call, page=0):
        """Обрабатывает раздел часто задаваемых вопросов с поддержкой постраничной навигации"""
        # Получаем FAQ из базы данных
        faqs = self.db.get_faq()
        logger.debug(f"Получены FAQ: {len(faqs) if faqs else 0} записей")

        if not faqs:
            text = "❓ <b>Часто задаваемые вопросы</b>\n\nРаздел часто задаваемых вопросов пока пуст."
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(
                types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
            )
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return

        # Определяем количество вопросов на странице и общее количество страниц
        faqs_per_page = 3  # Показываем 3 вопроса на странице
        total_pages = (len(faqs) + faqs_per_page - 1) // faqs_per_page  # Округление вверх

        # Проверяем, что номер страницы в допустимых пределах
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1

        # Определяем индексы вопросов для текущей страницы
        start_idx = page * faqs_per_page
        end_idx = min(start_idx + faqs_per_page, len(faqs))

        # Создаем клавиатуру с кнопками навигации
        keyboard = types.InlineKeyboardMarkup()

        # Добавляем кнопки навигации по страницам
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("« Пред.", callback_data=f'faq_page_{page-1}'))

        nav_buttons.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data='faq'))

        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton("След. »", callback_data=f'faq_page_{page+1}'))

        if nav_buttons:
            keyboard.row(*nav_buttons)

        # Добавляем кнопку возврата в меню
        keyboard.row(
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        # Формируем текст с вопросами для текущей страницы
        text = f"❓ <b>Часто задаваемые вопросы (Страница {page+1} из {total_pages})</b>\n\n"

        # Добавляем вопросы и ответы для текущей страницы
        for i in range(start_idx, end_idx):
            faq = faqs[i]
            question = faq[1] if len(faq) > 1 else "Вопрос"
            answer = faq[2] if len(faq) > 2 else "Ответ отсутствует"

            # Ограничиваем длину ответа, если он слишком длинный
            if len(answer) > 300:
                answer = answer[:297] + "..."

            # Добавляем вопрос и ответ в текст сообщения
            text += f"<b>Вопрос {i+1}:</b> {question}\n"
            text += f"<b>Ответ:</b> {answer}\n\n"

        # Добавляем завершающий текст, если отображается последняя страница
        if page == total_pages - 1:
            text += "Для получения дополнительной информации посетите официальный сайт колледжа."

        try:
            # Отправляем сообщение с вопросами и клавиатурой навигации
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка при отображении FAQ: {e}")
            # В случае ошибки пытаемся отправить сообщение заново
            try:
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as send_err:
                logger.error(f"Не удалось отправить FAQ даже новым сообщением: {send_err}")
                # Если и это не помогло, отправляем сокращенную версию
                text = "❓ <b>Часто задаваемые вопросы</b>\n\n"
                text += "Извините, произошла ошибка при загрузке вопросов. Попробуйте позже или обратитесь в информационный центр колледжа."
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )

    def handle_teacher_search(self, call):
        """Обрабатывает поиск преподавателя"""
        user_id = call.from_user.id

        # Устанавливаем состояние пользователя - ожидание ввода фамилии преподавателя
        self.user_states[user_id] = 'waiting_for_teacher_name'

        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("« Назад к преподавателям", callback_data='teachers'),
            types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
        )

        text = ("🔍 <b>Поиск преподавателей</b>\n\n"
               "Введите фамилию преподавателя или ее часть, например: \"Ставицкая\" или \"Бочаров\"")

        self.bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

        # Устанавливаем обработчик для ожидания ввода фамилии преподавателя
        self.bot.register_next_step_handler(call.message, self.process_teacher_search_query)

    def show_teacher_page(self, call, page, search_text):
        """Показывает страницу с результатами поиска преподавателей"""
        try:
            # Получаем информацию о преподавателях из базы данных
            teachers = self.db.get_teachers(search_text)
            logger.debug(f"Найденные преподаватели по запросу '{search_text}': {teachers}")
            
            keyboard = types.InlineKeyboardMarkup()
            
            if not teachers:
                text = (f"🔍 <b>Поиск преподавателей</b>\n\n"
                       f"По запросу \"{search_text}\" ничего не найдено.\n"
                       f"Пожалуйста, проверьте правильность написания фамилии преподавателя.")
                       
                keyboard.row(
                    types.InlineKeyboardButton("« Назад к поиску", callback_data='teacher_search'),
                    types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
                )
                
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return
                
            # Формируем текст с результатами поиска
            text = f"🔍 <b>Результаты поиска по запросу \"{search_text}\"</b>\n\n"
            
            # Группируем преподавателей по фамилии для устранения дубликатов
            unique_teachers = {}
            
            for teacher in teachers:
                teacher_id = teacher[0]
                surname = teacher[1] if len(teacher) > 1 else ""
                first_name = teacher[2] if len(teacher) > 2 else ""
                middle_name = teacher[3] if len(teacher) > 3 else ""
                position = teacher[4] if len(teacher) > 4 else ""
                cabinet = teacher[5] if len(teacher) > 5 else ""
                photo = teacher[6] if len(teacher) > 6 else None
                
                # Формируем ФИО
                full_name = f"{surname} {first_name} {middle_name}".strip()
                
                # Используем ID преподавателя в качестве ключа для абсолютной уникальности
                unique_teachers[teacher_id] = {
                    'id': teacher_id,
                    'full_name': full_name,
                    'surname': surname,
                    'position': position,
                    'cabinet': cabinet,
                    'photo': photo
                }
            
            # Добавляем кнопки для преподавателей с постраничной навигацией
            text += f"Найдено преподавателей: {len(unique_teachers)}\n\n"
            text += "Выберите преподавателя, чтобы посмотреть информацию о нем:"
            
            # Сортируем преподавателей по фамилии для удобства
            sorted_teachers = sorted(unique_teachers.values(), key=lambda x: x['full_name'])
            
            # Реализуем постраничную навигацию
            TEACHERS_PER_PAGE = 5  # Количество преподавателей на одной странице
            total_pages = (len(sorted_teachers) + TEACHERS_PER_PAGE - 1) // TEACHERS_PER_PAGE
            
            # Проверяем валидность номера страницы
            if page < 0:
                page = 0
            elif page >= total_pages:
                page = total_pages - 1
                
            # Получаем учителей для текущей страницы
            start_idx = page * TEACHERS_PER_PAGE
            end_idx = min(start_idx + TEACHERS_PER_PAGE, len(sorted_teachers))
            current_page_teachers = sorted_teachers[start_idx:end_idx]
            
            # Добавляем кнопки для каждого преподавателя на текущей странице
            for teacher_data in current_page_teachers:
                button_text = f"{teacher_data['full_name']}"
                if teacher_data['position'] and not teacher_data['position'].isdigit():
                    button_text += f" ({teacher_data['position']})"
                elif teacher_data['cabinet']:
                    button_text += f" (каб. {teacher_data['cabinet']})"
                
                keyboard.row(
                    types.InlineKeyboardButton(button_text, callback_data=f'teacher_{teacher_data["id"]}')
                )
            
            # Добавляем навигационные кнопки
            nav_buttons = []
            
            # Кнопка "Предыдущая страница" (недоступна на первой странице)
            if page > 0:
                nav_buttons.append(types.InlineKeyboardButton("« Назад", callback_data=f'teacher_page_{page-1}_{search_text}'))
            
            # Индикатор текущей страницы
            nav_buttons.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
            
            # Кнопка "Следующая страница" (недоступна на последней странице)
            if page < total_pages - 1:
                nav_buttons.append(types.InlineKeyboardButton("Вперед »", callback_data=f'teacher_page_{page+1}_{search_text}'))
            
            # Добавляем навигационные кнопки, если больше одной страницы
            if total_pages > 1:
                keyboard.row(*nav_buttons)
            
            # Добавляем кнопки назад
            keyboard.row(
                types.InlineKeyboardButton("« Назад к поиску", callback_data='teacher_search'),
                types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
            )
            
            # Отправляем сообщение с результатами поиска и кнопками
            self.bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Error in show_teacher_page: {e}")
            try:
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Произошла ошибка при загрузке списка преподавателей. Попробуйте позже.",
                    parse_mode='HTML'
                )
            except:
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text="Произошла ошибка при загрузке списка преподавателей. Попробуйте позже.",
                    parse_mode='HTML'
                )
    
    def process_teacher_search_query(self, message):
        """Обрабатывает введенный запрос поиска преподавателя"""
        search_text = sanitize_input(message.text)
        user_id = message.from_user.id

        # Сбрасываем состояние пользователя после обработки запроса
        if user_id in self.user_states:
            del self.user_states[user_id]

        logger.info(f"Received teacher search query from user {user_id}: {search_text}")

        try:
            # Выполняем поиск преподавателя
            teachers = self.db.get_teachers(search_text)
            logger.debug(f"Найденные преподаватели по запросу '{search_text}': {teachers}")

            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(
                types.InlineKeyboardButton("« Назад к поиску", callback_data='teacher_search'),
                types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
            )

            if not teachers:
                text = (f"🔍 <b>Поиск преподавателей</b>\n\n"
                       f"По запросу \"{search_text}\" ничего не найдено.\n"
                       f"Пожалуйста, проверьте правильность написания фамилии преподавателя.")

                self.bot.send_message(
                    message.chat.id,
                    text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                return

            # Формируем текст с результатами поиска
            text = f"🔍 <b>Результаты поиска по запросу \"{search_text}\"</b>\n\n"

            # Группируем преподавателей по фамилии для устранения дубликатов
            unique_teachers = {}

            for teacher in teachers:
                teacher_id = teacher[0]
                surname = teacher[1] if len(teacher) > 1 else ""
                first_name = teacher[2] if len(teacher) > 2 else ""
                middle_name = teacher[3] if len(teacher) > 3 else ""
                position = teacher[4] if len(teacher) > 4 else ""
                cabinet = teacher[5] if len(teacher) > 5 else ""
                photo = teacher[6] if len(teacher) > 6 else None

                # Формируем ФИО
                full_name = f"{surname} {first_name} {middle_name}".strip()

                # Используем ID преподавателя в качестве ключа для абсолютной уникальности
                unique_teachers[teacher_id] = {
                    'id': teacher_id,
                    'full_name': full_name,
                    'surname': surname,
                    'position': position,
                    'cabinet': cabinet,
                    'photo': photo
                }

            # Добавляем кнопки для преподавателей с постраничной навигацией
            text += f"Найдено преподавателей: {len(unique_teachers)}\n\n"
            text += "Выберите преподавателя, чтобы посмотреть информацию о нем:"

            # Сортируем преподавателей по фамилии для удобства
            sorted_teachers = sorted(unique_teachers.values(), key=lambda x: x['full_name'])
            
            # Реализуем постраничную навигацию
            TEACHERS_PER_PAGE = 5  # Количество преподавателей на одной странице
            page = 0  # Начинаем с первой страницы
            total_pages = (len(sorted_teachers) + TEACHERS_PER_PAGE - 1) // TEACHERS_PER_PAGE
            
            # Получаем учителей для первой страницы
            start_idx = page * TEACHERS_PER_PAGE
            end_idx = min(start_idx + TEACHERS_PER_PAGE, len(sorted_teachers))
            current_page_teachers = sorted_teachers[start_idx:end_idx]
            
            # Добавляем кнопки для каждого преподавателя на текущей странице
            for teacher_data in current_page_teachers:
                button_text = f"{teacher_data['full_name']}"
                if teacher_data['position'] and not teacher_data['position'].isdigit():
                    button_text += f" ({teacher_data['position']})"
                elif teacher_data['cabinet']:
                    button_text += f" (каб. {teacher_data['cabinet']})"
                
                keyboard.row(
                    types.InlineKeyboardButton(button_text, callback_data=f'teacher_{teacher_data["id"]}')
                )
            
            # Добавляем навигационные кнопки
            nav_buttons = []
            
            # Кнопка "Предыдущая страница" (недоступна на первой странице)
            if page > 0:
                nav_buttons.append(types.InlineKeyboardButton("« Назад", callback_data=f'teacher_page_{page-1}_{search_text}'))
            
            # Индикатор текущей страницы
            nav_buttons.append(types.InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
            
            # Кнопка "Следующая страница" (недоступна на последней странице)
            if page < total_pages - 1:
                nav_buttons.append(types.InlineKeyboardButton("Вперед »", callback_data=f'teacher_page_{page+1}_{search_text}'))
            
            # Добавляем эти кнопки, если есть больше одной страницы
            if total_pages > 1:
                keyboard.row(*nav_buttons)
                
            # Отправляем сообщение с результатами поиска и кнопками
            self.bot.send_message(
                message.chat.id,
                text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )

        except Exception as e:
            logger.error(f"Error in process_teacher_search_query: {e}")
            self.bot.send_message(
                message.chat.id,
                "Произошла ошибка при поиске. Пожалуйста, попробуйте позже.",
                parse_mode='HTML'
            )

    def show_teacher_info(self, call, teacher_id):
        """Показывает информацию о конкретном преподавателе"""
        try:
            # Получаем информацию о преподавателе из базы данных
            query = "SELECT * FROM Prepodavately WHERE id = ?"
            teachers = self.db.execute_query(query, (teacher_id,))
            logger.debug(f"Данные преподавателя {teacher_id}: {teachers}")

            if not teachers:
                self.bot.answer_callback_query(call.id, "Информация о преподавателе не найдена")
                logger.warning(f"Teacher with ID {teacher_id} not found")
                return

            teacher = teachers[0]
            
            # Если у пользователя было сообщение с фото, удаляем его
            if call.from_user.id in self.teacher_display_messages:
                try:
                    self.bot.delete_message(
                        chat_id=call.message.chat.id,
                        message_id=self.teacher_display_messages[call.from_user.id]
                    )
                except Exception as e:
                    logger.error(f"Не удалось удалить предыдущее сообщение с фото: {e}")

            # Создаем клавиатуру с кнопками навигации
            keyboard = types.InlineKeyboardMarkup()
            
            # Добавляем кнопки возврата
            keyboard.row(
                types.InlineKeyboardButton("« Назад к поиску", callback_data='teachers'),
                types.InlineKeyboardButton("« Назад в меню", callback_data='back_to_menu')
            )

            # Структура таблицы: id, Фамилия, Имя, Отчество, Должность, Кабинет, Фото
            surname = teacher[1] if len(teacher) > 1 else ""
            first_name = teacher[2] if len(teacher) > 2 else ""
            middle_name = teacher[3] if len(teacher) > 3 else ""
            position = teacher[4] if len(teacher) > 4 else ""
            cabinet = teacher[5] if len(teacher) > 5 else ""
            photo = teacher[6] if len(teacher) > 6 else None

            # Получаем дисциплины преподавателя из новой таблицы
            disciplines_list = self.db.get_teacher_disciplines(teacher_id)
            logger.info(f"Получены дисциплины для преподавателя {teacher_id}: {len(disciplines_list)} шт.")

            # Формируем ФИО
            full_name = f"{surname} {first_name} {middle_name}".strip()

            # Формируем карточку преподавателя
            text = f"📋 <b>Карточка преподавателя</b>\n\n"
            text += f"👨‍🏫 <b>ФИО:</b> {full_name}\n"

            # Проверяем, является ли position номером кабинета (часто это число)
            if position and position.isdigit():
                cabinet = position  # Используем position как cabinet
                position = None     # Очищаем position
            
            if position:
                text += f"🧑‍💼 <b>Должность:</b> {position}\n"

            if cabinet:
                text += f"🚪 <b>Кабинет:</b> {cabinet}\n"

            # Форматируем дисциплины из нового источника
            if disciplines_list:
                from src.utils import format_teacher_disciplines
                formatted_disciplines = format_teacher_disciplines(disciplines_list)
                if formatted_disciplines:
                    text += f"\n📚 <b>Дисциплины:</b>\n{formatted_disciplines}\n"
                else:
                    text += f"\n📚 <b>Дисциплины:</b> Информация недоступна\n"
            else:
                text += f"\n📚 <b>Дисциплины:</b> Информация не найдена\n"

            # Проверяем, есть ли фото
            has_photo = photo is not None and len(photo) > 100

            # Разбиваем сообщение для отправки
            from src.utils import split_long_message
            
            # Если нет фото, просто редактируем существующее сообщение
            if not has_photo:
                logger.warning(f"Фото преподавателя {surname} (ID: {teacher_id}) отсутствует или некорректно")
                
                # Разбиваем сообщение, если оно слишком длинное
                message_parts = split_long_message(text, 4000)
                
                # Отправляем сообщение
                for i, part in enumerate(message_parts):
                    # Последняя часть сообщения содержит кнопки
                    if i == len(message_parts) - 1:
                        self.bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=part,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    else:
                        self.bot.send_message(
                            call.message.chat.id,
                            part,
                            parse_mode='HTML'
                        )
                return
            
            # Если у нас есть фото, отправляем его с описанием
            logger.info(f"Фото преподавателя {surname} найдено, размер: {len(photo)} байт")
            
            try:
                # Удаляем предыдущее сообщение, чтобы отправить новое с фото
                self.bot.delete_message(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                logger.info(f"Предыдущее сообщение удалено")
            except Exception as del_error:
                logger.error(f"Ошибка при удалении предыдущего сообщения: {del_error}")
            
            try:
                import io
                # Создаем объект BytesIO из бинарных данных
                photo_bytes = io.BytesIO(photo)
                photo_bytes.seek(0)
                
                # Отправляем фото с подписью (ограничиваем до 1024 символов - максимум для caption)
                caption = text
                if len(caption) > 1000:
                    # Если текст слишком длинный, отправляем фото с кратким описанием,
                    # а затем отдельно полный текст
                    caption = f"📋 <b>Карточка преподавателя</b>\n\n👨‍🏫 <b>ФИО:</b> {full_name}"
                    if position:
                        caption += f"\n🧑‍💼 <b>Должность:</b> {position}"
                    if cabinet:
                        caption += f"\n🚪 <b>Кабинет:</b> {cabinet}"
                    
                    # Отправляем фото с кратким описанием
                    self.bot.send_photo(
                        chat_id=call.message.chat.id,
                        photo=photo_bytes,
                        caption=caption,
                        parse_mode='HTML'
                    )
                    
                    # Отправляем полное описание с кнопками
                    self.bot.send_message(
                        chat_id=call.message.chat.id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                else:
                    # Если текст помещается в caption, отправляем все вместе
                    message = self.bot.send_photo(
                        chat_id=call.message.chat.id,
                        photo=photo_bytes,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    
                    # Запоминаем ID сообщения для последующей навигации
                    self.teacher_display_messages[call.from_user.id] = message.message_id
                
                logger.info(f"Фото преподавателя {surname} успешно отправлено")
                
            except Exception as send_error:
                logger.error(f"Ошибка при отправке фото: {send_error}")
                # В случае ошибки, отправляем текстовое сообщение
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )

            logger.info(f"Показана информация о преподавателе {teacher[1]} пользователю {call.from_user.id}")

        except Exception as e:
            logger.error(f"Error in show_teacher_info: {e}")
            # Пытаемся обновить существующее сообщение
            try:
                self.bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="Произошла ошибка при загрузке информации о преподавателе. Попробуйте позже.",
                    parse_mode='HTML'
                )
            except:
                # Если не получается обновить, отправляем новое
                self.bot.send_message(
                    chat_id=call.message.chat.id,
                    text="Произошла ошибка при загрузке информации о преподавателе. Попробуйте позже.",
                    parse_mode='HTML'
                )

    def start(self):
        """Запуск бота"""
        # Проверяем подключение к базе данных перед запуском
        try:
            self.db.execute_query("SELECT 1")
            logger.info("Соединение с базой данных успешно установлено")
        except Exception as e:
            logger.error(f"Ошибка при подключении к базе данных: {e}")
            sys.exit(1)

        # Запускаем бота
        logger.info("Запуск бота...")
        self.bot.infinity_polling()
        logger.info("Бот остановлен")

def main():
    """Основная функция для запуска бота"""
    try:
        # Проверяем наличие токена
        if not TOKEN:
            logger.error("Не установлен TOKEN. Пожалуйста, укажите его в файле constants.py")
            sys.exit(1)

        # Создаем и запускаем экземпляр бота
        bot = CollegeBot(TOKEN)
        bot.start()

    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()