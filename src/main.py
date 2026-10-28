"""Модуль конфигурации CLI-приложения для анализа графа зависимостей."""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

VALID_SCHEMES = ("http", "https")
TRUE_VALUES = ("true", "1", "yes")
FALSE_VALUES = ("false", "0", "no")
REQUIRED_EXTENSION = ".png"
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
EXIT_ERROR_CODE = 1


class ConfigError(ValueError):
    """Исключение, выбрасываемое при ошибке валидации конфигурации."""


@dataclass
class AppConfig:
    """Структура хранения настраиваемых параметров приложения."""

    package_name: str
    repo_source: str
    test_mode: bool
    package_version: str
    output_image: str
    ascii_tree: bool
    filter_substring: str

    def format_key_value(self) -> str:
        """Форматирует все параметры в виде строк ключ-значение."""
        lines = [
            f"package_name={self.package_name}",
            f"repo_source={self.repo_source}",
            f"test_mode={self.test_mode}",
            f"package_version={self.package_version}",
            f"output_image={self.output_image}",
            f"ascii_tree={self.ascii_tree}",
            f"filter_substring={self.filter_substring}",
        ]
        return "\n".join(lines)


def parse_bool_param(raw_value: str, param_name: str) -> bool:
    """Преобразует строковое представление булева параметра в bool."""
    normalized = raw_value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    msg = (
        f"Некорректное значение параметра '{param_name}': '{raw_value}'. "
        f"Ожидается true или false."
    )
    raise ConfigError(msg)


def validate_package_name(package_name: str) -> str:
    """Проверяет корректность имени анализируемого пакета."""
    cleaned = package_name.strip()
    if not cleaned:
        raise ConfigError("Имя пакета (--package) не может быть пустым.")
    if any(ch.isspace() for ch in cleaned):
        raise ConfigError(
            "Имя пакета (--package) не должно содержать пробелов."
        )
    return cleaned


def validate_repo_source(repo_source: str, test_mode: bool) -> str:
    """Проверяет URL репозитория или путь к файлу тестового репозитория."""
    cleaned = repo_source.strip()
    if not cleaned:
        raise ConfigError(
            "Источник репозитория (--repo) не может быть пустым."
        )
    if test_mode:
        if not os.path.isfile(cleaned):
            raise ConfigError(
                f"Файл тестового репозитория не найден: '{cleaned}'."
            )
        return cleaned
    parsed = urlparse(cleaned)
    if parsed.scheme not in VALID_SCHEMES or not parsed.netloc:
        raise ConfigError(
            f"Некорректный URL репозитория: '{cleaned}'. "
            f"Ожидается http:// или https://."
        )
    return cleaned


def validate_version(version: str) -> str:
    """Проверяет корректность формата версии пакета."""
    cleaned = version.strip()
    if not cleaned:
        raise ConfigError("Версия пакета (--version) не может быть пустой.")
    if not VERSION_PATTERN.match(cleaned):
        raise ConfigError(
            f"Некорректный формат версии пакета: '{cleaned}'."
        )
    return cleaned


def validate_output_image(output_image: str) -> str:
    """Проверяет корректность имени выходного файла изображения графа."""
    cleaned = output_image.strip()
    if not cleaned:
        raise ConfigError(
            "Имя выходного файла (--output) не может быть пустым."
        )
    lower_name = cleaned.lower()
    if not lower_name.endswith(REQUIRED_EXTENSION):
        raise ConfigError(
            f"Файл изображения (--output) должен иметь расширение "
            f"'{REQUIRED_EXTENSION}'."
        )
    stem = cleaned[: -len(REQUIRED_EXTENSION)].strip()
    if not stem:
        raise ConfigError("Не указано имя файла перед расширением .png.")
    return cleaned


def validate_filter_substring(filter_substring: str) -> str:
    """Проверяет корректность подстроки для фильтрации пакетов."""
    if any(ch.isspace() for ch in filter_substring):
        raise ConfigError(
            "Подстрока фильтрации (--filter) не должна содержать пробелов."
        )
    return filter_substring


def create_argument_parser() -> argparse.ArgumentParser:
    """Создает и настраивает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Инструмент визуализации графа зависимостей пакетов."
    )
    parser.add_argument(
        "-p", "--package", required=True, help="Имя анализируемого пакета."
    )
    parser.add_argument(
        "-r", "--repo", required=True, help="URL репозитория или путь к файлу."
    )
    parser.add_argument(
        "-t",
        "--test-mode",
        nargs="?",
        const="true",
        default="false",
        help="Режим тестового репозитория (true/false).",
    )
    parser.add_argument(
        "-v", "--version", required=True, help="Версия анализируемого пакета."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="graph.png",
        help="Имя сгенерированного PNG-файла с графом.",
    )
    parser.add_argument(
        "-a",
        "--ascii-tree",
        nargs="?",
        const="true",
        default="false",
        help="Режим вывода в формате ASCII-дерева (true/false).",
    )
    parser.add_argument(
        "-f",
        "--filter",
        default="",
        help="Подстрока для фильтрации пакетов.",
    )
    return parser


def build_config(argv: list[str] | None = None) -> AppConfig:
    """Парсит аргументы CLI и возвращает проверенную конфигурацию."""
    parser = create_argument_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        raise ConfigError(
            "Ошибка разбора обязательных аргументов командной строки."
        ) from exc

    test_mode = parse_bool_param(str(args.test_mode), "--test-mode")
    ascii_tree = parse_bool_param(str(args.ascii_tree), "--ascii-tree")

    return AppConfig(
        package_name=validate_package_name(args.package),
        repo_source=validate_repo_source(args.repo, test_mode),
        test_mode=test_mode,
        package_version=validate_version(args.version),
        output_image=validate_output_image(args.output),
        ascii_tree=ascii_tree,
        filter_substring=validate_filter_substring(args.filter),
    )


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI-приложения."""
    try:
        config = build_config(argv)
    except ConfigError as err:
        print(f"Ошибка конфигурации: {err}", file=sys.stderr)
        return EXIT_ERROR_CODE

    print(config.format_key_value())
    return 0


if __name__ == "__main__":
    sys.exit(main())