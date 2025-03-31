try:
    import pymorphy3
except ImportError:
    # Для тех, кто уже установил pymorphy3
    pass
from typing import List, Tuple, Optional, Dict, Any
import re
import logging
from src.utils import format_teacher_disciplines

logger = logging.getLogger(__name__)

class NLPProcessor:
    """Класс для обработки естественного языка и запросов пользователей"""
    
    def __init__(self):
        """Инициализация морфологического анализатора"""
        self.morph = pymorphy3.MorphAnalyzer()
        
        # Словарь фамилий преподавателей
        self.teacher_surnames = {}
        
        # Категории запросов и связанные с ними ключевые слова
        self.categories: Dict[str, set] = {
            'teacher': {'преподаватель', 'учитель', 'педагог', 'преподает', 'ведет', 'пара', 'пары', 
                       'урок', 'уроки', 'кто', 'такая', 'такой', 'какие', 'предметы', 'покажи', 'расскажи', 
                       'информация', 'список', 'о преподавателях', 'о учителях', 'покажи', 'учат', 'преподаватели',
                       'найти', 'контакты', 'препод', 'ведёт', 'учит', 'фамилия', 'препода'},
            'discipline': {'предмет', 'дисциплина', 'математика', 'информатика', 'программирование', 'экономика',
                         'бухучет', 'бухгалтерия', 'физкультура', 'английский', 'история', 'физика', 'право',
                         'литература', 'русский', 'алгебра', 'геометрия', 'химия', 'биология', 'курс', 
                         'лекция', 'семинар', 'практика', 'лаба', 'преподает', 'ведет', 'изучает', 'изучаем'},
            'document': {'справка', 'документ', 'заявление', 'получить', 'оформить', 'бумага', 'справки', 
                        'документы', 'бумаги', 'заполнить', 'подать', 'справку'},
            'navigation': {'где', 'найти', 'находится', 'расположение', 'аудитория', 'кабинет', 'этаж', 'корпус', 
                          'столовая', 'библиотека', 'буфет', 'расположена', 'аудитории', 'находятся', 'поиск', 
                          'как пройти', 'дорога', 'путь', 'актовый', 'зал', 'лаборатория', 'медпункт', 'деканат'},
            'event': {'мероприятие', 'событие', 'праздник', 'концерт', 'выступление', 'когда', 'какие', 
                     'фестиваль', 'встреча', 'семинар', 'конференция', 'анонс', 'скоро', 'мероприятия', 'афиша'},
            'sport': {'секция', 'спорт', 'тренировка', 'занятие', 'тренер', 'игра', 'какие', 'есть', 
                     'секции', 'занятия', 'спортивные', 'спортзал', 'физкультура', 'футбол', 'волейбол', 
                     'баскетбол', 'теннис', 'тренер', 'физрук', 'спортивный', 'заниматься'},
            'dormitory': {'общежитие', 'общага', 'комната', 'проживание', 'заселение', 'комендант', 'жить', 
                         'поселиться', 'квартира', 'общежития', 'заселиться', 'условия', 'плата', 'снять'}
        }
        
        # Стоп-слова, которые исключаются из обработки
        self.stop_words = {'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 
                          'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 
                          'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 
                          'ему', 'такая', 'это', 'эта', 'где', 'какая'}

    def set_teacher_surnames(self, teachers_list):
        """Устанавливает словарь фамилий преподавателей для быстрого поиска"""
        try:
            self.teacher_surnames = {}
            
            if not teachers_list or len(teachers_list) == 0:
                logger.warning("Empty teachers list provided to set_teacher_surnames")
                return
                
            for teacher in teachers_list:
                if not isinstance(teacher, (list, tuple)):
                    logger.warning(f"Invalid teacher data type: {type(teacher)}")
                    continue
                    
                # Проверим, есть ли у нас все необходимые поля
                if len(teacher) < 4:
                    logger.warning(f"Teacher record has insufficient fields: {teacher}")
                    continue
                    
                # Собираем ФИО из фамилии, имени и отчества (индексы 1, 2, 3)
                try:
                    surname = str(teacher[1]).lower()  # Фамилия в нижнем регистре
                    full_name = f"{teacher[1]} {teacher[2]} {teacher[3]}"  # ФИО
                    self.teacher_surnames[surname] = full_name
                    logger.debug(f"Added teacher surname: {surname} -> {full_name}")
                except Exception as e:
                    logger.error(f"Error processing teacher record {teacher}: {e}")
            
            logger.info(f"Teacher surnames dictionary initialized with {len(self.teacher_surnames)} entries")
        except Exception as e:
            logger.error(f"Error initializing teacher surnames: {e}")
            self.teacher_surnames = {}

    def normalize_word(self, word: str) -> str:
        """Приводит слово к нормальной форме"""
        try:
            return self.morph.parse(word)[0].normal_form
        except Exception as e:
            logger.error(f"Error normalizing word '{word}': {e}")
            return word

    def extract_keywords(self, text: str) -> List[str]:
        """Извлекает ключевые слова из текста"""
        try:
            # Убираем знаки препинания и приводим к нижнему регистру
            text = re.sub(r'[^\w\s]', ' ', text.lower())

            # Разбиваем на слова и нормализуем каждое
            words = text.split()
            normalized_words = [self.normalize_word(word) for word in words]

            # Фильтруем стоп-слова
            keywords = [word for word in normalized_words if word not in self.stop_words]
            logger.debug(f"Extracted keywords from '{text}': {keywords}")
            return keywords
        except Exception as e:
            logger.error(f"Error extracting keywords from '{text}': {e}")
            return []

    def find_discipline_in_text(self, text: str) -> Optional[str]:
        """Ищет упоминание дисциплины в тексте"""
        try:
            # Сначала проверяем конкретные упоминания дисциплин
            if "ведет" in text.lower() or "преподает" in text.lower() or "ведёт" in text.lower():
                for word in self.extract_keywords(text.lower()):
                    for discipline in self.categories.get('discipline', set()):
                        if discipline in word:
                            logger.info(f"Found discipline in query context: {discipline}")
                            return discipline.capitalize()
            
            # Ищем паттерны вида "МДК XX.XX"
            mdk_pattern = re.compile(r'мдк\s*\d{2}\.\d{2}', re.IGNORECASE)
            match = mdk_pattern.search(text)
            if match:
                # Форматируем найденное значение МДК (удаляем пробелы и приводим к верхнему регистру)
                found_mdk = match.group().upper().replace(' ', '')
                logger.info(f"Found discipline in text: {found_mdk}")
                return found_mdk
                
            # Ищем имена общих дисциплин
            common_disciplines = ['математика', 'информатика', 'русский язык', 'литература', 
                                'история', 'физика', 'химия', 'биология', 'экономика', 'право',
                                'бухгалтерия', 'программирование', 'английский язык', 'философия',
                                'психология', 'статистика', 'культура', 'менеджмент', 'маркетинг',
                                'социология', 'политология', 'экология']
            
            # Проверяем полное вхождение дисциплины
            for discipline in common_disciplines:
                if discipline in text.lower():
                    logger.info(f"Found common discipline in text: {discipline}")
                    return discipline.capitalize()
            
            # Проверяем частичное вхождение (если дисциплина короткая)
            for discipline in common_disciplines:
                if len(discipline) > 5:
                    for word in self.extract_keywords(text.lower()):
                        if len(word) > 5 and (discipline in word or word in discipline):
                            logger.info(f"Found partial discipline match: {discipline} in/from {word}")
                            return discipline.capitalize()
                    
            return None
        except Exception as e:
            logger.error(f"Error finding discipline in text '{text}': {e}")
            return None

    def categorize_query(self, text: str) -> Tuple[str, List[str]]:
        """Определяет категорию запроса и извлекает ключевые слова"""
        try:
            text_lower = text.lower()
            keywords = self.extract_keywords(text_lower)
            logger.info(f"Query text: {text_lower}")
            logger.info(f"Extracted keywords: {keywords}")
            
            # Дисциплины обрабатываются через find_discipline_in_text
            # Временно отключаем поиск по шаблонам
            
            # Дополнительные шаблоны запросов для преподавателей
            teacher_patterns = [
                r"кто такая ([\w]+)",
                r"кто такой ([\w]+)",
                r"преподаватель ([\w]+)",
                r"о преподавателе ([\w]+)",
                r"где найти ([\w]+)",
                r"контакты ([\w]+)"
            ]
            
            # Проверяем наличие шаблонов запросов о преподавателях
            for pattern in teacher_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    teacher_name = match.group(1)
                    logger.info(f"Found teacher name pattern: {teacher_name} via pattern {pattern}")
                    # Добавляем в keywords для дальнейшего анализа
                    keywords.append(teacher_name)
                    
            # Проверяем наличие фамилии преподавателя в запросе
            for word in keywords:
                for name_base, full_name in self.teacher_surnames.items():
                    if name_base in word.lower():
                        logger.info(f"Found teacher name: {full_name} from word {word}")
                        return 'teacher', [full_name]
                        
            # Проверяем наличие явных упоминаний категорий перед проверкой на фамилию
            text_lower = text.lower()
            
            # Проверяем явные запросы о навигации
            if ("где" in text_lower or "как найти" in text_lower or "как пройти" in text_lower or 
                "местоположение" in text_lower or "расположение" in text_lower):
                
                # Библиотека
                if "библиотек" in text_lower:
                    logger.info("Direct mention of library location detected")
                    return 'navigation', ['библиотека']
                    
                # Столовая
                elif "столов" in text_lower or "буфет" in text_lower or "поесть" in text_lower or "еда" in text_lower:
                    logger.info("Direct mention of canteen location detected")
                    return 'navigation', ['столовая']
                
                # VR-лаборатория
                elif "vr" in text_lower or "лаборатор" in text_lower:
                    logger.info("Direct mention of VR lab location detected")
                    return 'navigation', ['лаборатория']
                    
                # Другие места (общий запрос о навигации)
                else:
                    for loc in ["деканат", "учебная часть", "студсовет", "бухгалтерия", 
                               "актовый зал", "спортзал", "медпункт"]:
                        if loc in text_lower:
                            logger.info(f"Direct mention of {loc} location detected")
                            return 'navigation', [loc]
                            
                    logger.info("General navigation query detected")
                    return 'navigation', keywords
            
            # Проверяем, есть ли в запросе явные слова о преподавателях
            if any(word in text_lower for word in ["преподаватель", "учитель", "педагог"]):
                # Теперь ищем преподавателя, который не в нашем справочнике
                for word in keywords:
                    if len(word) > 3 and word.isalpha() and not any(
                        common_word in word.lower() for common_word in 
                        ["где", "как", "что", "когда", "почему", "кто", "находиться", "расположен"]
                    ):
                        logger.info(f"Potential teacher name found: {word}")
                        return 'teacher', [word]
            
            # Если запрос похож на фамилию (как запасной вариант)
            for word in keywords:
                if (len(word) > 3 and word.isalpha() and word[0].isupper() and 
                    not any(common_word in word.lower() for common_word in 
                         ["где", "как", "что", "когда", "почему", "кто", "находиться", "расположен"])):
                    logger.info(f"Potential teacher surname found: {word}")
                    return 'teacher', [word]

            # Ищем дисциплину в тексте
            discipline = self.find_discipline_in_text(text_lower)
            if discipline:
                logger.info(f"Found discipline reference: {discipline}")
                return 'discipline', [discipline]

            # Проверяем наличие явных упоминаний категорий
            if "преподаватели" in text_lower or "о преподавателях" in text_lower or "список преподавателей" in text_lower:
                logger.info("Direct mention of teachers list detected")
                return 'teacher', keywords
                
            if "столовая" in text_lower or "буфет" in text_lower or "поесть" in text_lower:
                logger.info("Direct mention of canteen detected")
                return 'navigation', ['столовая'] + keywords

            # Проверяем пересечение с категориями (по словам)
            for category, category_keywords in self.categories.items():
                if any(keyword in category_keywords for keyword in keywords):
                    logger.info(f"Matched category by keyword: {category} with keywords: {keywords}")
                    return category, keywords
                    
            # Проверяем пересечение с категориями (по частям слов)
            for category, category_keywords in self.categories.items():
                for keyword in keywords:
                    for category_word in category_keywords:
                        if (len(keyword) > 3 and keyword in category_word) or (len(category_word) > 3 and category_word in keyword):
                            logger.info(f"Fuzzy matched category: {category} with keyword {keyword} matching {category_word}")
                            return category, keywords

            logger.info("No specific category matched")
            return 'unknown', keywords
        except Exception as e:
            logger.error(f"Error categorizing query '{text}': {e}")
            return 'unknown', []

    def process_query(self, text: str, db_manager) -> Optional[str]:
        """Обрабатывает запрос и возвращает ответ"""
        try:
            # Проверяем команды
            if text.startswith('/'):
                return None  # Возвращаем None для команд, чтобы их обрабатывал CommandHandler

            category, keywords = self.categorize_query(text)
            logger.info(f"Query category: {category}, keywords: {keywords}")

            if not keywords:
                return "Пожалуйста, сформулируйте вопрос подробнее."

            if category == 'teacher':
                return self._process_teacher_query(db_manager, keywords)
            elif category == 'discipline':
                return self._process_discipline_query(db_manager, keywords)
            elif category == 'sport':
                return self._process_sport_query(db_manager)
            elif category == 'document':
                return self._process_document_query(db_manager)
            elif category == 'navigation':
                return self._process_navigation_query(db_manager, keywords)
            elif category == 'event':
                return self._process_event_query(db_manager)
            elif category == 'dormitory':
                return self._process_dormitory_query(db_manager)
            else:
                return "Извините, я не смог понять ваш вопрос. Попробуйте переформулировать или выберите пункт из меню."
                
        except Exception as e:
            logger.error(f"Error processing query '{text}': {e}")
            return "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."

    def _process_teacher_query(self, db_manager, keywords: List[str]) -> str:
        """Обрабатывает запрос о преподавателе"""
        # Заглушка для поиска преподавателей
        logger.info(f"Teacher query received via NLP (disabled): {keywords}")
        
        return ("👨‍🏫 <b>Поиск преподавателей через текстовые запросы временно недоступен</b>\n\n"
                "Пожалуйста, воспользуйтесь функцией поиска преподавателей через меню 'Преподаватели' -> 'Поиск по фамилии'.\n\n"
                "В текстовом формате доступны запросы о местоположении (столовая, библиотека и т.д.), "
                "документах, мероприятиях и спортивных секциях.")

    def _process_discipline_query(self, db_manager, keywords: List[str]) -> str:
        """Обрабатывает запрос о дисциплине"""
        # Заглушка для поиска по дисциплинам
        logger.info(f"Discipline query received via NLP (disabled): {keywords}")
        
        return ("📚 <b>Поиск по дисциплинам через текстовые запросы временно недоступен</b>\n\n"
                "Пожалуйста, воспользуйтесь меню для просмотра информации о преподавателях и их дисциплинах.\n\n"
                "В текстовом формате доступны запросы о местоположении (столовая, библиотека и т.д.), "
                "документах, мероприятиях и спортивных секциях.")

    def _process_sport_query(self, db_manager) -> str:
        """Обрабатывает запрос о спортивных секциях"""
        sections = db_manager.get_sections()
        if not sections:
            return "К сожалению, информация о спортивных секциях временно недоступна. Рекомендую обратиться на кафедру физической культуры для получения актуальной информации."
            
        response = "🏆 <b>Спортивные секции в колледже</b>\n\n"
        response += "В нашем колледже представлены различные спортивные направления для всестороннего физического развития студентов. Вы можете выбрать любую секцию в соответствии с вашими интересами:\n\n"
        
        for section in sections:
            name = section[1] if len(section) > 1 else "Название секции не указано"
            coach = section[2] if len(section) > 2 else "Не указан"
            location = section[3] if len(section) > 3 else "Не указано"
            schedule = section[4] if len(section) > 4 else "Не указано"
            
            response += f"🎯 <b>{name}</b>\n"
            response += f"👨‍🏫 Тренер: {coach}\n"
            response += f"📍 Место проведения: {location}\n"
            response += f"⏰ Расписание: {schedule}\n\n"
        
        response += "Для записи в секцию обратитесь к тренеру или на кафедру физической культуры. Занятия в секциях помогут вам поддерживать физическую форму и успешно сдавать нормативы."
        
        return response

    def _process_document_query(self, db_manager) -> str:
        """Обрабатывает запрос о документах"""
        docs = db_manager.get_documents()
        if not docs:
            return "К сожалению, информация о документах временно недоступна. Рекомендую обратиться в учебную часть для получения актуальной информации о необходимых документах."
            
        response = "📄 <b>Документы и справки в колледже</b>\n\n"
        response += "В нашем колледже вы можете получить различные документы и справки. Ниже представлен список доступных документов и информация о том, как их получить:\n\n"
        
        for doc in docs:
            name = doc[1] if len(doc) > 1 else "Не указано"
            description = doc[2] if len(doc) > 2 else "Описание отсутствует"
            link = doc[3] if len(doc) > 3 and doc[3] else None
            
            response += f"📑 <b>{name}</b>\n"
            response += f"ℹ️ {description}\n"
            if link:
                response += f"🔗 <a href='{link}'>Скачать бланк/образец</a>\n"
            response += "\n"
            
        response += "<b>Как получить документы:</b>\n"
        response += "• Для получения справок обращайтесь в учебную часть (кабинет 205) в часы работы: пн-пт 9:00-17:00\n"
        response += "• Справки об обучении выдаются в течение 3 рабочих дней после запроса\n"
        response += "• При себе необходимо иметь студенческий билет или паспорт\n"
        response += "• По вопросам оформления документов можно обратиться к своему куратору группы\n"
        
        return response

    def _process_navigation_query(self, db_manager, keywords: List[str]) -> str:
        """Обрабатывает запрос о навигации по колледжу"""
        # Получаем навигационные данные
        places = db_manager.get_navigation()
        if not places or len(places) == 0:
            return "🏢 <b>Навигация по колледжу</b>\n\nИзвините, информация о расположении помещений временно недоступна. Рекомендуем обратиться на ресепшн при входе в здание колледжа для получения подробной информации."
            
        # Определяем, был ли запрос о конкретном месте
        keywords_string = " ".join(keywords).lower()
        
        # Библиотека
        if "библиотека" in keywords_string or "библиотеки" in keywords_string or "книги" in keywords_string:
            return ("📚 <b>Библиотека колледжа</b>\n\n"
                   "Библиотека находится на 3 этаже в кабинете 312. \n\n"
                   "<b>Часы работы:</b> Пн-Пт с 9:00 до 17:00, обед с 12:00 до 13:00\n\n"
                   "<b>Услуги библиотеки:</b>\n"
                   "• Выдача учебной литературы\n"
                   "• Доступ к электронным ресурсам\n"
                   "• Консультационная помощь\n"
                   "• Копирование и сканирование материалов\n\n"
                   "Для получения учебников необходимо предъявить студенческий билет. "
                   "Срок выдачи учебной литературы - один семестр.")
            
        # VR-лаборатория
        elif "vr" in keywords_string or "лаборатория" in keywords_string or "виртуальная реальность" in keywords_string:
            return ("🎮 <b>VR-лаборатория</b>\n\n"
                   "VR-лаборатория расположена на 2 этаже в кабинете 208. \n\n"
                   "<b>Часы работы:</b> По расписанию занятий и во время проведения специальных мероприятий\n\n"
                   "<b>Оборудование:</b>\n"
                   "• VR-шлемы Oculus Quest 2\n"
                   "• Мощные компьютеры для работы с VR\n"
                   "• Интерактивные дисплеи\n\n"
                   "Для посещения лаборатории вне учебного расписания необходимо предварительно записаться у куратора лаборатории.")
            
        # Учебная часть / деканат
        elif "учебная" in keywords_string or "деканат" in keywords_string or "учебный" in keywords_string:
            return ("📝 <b>Учебная часть колледжа</b>\n\n"
                   "Учебная часть расположена на 2 этаже в кабинете 205. \n\n"
                   "<b>Часы работы:</b> Пн-Пт с 9:00 до 17:00, обед с 12:00 до 13:00\n\n"
                   "<b>Вопросы, решаемые в учебной части:</b>\n"
                   "• Расписание занятий\n"
                   "• Выдача справок об обучении\n"
                   "• Оформление академических отпусков\n"
                   "• Выдача зачетных книжек и студенческих билетов\n"
                   "• Консультации по вопросам образовательного процесса\n\n"
                   "При обращении необходимо иметь при себе студенческий билет или зачетную книжку.")
            
        # Столовая / буфет
        elif "столовая" in keywords_string or "буфет" in keywords_string or "поесть" in keywords_string or "еда" in keywords_string:
            return ("🍽️ <b>Столовая и буфет колледжа</b>\n\n"
                   "Столовая находится на 1 этаже. \n\n"
                   "<b>Часы работы:</b>\n"
                   "• Столовая: Пн-Пт с 9:00 до 16:00\n"
                   "• Буфет: Пн-Пт с 8:30 до 17:00\n\n"
                   "<b>Информация о питании:</b>\n"
                   "• Ежедневно предлагается разнообразное меню\n"
                   "• Возможна оплата наличными и банковскими картами\n"
                   "• Для льготных категорий студентов предусмотрено бесплатное питание\n\n"
                   "Для оформления льготного питания необходимо обратиться в социальный отдел колледжа.")
            
        # Студенческий совет
        elif "студенческий" in keywords_string or "совет" in keywords_string or "студсовет" in keywords_string:
            return ("👥 <b>Студенческий совет колледжа</b>\n\n"
                   "Студенческий совет расположен на 2 этаже в кабинете 220. \n\n"
                   "<b>Часы работы:</b> Пн-Пт с 10:00 до 16:00\n\n"
                   "<b>Направления деятельности студсовета:</b>\n"
                   "• Организация студенческих мероприятий\n"
                   "• Поддержка студенческих инициатив\n"
                   "• Защита прав и интересов студентов\n"
                   "• Волонтерство и общественная деятельность\n\n"
                   "Каждый студент может принять участие в работе студенческого совета. Выборы в студсовет проводятся ежегодно в октябре.")
            
        # Бухгалтерия
        elif "бухгалтерия" in keywords_string or "оплата" in keywords_string or "финансы" in keywords_string:
            return ("💰 <b>Бухгалтерия колледжа</b>\n\n"
                   "Бухгалтерия находится на 1 этаже в кабинете 103. \n\n"
                   "<b>Часы работы:</b> Пн-Пт с 9:00 до 16:00, обед с 12:00 до 13:00\n"
                   "<b>Приемные часы для студентов:</b> Вт, Чт с 13:00 до 16:00\n\n"
                   "<b>Вопросы, решаемые в бухгалтерии:</b>\n"
                   "• Оплата обучения\n"
                   "• Выдача квитанций и справок об оплате\n"
                   "• Стипендиальные выплаты\n"
                   "• Материальная помощь\n\n"
                   "Для решения финансовых вопросов необходимо иметь при себе паспорт и студенческий билет.")
            
        # Актовый зал
        elif "актовый" in keywords_string or "зал" in keywords_string:
            return ("🎭 <b>Актовый зал колледжа</b>\n\n"
                   "Актовый зал находится на 2 этаже. \n\n"
                   "<b>Характеристики:</b>\n"
                   "• Вместимость: до 200 человек\n"
                   "• Оборудование: современная аудио и видеосистемы, проектор\n"
                   "• Сцена площадью 40 кв.м\n\n"
                   "<b>Назначение:</b>\n"
                   "• Проведение торжественных мероприятий\n"
                   "• Конференции и семинары\n"
                   "• Концерты и творческие выступления\n"
                   "• Собрания и встречи\n\n"
                   "Для бронирования актового зала необходимо обратиться к заместителю директора по воспитательной работе.")
            
        # Спортзал
        elif "спортзал" in keywords_string or "спортивный" in keywords_string or "физкультура" in keywords_string:
            return ("🏀 <b>Спортивный зал колледжа</b>\n\n"
                   "Спортзал находится на 2 этаже. \n\n"
                   "<b>Часы работы:</b> Пн-Сб с 8:00 до 20:00 по расписанию занятий и секций\n\n"
                   "<b>Инфраструктура:</b>\n"
                   "• Универсальный игровой зал\n"
                   "• Тренажерный зал\n"
                   "• Раздевалки с душевыми\n"
                   "• Спортивный инвентарь\n\n"
                   "<b>Секции и занятия:</b>\n"
                   "• Волейбол, баскетбол, мини-футбол\n"
                   "• Настольный теннис\n"
                   "• Фитнес и общая физическая подготовка\n\n"
                   "Для посещения спортзала вне учебных занятий необходимо записаться у преподавателя физкультуры.")
            
        # Медпункт
        elif "медпункт" in keywords_string or "медицинский" in keywords_string or "врач" in keywords_string:
            return ("🩺 <b>Медицинский пункт колледжа</b>\n\n"
                   "Медпункт находится на 1 этаже в кабинете 106. \n\n"
                   "<b>Часы работы:</b> Пн-Пт с 9:00 до 16:00\n\n"
                   "<b>Услуги медпункта:</b>\n"
                   "• Первая медицинская помощь\n"
                   "• Плановые медицинские осмотры\n"
                   "• Профилактические мероприятия\n"
                   "• Выдача справок по болезни\n\n"
                   "Для получения медицинской помощи необходимо предъявить студенческий билет и полис ОМС. "
                   "В экстренных случаях помощь оказывается всем обратившимся.")
            
        # Общая информация о навигации
        else:
            response = "🏢 <b>Навигация по колледжу</b>\n\n"
            response += "Здание колледжа имеет 3 этажа. Ниже представлена информация о расположении основных помещений:\n\n"
            
            response += "📚 <b>Библиотека</b>: 3 этаж, кабинет 312\n"
            response += "🎮 <b>VR-лаборатория</b>: 2 этаж, кабинет 208\n"
            response += "📝 <b>Учебная часть</b>: 2 этаж, кабинет 205\n"
            response += "🍽️ <b>Столовая</b>: 1 этаж\n"
            response += "👥 <b>Студенческий совет</b>: 2 этаж, кабинет 220\n"
            response += "💰 <b>Бухгалтерия</b>: 1 этаж, кабинет 103\n"
            response += "🎭 <b>Актовый зал</b>: 2 этаж\n"
            response += "🏀 <b>Спортивный зал</b>: 2 этаж\n"
            response += "🩺 <b>Медицинский пункт</b>: 1 этаж, кабинет 106\n\n"
            
            response += "Для более подробной информации о конкретном помещении, спросите например: 'Где находится библиотека?' или 'Как пройти в столовую?'"
            
            return response
            
    def _process_event_query(self, db_manager) -> str:
        """Обрабатывает запрос о мероприятиях"""
        events = db_manager.get_events()
        if not events:
            return "🎉 <b>Мероприятия колледжа</b>\n\nНа данный момент нет запланированных мероприятий. Информация о будущих событиях будет доступна позже. Следите за обновлениями в группе колледжа ВКонтакте и Telegram-канале."
            
        response = "🎉 <b>Ближайшие мероприятия колледжа</b>\n\n"
        response += "В ближайшее время в колледже запланированы следующие мероприятия. Приглашаем всех студентов принять участие!\n\n"
        
        for event in events:
            date = event[1] if len(event) > 1 else "Дата не указана"
            title = event[2] if len(event) > 2 else "Название не указано"
            location = event[3] if len(event) > 3 else "Место не указано"
            
            response += f"📌 <b>{title}</b>\n"
            response += f"📅 Дата и время: {date}\n"
            response += f"📍 Место проведения: {location}\n\n"
        
        response += "<b>Как принять участие:</b>\n"
        response += "• Для участия в большинстве мероприятий требуется предварительная регистрация\n"
        response += "• Записаться можно у организаторов или через студенческий совет\n"
        response += "• Следите за обновлениями в группе колледжа ВКонтакте и Telegram-канале\n"
        
        return response

    def _process_dormitory_query(self, db_manager) -> str:
        """Обрабатывает запрос об общежитиях"""
        dorms = db_manager.get_dormitories()
        if not dorms:
            return "🏠 <b>Общежития колледжа</b>\n\nК сожалению, информация об общежитиях временно недоступна. Рекомендуем обратиться в учебную часть для получения актуальной информации о заселении и условиях проживания."
            
        response = "🏠 <b>Общежития Пермского финансово-экономического колледжа</b>\n\n"
        response += "Студентам колледжа предоставляется возможность проживания в общежитиях. Ниже представлена информация об общежитиях, условиях проживания и правилах заселения:\n\n"
        
        for dorm in dorms:
            number = dorm[1] if len(dorm) > 1 else "Номер не указан"
            warden = dorm[2] if len(dorm) > 2 else "Не указан"
            address = dorm[3] if len(dorm) > 3 else "Не указан"
            phone = dorm[4] if len(dorm) > 4 else "Не указан"
            
            response += f"🏢 <b>Общежитие №{number}</b>\n"
            response += f"📍 Адрес: {address}\n"
            response += f"👤 Комендант: {warden}\n"
            response += f"📞 Контактный телефон: {phone}\n\n"
        
        response += "<b>Правила заселения в общежитие:</b>\n"
        response += "• Заселение происходит на основании приказа о зачислении\n"
        response += "• Необходимо предоставить паспорт, медицинскую справку и фотографии\n"
        response += "• Заселение проводится в конце августа перед началом учебного года\n"
        response += "• Стоимость проживания и подробности можно уточнить в учебной части\n\n"
        
        response += "Для получения дополнительной информации обращайтесь в учебную часть колледжа."
        
        return response
