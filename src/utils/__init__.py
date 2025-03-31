import re
import logging

logger = logging.getLogger(__name__)

def format_teacher_disciplines(disciplines_list) -> str:
    """
    Форматирует список дисциплин преподавателя для лучшей читаемости.
    Args:
        disciplines_list: Список или строка с дисциплинами (может быть List, str или bytes)
    Returns:
        Отформатированная строка с дисциплинами
    """
    import logging
    import re
    logger = logging.getLogger(__name__)
    
    try:
        # Проверка на пустое значение
        if not disciplines_list:
            return "Дисциплины не указаны"
        
        # Если передан список строк (новый формат из таблицы disciplines)
        if isinstance(disciplines_list, list):
            formatted_disciplines = []
            for disc in disciplines_list:
                if disc and isinstance(disc, str):
                    disc = disc.strip()
                    if disc:
                        # Улучшаем форматирование (первую букву делаем заглавной)
                        if disc[0].islower():
                            disc = disc[0].upper() + disc[1:]
                        # Добавляем маркер списка
                        formatted_disciplines.append(f"• {disc}")
            
            if not formatted_disciplines:
                return "Дисциплины не указаны"
            
            return "\n".join(formatted_disciplines)
            
        # Для обратной совместимости со старым форматом (строка)
        disciplines_str = disciplines_list
        
        # Если disciplines_str это bytes, декодируем в строку
        if isinstance(disciplines_str, bytes):
            # Пробуем декодировать с разными кодировками
            for encoding in ['utf-8', 'windows-1251', 'latin1', 'cp1251']:
                try:
                    disciplines_str = disciplines_str.decode(encoding)
                    # Если декодирование успешно, выходим из цикла
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Если ни одна кодировка не подошла, используем замену символов
                try:
                    disciplines_str = disciplines_str.decode('utf-8', errors='replace')
                except:
                    logger.error(f"Не удалось декодировать дисциплины: {disciplines_str[:50]}... (показаны первые 50 байт)")
                    # Попробуем использовать грубую силу, просто декодируя каждый байт в строку
                    try:
                        disciplines_str = ''.join(chr(b) for b in disciplines_str if b < 128)
                    except:
                        return "Дисциплины недоступны (ошибка декодирования)"
        
        # Проверяем, что теперь у нас строка
        if not isinstance(disciplines_str, str):
            return str(disciplines_str)
        
        # Очищаем строку от странных символов, оставляем только буквы, цифры и знаки пунктуации
        disciplines_str = re.sub(r'[^\w\s\.,;:-]', ' ', disciplines_str, flags=re.UNICODE)
        # Удаляем лишние пробелы
        disciplines_str = re.sub(r'\s+', ' ', disciplines_str).strip()
        
        # Если после очистки ничего не осталось
        if not disciplines_str:
            return "Дисциплины не указаны"
            
        # Сначала проверяем, есть ли разделители в строке
        if any(sep in disciplines_str for sep in [',', ';', '.', '\n']):
            # Разделяем по запятым, точкам с запятой, точкам или новым строкам
            raw_disciplines = re.split(r'[,;.\n]', disciplines_str)
        else:
            # Если нет разделителей, считаем всю строку одной дисциплиной
            raw_disciplines = [disciplines_str]
        
        # Форматируем каждую дисциплину
        formatted_disciplines = []
        for disc in raw_disciplines:
            disc = disc.strip()
            if disc:
                # Улучшаем форматирование
                # Первую букву делаем заглавной, если она строчная
                if disc and disc[0].islower():
                    disc = disc[0].upper() + disc[1:]
                # Добавляем маркер списка
                formatted_disciplines.append(f"• {disc}")
        
        # Если после форматирования ничего не осталось
        if not formatted_disciplines:
            return "Дисциплины не указаны"
            
        return "\n".join(formatted_disciplines)
        
    except Exception as e:
        logger.error(f"Error formatting disciplines: {e}")
        if isinstance(disciplines_list, (list, tuple)):
            return "\n".join([f"• {d}" for d in disciplines_list if d])
        return str(disciplines_list)

def sanitize_input(text: str) -> str:
    """
    Очищает пользовательский ввод от потенциально опасных символов.
    
    Args:
        text: Исходный текст
        
    Returns:
        Очищенный текст
    """
    if not text:
        return ""
    
    # Удаляем управляющие символы
    sanitized = re.sub(r'[\x00-\x1F\x7F]', '', text)
    
    # Ограничиваем длину текста
    if len(sanitized) > 2000:
        sanitized = sanitized[:2000]
        
    return sanitized

def split_long_message(message: str, max_length: int = 4000) -> list:
    """
    Разбивает длинное сообщение на части для отправки через Telegram API.
    
    Args:
        message: Исходное сообщение
        max_length: Максимальная длина части
        
    Returns:
        Список частей сообщения
    """
    if len(message) <= max_length:
        return [message]
        
    parts = []
    current_part = ""
    
    for line in message.split('\n'):
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line
        else:
            if current_part:
                current_part += '\n' + line
            else:
                current_part = line
                
    if current_part:
        parts.append(current_part)        

    return parts