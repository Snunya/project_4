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
        """Удаляет однострочные и многострочные комментарии, объединяет перенесенные строки"""
        # Удаляем однострочные комментарии
        text = re.sub(r'C .*$', '', text, flags=re.MULTILINE)

        # Удаляем многострочные комментарии
        text = re.sub(r'--\[\[.*?\]\]', '', text, flags=re.DOTALL)

        # Объединяем строки, которые заканчиваются на запятую или открывающую скобку
        lines = text.split('\n')
        result_lines = []
        i = 0

        while i < len(lines):
            line = lines[i].rstrip()
            # Если строка заканчивается запятой, открывающей скобкой, ИЛИ начинается с продолжения
            if line.endswith(',') or line.endswith('(') or line.endswith('[') or \
                    line.startswith('    ') or line.startswith('\t'):  # продолжение с отступом
                combined = line
                i += 1
                while i < len(lines):
                    next_line = lines[i].rstrip()
                    combined += ' ' + next_line
                    # Проверяем есть ли закрывающая скобка
                    if ')' in next_line or ']' in next_line:
                        break
                    i += 1
                result_lines.append(combined)
            else:
                result_lines.append(line)
                i += 1

        return '\n'.join(result_lines)

    def parse_number(self, token: str) -> Union[int, float]:
        """Парсит числа"""
        if '.' in token:
            return float(token)
        return int(token)

    def parse_array(self, text: str) -> List[Any]:
        """Парсит массивы array(...)"""
        content = text[6:-1].strip()  # Убираем 'array(' и ')'
        if not content:
            return []

        tokens = self.tokenize_array_content(content)
        return [self.parse_value(token.strip()) for token in tokens]

    def tokenize_array_content(self, content: str) -> List[str]:
        """Разбивает содержимое массива на токены с учетом вложенности"""
        tokens = []
        current_token = ""
        brace_count = 0
        parenthesis_count = 0

        for char in content:
            if char == ',' and brace_count == 0 and parenthesis_count == 0:
                if current_token.strip():
                    tokens.append(current_token.strip())
                current_token = ""
            else:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '(':
                    parenthesis_count += 1
                elif char == ')':
                    parenthesis_count -= 1
                current_token += char

        if current_token.strip():
            tokens.append(current_token.strip())

        return tokens

    def parse_value(self, token: str) -> Any:
        """Парсит значения (числа, массивы, константы, строки, булевы)"""
        token = token.strip()

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
        if re.match(r'^[+-]?([1-9][0-9]*|0)(\.[0-9]+)?$', token):
            return self.parse_number(token)

        # Проверка на строку (в кавычках)
        if (token.startswith('"') and token.endswith('"')) or \
                (token.startswith("'") and token.endswith("'")):
            # Убираем кавычки
            return token[1:-1]

        # Проверка на булевые значения
        if token.lower() == 'true':
            return True
        if token.lower() == 'false':
            return False

        # Если это имя, но не константа - это ошибка
        if re.match(r'^[a-z][a-z0-9_]*$', token):
            raise SyntaxError(f"Неизвестный идентификатор: {token}")

        raise SyntaxError(f"Некорректное значение: {token}")

    def process_definitions(self, text: str) -> str:
        """Обрабатывает объявления констант и удаляет их из текста"""
        lines = text.split('\n')
        result_lines = []

        for line in lines:
            def_match = re.match(r'^\s*\(def\s+([a-z][a-z0-9_]*)\s+(.*?)\);\s*$', line)
            if def_match:
                const_name = def_match.group(1)
                const_value = def_match.group(2)
                try:
                    self.constants[const_name] = self.parse_value(const_value)
                except Exception as e:
                    raise SyntaxError(f"Ошибка в определении константы {const_name}: {e}")
            else:
                result_lines.append(line)

        return '\n'.join(result_lines)

    def parse_assignment(self, line: str) -> tuple[str, Any]:
        """Парсит присваивание вида 'имя = значение;'"""
        match = re.match(r'^\s*([a-z][a-z0-9_]*)\s*=\s*(.*?);\s*$', line)
        if not match:
            raise SyntaxError(f"Некорректное присваивание: {line}")

        name = match.group(1)
        value_str = match.group(2)
        value = self.parse_value(value_str)

        return name, value

    def parse(self, text: str) -> Dict[str, Any]:
        """Основной метод парсинга"""
        self.constants = {}
        self.output_data = {}

        text = self.remove_comments(text)

        text = self.process_definitions(text)

        for line in text.split('\n'):
            line = line.strip()
            if line and not line.startswith('C ') and not line.startswith('--'):
                try:
                    name, value = self.parse_assignment(line)
                    self.output_data[name] = value
                except SyntaxError as e:
                    raise SyntaxError(f"Ошибка в строке '{line}': {e}")

        return self.output_data


def main():
    parser = argparse.ArgumentParser(description='Конвертер учебного конфигурационного языка в YAML')
    parser.add_argument('-i', '--input', required=True, help='Входной файл')
    parser.add_argument('-o', '--output', help='Выходной файл YAML (если не указан, вывод в консоль)')

    args = parser.parse_args()

    try:
        # Функция для чтения файла с разными кодировками
        def read_file_with_encoding(file_path):
            # Сначала пробуем utf-8-sig (с поддержкой BOM)
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    return f.read()
            except UnicodeDecodeError:
                # Пробуем cp1251 (Windows кириллица)
                try:
                    with open(file_path, 'r', encoding='cp1251') as f:
                        return f.read()
                except UnicodeDecodeError:
                    # Пробуем utf-8 (обычный)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return f.read()

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
