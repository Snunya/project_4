#!/usr/bin/env python3
import re
import sys
import argparse
import yaml
from typing import Dict, Any, List, Union


class ConfigParser:
    def __init__(self):
        self.constants: Dict[str, Any] = {}
        self.output_data: Dict[str, Any] = {}

    def remove_comments(self, text: str) -> str:
        """Удаляет однострочные и многострочные комментарии"""
        # Удаляем однострочные комментарии (начинаются с C и пробела)
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            # Удаляем комментарий C
            if 'C ' in line:
                line = line.split('C ')[0]
            cleaned_lines.append(line.strip())

        text = '\n'.join(cleaned_lines)

        # Удаляем многострочные комментарии --[[ ... ]]
        while '--[[' in text:
            start = text.find('--[[')
            end = text.find(']]', start)
            if end == -1:
                break
            text = text[:start] + text[end + 2:]

        return text

    def parse_number(self, token: str) -> Union[int, float]:
        """Парсит числа"""
        try:
            if '.' in token:
                return float(token)
            return int(token)
        except ValueError:
            raise SyntaxError(f"Некорректное число: {token}")

    def parse_array(self, text: str) -> List[Any]:
        """Парсит массивы array(...)"""
        # Убираем 'array(' и ')'
        content = text[6:-1].strip()
        if not content:
            return []

        # Разбиваем содержимое массива на элементы
        tokens = []
        current = ""
        depth = 0  # глубина вложенных скобок

        for char in content:
            if char == '(' or char == '{' or char == '[':
                depth += 1
                current += char
            elif char == ')' or char == '}' or char == ']':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                if current.strip():
                    tokens.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            tokens.append(current.strip())

        # Парсим каждый элемент
        result = []
        for token in tokens:
            result.append(self.parse_value(token))

        return result

    def parse_value(self, token: str) -> Any:
        """Парсит значения (числа, массивы, константы, строки, булевы)"""
        token = token.strip()

        if not token:
            raise SyntaxError("Пустое значение")

        # Проверка на константу
        if token.startswith('{') and token.endswith('}'):
            const_name = token[1:-1].strip()
            if const_name in self.constants:
                return self.constants[const_name]
            else:
                raise SyntaxError(f"Неизвестная константа: {const_name}")

        # Проверка на массив
        if token.startswith('array(') and token.endswith(')'):
            return self.parse_array(token)

        # Проверка на число
        if re.match(r'^[+-]?\d+(\.\d+)?$', token):
            return self.parse_number(token)

        # Проверка на строку в кавычках
        if len(token) >= 2 and ((token.startswith('"') and token.endswith('"')) or
                                (token.startswith("'") and token.endswith("'"))):
            return token[1:-1]

        # Проверка на булевы значения
        if token.lower() == 'true':
            return True
        if token.lower() == 'false':
            return False

        # ВСЕ ЧТО ВЫГЛЯДИТ КАК ИМЯ (буква + буквы/цифры/подчёркивания) - ЭТО СТРОКА
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', token):
            return token

        raise SyntaxError(f"Некорректное значение: {token}")

    def process_definitions(self, text: str) -> str:
        """Обрабатывает объявления констант и удаляет их из текста"""
        lines = text.split('\n')
        result_lines = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Ищем определение константы
            def_match = re.search(r'\(def\s+([a-z][a-z0-9_]*)\s+(.*?)\);', line)
            if def_match:
                const_name = def_match.group(1)
                const_value = def_match.group(2).strip()

                try:
                    self.constants[const_name] = self.parse_value(const_value)
                except Exception as e:
                    raise SyntaxError(f"Ошибка в определении константы {const_name}: {e}")

                # Удаляем это определение из строки
                line = re.sub(r'\(def\s+[a-z][a-z0-9_]*\s+.*?\);', '', line)

                # Проверяем, есть ли в строке еще что-то кроме пробелов
                if line.strip():
                    result_lines.append(line.strip())
            else:
                # Если это не определение
                result_lines.append(line)

            i += 1

        return '\n'.join(result_lines)

    def parse_assignment(self, line: str) -> tuple[str, Any]:
        """Парсит присваивание вида 'имя = значение;'"""
        # Удаляем точку с запятой в конце если есть
        line = line.rstrip(';').strip()

        if '=' not in line:
            raise SyntaxError(f"Отсутствует '=' в присваивании: {line}")

        parts = line.split('=', 1)
        name = parts[0].strip()
        value_str = parts[1].strip()

        # Проверяем имя переменной
        if not re.match(r'^[a-z][a-z0-9_]*$', name):
            raise SyntaxError(f"Некорректное имя переменной: {name}")

        value = self.parse_value(value_str)

        return name, value

    def split_statements(self, text: str) -> List[str]:
        """Разбивает текст на отдельные операторы (по ;)"""
        statements = []
        current = ""
        depth = 0  # для учета скобок

        for char in text:
            if char == '(' or char == '{' or char == '[':
                depth += 1
            elif char == ')' or char == '}' or char == ']':
                depth -= 1

            current += char

            if char == ';' and depth == 0:
                statements.append(current.strip())
                current = ""

        # Добавляем остаток, если он есть
        if current.strip():
            statements.append(current.strip())

        return statements

    def parse(self, text: str) -> Dict[str, Any]:
        """Основной метод парсинга"""
        self.constants = {}
        self.output_data = {}

        # 1. Удаляем комментарии
        text = self.remove_comments(text)

        # 2. Обрабатываем определения констант
        text = self.process_definitions(text)

        # 3. Разбиваем на отдельные операторы
        statements = self.split_statements(text)

        # 4. Обрабатываем каждый оператор
        for statement in statements:
            if not statement or statement == ';':
                continue

            try:
                name, value = self.parse_assignment(statement)
                self.output_data[name] = value
            except SyntaxError as e:
                raise SyntaxError(f"Ошибка в выражении '{statement}': {e}")
            except Exception as e:
                raise SyntaxError(f"Неожиданная ошибка в '{statement}': {e}")

        return self.output_data


def main():
    parser = argparse.ArgumentParser(description='Конвертер учебного конфигурационного языка в YAML')
    parser.add_argument('-i', '--input', required=True, help='Входной файл')
    parser.add_argument('-o', '--output', help='Выходной файл YAML (если не указан, вывод в консоль)')

    args = parser.parse_args()

    try:
        # Функция для чтения файла с разными кодировками
        def read_file_with_encoding(file_path):
            encodings = ['utf-8-sig', 'cp1251', 'utf-8']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise UnicodeDecodeError(f"Не удалось декодировать файл {file_path}")

        input_text = read_file_with_encoding(args.input)

        config_parser = ConfigParser()
        result = config_parser.parse(input_text)

        if args.output:
            # Сохраняем в файл
            with open(args.output, 'w', encoding='utf-8') as f:
                yaml.dump(result, f, allow_unicode=True, default_flow_style=False)

            print(f"Успешно преобразовано {args.input} -> {args.output}")
        else:
            # Выводим в консоль
            print(yaml.dump(result, allow_unicode=True, default_flow_style=False))

    except FileNotFoundError:
        print(f"Ошибка: Файл {args.input} не найден")
        sys.exit(1)
    except SyntaxError as e:
        print(f"Синтаксическая ошибка: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
