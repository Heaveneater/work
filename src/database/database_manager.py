import sqlite3
from typing import List, Tuple, Optional, Dict, Any
import os
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Класс для управления подключением к базе данных и выполнения запросов"""

    def __init__(self, db_path: str):
        """Инициализация менеджера базы данных"""
        self.db_path = db_path
        self._query_cache: Dict[str, Tuple[List[Tuple], float]] = {}  # кэш для запросов
        self.cache_timeout = 300  # 5 минут
        self.init_database()

    def init_database(self):
        """Инициализирует подключение к базе данных и создает таблицы, если они не существуют"""
        try:
            db_exists = os.path.exists(self.db_path)

            # Подключаемся к базе данных (создаст файл, если его нет)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Если база данных не существовала, инициализируем ее
            if not db_exists:
                logger.info(f"Database file not found, initializing from SQL script")
                sql_script_path = 'database.db.sql'
                if not os.path.exists(sql_script_path):
                    raise FileNotFoundError(f"SQL script not found at {sql_script_path}")

                with open(sql_script_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()

                cursor.executescript(sql_script)
                conn.commit()
                logger.info("Database initialized with sample data")
            else:
                logger.info(f"Using existing database at {self.db_path}")

                # Проверяем, есть ли основные таблицы, и если нет - создаем их
                tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
                table_names = [table[0] for table in tables]

                if 'Prepodavately' not in table_names:
                    logger.info("Creating missing tables in existing database")
                    sql_script_path = 'database.db.sql'
                    with open(sql_script_path, 'r', encoding='utf-8') as f:
                        sql_script = f.read().split(';')

                    # Выполняем только CREATE TABLE запросы без INSERT
                    for query in sql_script:
                        if query.strip().upper().startswith('CREATE TABLE'):
                            cursor.execute(query)

                    conn.commit()
                    logger.info("Missing tables created")

            conn.close()
            logger.info("Database connection initialized successfully")

            # Verify tables exist
            tables = self.execute_query("SELECT name FROM sqlite_master WHERE type='table';")
            logger.info(f"Available tables: {[table[0] for table in tables]}")

        except sqlite3.Error as e:
            logger.error(f"SQLite error during initialization: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during database initialization: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """Получает подключение к базе данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            return conn
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def execute_query(self, query: str, params: tuple = (), use_cache: bool = True) -> List[Tuple]:
        """Выполняет запрос к базе данных и возвращает результаты"""
        # Кэширование только для SELECT-запросов без параметров
        cache_key = None
        if use_cache and query.strip().upper().startswith("SELECT") and not params:
            cache_key = query

            # Проверяем наличие флага принудительного обновления
            cache_invalidated = False
            try:
                if os.path.exists('cache_invalidated'):
                    with open('cache_invalidated', 'r') as f:
                        invalidation_time = int(f.read().strip())
                        if time.time() - invalidation_time < 60:  # Если файл создан менее 60 секунд назад
                            cache_invalidated = True
                            logger.info(f"Принудительное обновление кэша для запроса: {query}")
            except Exception as e:
                logger.error(f"Ошибка при проверке флага обновления кэша: {e}")

            # Проверяем кэш только если нет флага принудительного обновления
            if not cache_invalidated and cache_key in self._query_cache:
                cached_result, timestamp = self._query_cache[cache_key]
                if time.time() - timestamp < self.cache_timeout:
                    logger.debug(f"Using cached result for query: {query}")
                    return cached_result

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            conn.close()

            # Сохраняем результат в кэш
            if cache_key is not None:
                self._query_cache[cache_key] = (result, time.time())

            return result
        except sqlite3.Error as e:
            logger.error(f"Database error executing query '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"General error executing query '{query}': {e}")
            return []

    def clear_cache(self):
        """Очищает кэш запросов"""
        self._query_cache.clear()
        logger.info("Query cache cleared")

    def get_teachers(self, search_term: Optional[str] = None) -> List[Tuple]:
        """Получает информацию о преподавателях, при необходимости фильтруя по поисковому запросу"""
        try:
            if search_term:
                # Очищаем поисковый запрос от лишних символов и переводим в нижний регистр
                search_term = search_term.strip().lower()
                
                # Ищем преподавателей по фамилии
                query = """
                    SELECT 
                        id,
                        Фамилия,
                        "Имя ",
                        Отчество,
                        Должность,
                        Кабинет,
                        Фото
                    FROM Prepodavately 
                    WHERE instr(lower(Фамилия), ?) > 0 
                    ORDER BY Фамилия
                """
                result = self.execute_query(query, (search_term,), use_cache=False)
                
                # Если результаты не найдены и длина строки > 1, удаляем первую букву и ищем снова
                if len(result) == 0 and len(search_term) > 1:
                    search_term_without_first = search_term[1:]
                    logger.info(f"Поиск не дал результатов, пробуем поиск без первой буквы: '{search_term_without_first}'")
                    
                    result = self.execute_query(query, (search_term_without_first,), use_cache=False)
                
                # Отладочный вывод
                logger.info(f"Поиск преподавателей '{search_term}' вернул {len(result)} результатов")
                if len(result) > 0:
                    for r in result[:3]:  # Показываем первые 3 результата для отладки
                        logger.info(f"Найден преподаватель: id={r[0]}, фамилия={r[1]}")
                
                return result
            else:
                # Возвращаем всех преподавателей, отсортированных по фамилии
                result = self.execute_query("SELECT * FROM Prepodavately ORDER BY Фамилия ASC")
                logger.info(f"Получены все преподаватели: {len(result)} записей")
                
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении списка преподавателей: {e}")
            return []
            
    def get_teacher_disciplines(self, teacher_id: int) -> List[str]:
        """Получает список дисциплин преподавателя по его ID"""
        try:
            query = """
                SELECT d.name
                FROM disciplines d
                JOIN Prepodavately_disciplines pd ON d.id = pd.discipline_id
                WHERE pd.Prepodavately_id = ?
                ORDER BY d.name
            """
            result = self.execute_query(query, (teacher_id,), use_cache=False)
            
            # Извлекаем названия дисциплин из результата запроса
            disciplines = [row[0] for row in result]
            logger.info(f"Получено {len(disciplines)} дисциплин для преподавателя {teacher_id}")
            
            return disciplines
        except Exception as e:
            logger.error(f"Ошибка при получении дисциплин преподавателя: {e}")
            return []
            
    def get_disciplines(self) -> List[Tuple]:
        """Получает список всех дисциплин"""
        try:
            result = self.execute_query("SELECT * FROM disciplines ORDER BY name")
            logger.info(f"Получено {len(result)} дисциплин")
            return result
        except Exception as e:
            logger.error(f"Ошибка при получении списка дисциплин: {e}")
            return []

    def get_sections(self) -> List[Tuple]:
        """Получает информацию о спортивных секциях"""
        try:
            result = self.execute_query("SELECT * FROM sport")
            logger.info(f"Retrieved {len(result)} sections")
            return result
        except Exception as e:
            logger.error(f"Error getting sections: {e}")
            return []

    def get_dormitories(self) -> List[Tuple]:
        """Получает информацию об общежитиях"""
        try:
            result = self.execute_query("SELECT * FROM obshejitie")
            logger.info(f"Retrieved {len(result)} dormitories")
            return result
        except Exception as e:
            logger.error(f"Error getting dormitories: {e}")
            return []

    def get_events(self) -> List[Tuple]:
        """Получает информацию о предстоящих мероприятиях"""
        try:
            result = self.execute_query("SELECT * FROM Meropryitiay")
            logger.info(f"Retrieved {len(result)} events")
            return result
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []

    def get_documents(self) -> List[Tuple]:
        """Получает информацию о документах"""
        try:
            result = self.execute_query("SELECT * FROM document")
            logger.info(f"Retrieved {len(result)} documents")
            return result
        except Exception as e:
            logger.error(f"Error getting documents: {e}")
            return []

    def get_navigation(self, location: Optional[str] = None) -> List[Tuple]:
        """Получает информацию о навигации по колледжу"""
        try:
            if location:
                query = """
                    SELECT * FROM navigate 
                    WHERE lower(Библиотека) LIKE lower(?) OR lower(VR) LIKE lower(?) 
                    OR lower([Учебная часть]) LIKE lower(?) OR lower(Столовая) LIKE lower(?) 
                    OR lower([Студенческий совет]) LIKE lower(?) OR lower(Бухгалтерия) LIKE lower(?)
                """
                search_pattern = f"%{location}%"
                result = self.execute_query(query, (search_pattern,) * 6, use_cache=False)
            else:
                result = self.execute_query("SELECT * FROM navigate")

            logger.info(f"Retrieved {len(result)} navigation entries")
            return result
        except Exception as e:
            logger.error(f"Error getting navigation: {e}")
            return []

    def get_auditorium(self, room_number: Optional[str] = None) -> List[Tuple]:
        """Получает информацию об аудиториях"""
        try:
            if room_number:
                result = self.execute_query("SELECT * FROM auditoria WHERE Номер = ?", (room_number,), use_cache=False)
            else:
                result = self.execute_query("SELECT * FROM auditoria")

            logger.info(f"Retrieved {len(result)} auditoriums")
            return result
        except Exception as e:
            logger.error(f"Error getting auditoriums: {e}")
            return []

    def get_faq(self) -> List[Tuple]:
        """Получает информацию о часто задаваемых вопросах"""
        try:
            result = self.execute_query("SELECT * FROM faq")
            logger.info(f"Retrieved {len(result)} FAQ entries")
            return result
        except Exception as e:
            logger.error(f"Error getting FAQ: {e}")
            return []