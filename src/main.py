"""Модуль CLI-приложения для сбора прямых зависимостей пакетов Maven."""

import argparse
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urlparse

VALID_SCHEMES = ("http", "https")
TRUE_VALUES = ("true", "1", "yes")
FALSE_VALUES = ("false", "0", "no")
REQUIRED_EXTENSION = ".png"
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
COORD_PARTS_COUNT = 2
HTTP_TIMEOUT_SECONDS = 10
EXIT_SUCCESS = 0
EXIT_ERROR_CODE = 1


class ConfigError(ValueError):
    """Исключение при ошибке конфигурации или загрузки зависимостей."""


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
    return cleaned.rstrip("/")


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
    if not cleaned.lower().endswith(REQUIRED_EXTENSION):
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
        description="Инструмент визуализации графа зависимостей пакетов." )
    parser.add_argument(
        "-p", "--package", required=True, 
        help="Имя пакета (groupId:artifactId)." )
    parser.add_argument(
        "-r", "--repo", required=True, 
        help="URL репозитория или путь к файлу."  )
    parser.add_argument(
        "-t",
        "--test-mode",
        nargs="?",
        const="true",
        default="false",
        help="Режим тестового репозитория (true/false).", )
    parser.add_argument(
        "-v", "--version", required=True, help="Версия анализируемого пакета." )
    parser.add_argument(
        "-o",
        "--output",
        default="graph.png",
        help="Имя сгенерированного PNG-файла с графом.",  )
    parser.add_argument(
        "-a",
        "--ascii-tree",
        nargs="?",
        const="true",
        default="false",
        help="Режим вывода в формате ASCII-дерева (true/false).",  )
    parser.add_argument(
        "-f", "--filter", default="", help="Подстрока для фильтрации пакетов." )
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


def build_pom_url(repo_url: str, package_name: str, version: str) -> str:
    """Формирует URL-адрес POM-файла пакета в репозитории Maven."""
    parts = package_name.split(":")
    if len(parts) != COORD_PARTS_COUNT or not all(parts):
        raise ConfigError(
            f"Для Maven имя пакета должно иметь формат "
            f"'groupId:artifactId', получено: '{package_name}'."
        )
    group_id, artifact_id = parts
    group_path = group_id.replace(".", "/")
    base_url = repo_url.rstrip("/")
    return (
        f"{base_url}/{group_path}/{artifact_id}/"
        f"{version}/{artifact_id}-{version}.pom"
    )


def fetch_pom_xml(pom_url: str) -> str:
    """Скачивает содержимое POM-файла по заданному URL."""
    request = urllib.request.Request(
        pom_url, headers={"User-Agent": "DepGraphVisualizer/1.0"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=HTTP_TIMEOUT_SECONDS
        ) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ConfigError(
            f"Не удалось скачать POM-файл ({pom_url}): HTTP {exc.code}."
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ConfigError(
            f"Ошибка сети при обращении к репозиторию ({pom_url}): {exc}."
        ) from exc


def strip_namespace(tag: str) -> str:
    """Удаляет XML-пространство имен из имени тега."""
    _, _, local_name = tag.rpartition("}")
    return local_name


def extract_pom_properties(
    root: ET.Element, package_version: str
) -> dict[str, str]:
    """Извлекает словарь свойств <properties> из корневого элемента POM."""
    props = {
        "project.version": package_version,
        "pom.version": package_version,
    }
    for child in root:
        if strip_namespace(child.tag) == "properties":
            for prop in child:
                prop_name = strip_namespace(prop.tag)
                props[prop_name] = (prop.text or "").strip()
    return props


def resolve_property(value: str, props: dict[str, str]) -> str:
    """Подставляет значение свойства Maven вида ${property}."""
    cleaned = value.strip()
    if cleaned.startswith("${") and cleaned.endswith("}"):
        key = cleaned.removeprefix("${").removesuffix("}")
        return props.get(key, cleaned)
    return cleaned


def parse_dependency_element(
    dep_elem: ET.Element, props: dict[str, str]
) -> str | None:
    """Извлекает координаты одной зависимости из элемента <dependency>."""
    fields: dict[str, str] = {}
    for child in dep_elem:
        tag_name = strip_namespace(child.tag)
        fields[tag_name] = resolve_property(child.text or "", props)

    group_id = fields.get("groupId", "")
    artifact_id = fields.get("artifactId", "")
    version = fields.get("version", "")

    if not group_id or not artifact_id:
        return None
    if version:
        return f"{group_id}:{artifact_id}:{version}"
    return f"{group_id}:{artifact_id}"


def parse_direct_dependencies(xml_text: str, version: str) -> list[str]:
    """Парсит XML-текст POM-файла и возвращает список прямых зависимостей."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ConfigError(
            f"Ошибка разбора XML в POM-файле: {exc}."
        ) from exc

    props = extract_pom_properties(root, version)
    dependencies: list[str] = []

    for child in root:
        if strip_namespace(child.tag) == "dependencies":
            for dep_elem in child:
                if strip_namespace(dep_elem.tag) == "dependency":
                    parsed = parse_dependency_element(dep_elem, props)
                    if parsed:
                        dependencies.append(parsed)
    return dependencies


def get_direct_dependencies(config: AppConfig) -> list[str]:
    """Получает список прямых зависимостей для заданной конфигурации."""
    pom_url = build_pom_url(
        config.repo_source, config.package_name, config.package_version
    )
    xml_text = fetch_pom_xml(pom_url)
    return parse_direct_dependencies(xml_text, config.package_version)


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI-приложения."""
    try:
        config = build_config(argv)
        dependencies = get_direct_dependencies(config)
    except ConfigError as err:
        print(f"Ошибка: {err}", file=sys.stderr)
        return EXIT_ERROR_CODE

    print(
        f"Прямые зависимости пакета "
        f"{config.package_name}:{config.package_version}:"
    )
    if not dependencies:
        print("Прямые зависимости отсутствуют.")
    else:
        for dep in dependencies:
            print(dep)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())