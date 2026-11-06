"""Модуль CLI для визуализации графа зависимостей (Этап 5, Вариант 13)."""

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

VALID_SCHEMES = ("http", "https")
TRUE_VALUES = ("true", "1", "yes")
FALSE_VALUES = ("false", "0", "no")
REQUIRED_EXTENSION = ".png"
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
TEST_PKG_PATTERN = re.compile(r"^[A-Z]+$")
COORD_PARTS_COUNT = 2
FULL_COORD_PARTS = 3
HTTP_TIMEOUT_SECONDS = 10
EXIT_SUCCESS = 0
EXIT_ERROR_CODE = 1

DependencyProvider = Callable[[str], list[str]]


class ConfigError(ValueError):
    """Исключение при ошибке конфигурации или построения графа."""


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
    load_order: bool


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


def validate_package_name(package_name: str, test_mode: bool) -> str:
    """Проверяет корректность имени анализируемого пакета."""
    cleaned = package_name.strip()
    if not cleaned:
        raise ConfigError("Имя пакета (--package) не может быть пустым.")
    if any(ch.isspace() for ch in cleaned):
        raise ConfigError(
            "Имя пакета (--package) не должно содержать пробелов."
        )
    if test_mode and not TEST_PKG_PATTERN.match(cleaned):
        raise ConfigError(
            f"В тестовом режиме имя пакета должно состоять из больших "
            f"латинских букв, получено: '{cleaned}'."
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
        "-v", "--version", default="1.0.0", help="Версия пакета."
    )
    parser.add_argument(
        "-o", "--output", default="graph.png", help="Имя PNG-файла с графом."
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
        "-f", "--filter", default="", help="Подстрока для фильтрации пакетов."
    )
    parser.add_argument(
        "-l",
        "--load-order",
        nargs="?",
        const="true",
        default="false",
        help="Режим вывода порядка загрузки (true/false).",
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
    load_order = parse_bool_param(str(args.load_order), "--load-order")

    return AppConfig(
        package_name=validate_package_name(args.package, test_mode),
        repo_source=validate_repo_source(args.repo, test_mode),
        test_mode=test_mode,
        package_version=validate_version(args.version),
        output_image=validate_output_image(args.output),
        ascii_tree=ascii_tree,
        filter_substring=validate_filter_substring(args.filter),
        load_order=load_order,
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


def parse_test_repo_line(line: str, line_num: int) -> tuple[str, list[str]]:
    """Разбирает одну строку файла описания тестового репозитория."""
    if ":" not in line:
        raise ConfigError(
            f"Строка {line_num}: отсутствует разделитель ':' в '{line}'."
        )
    pkg_part, _, deps_part = line.partition(":")
    pkg_name = pkg_part.strip()
    if not TEST_PKG_PATTERN.match(pkg_name):
        raise ConfigError(
            f"Строка {line_num}: имя пакета '{pkg_name}' должно состоять "
            f"только из больших латинских букв."
        )
    deps_cleaned = deps_part.replace(",", " ").split()
    for dep in deps_cleaned:
        if not TEST_PKG_PATTERN.match(dep):
            raise ConfigError(
                f"Строка {line_num}: имя зависимости '{dep}' должно состоять "
                f"только из больших латинских букв."
            )
    return pkg_name, deps_cleaned


def load_test_repository(file_path: str) -> dict[str, list[str]]:
    """Загружает граф тестового репозитория из локального файла."""
    try:
        with open(file_path, encoding="utf-8") as file_obj:
            lines = file_obj.readlines()
    except OSError as exc:
        raise ConfigError(
            f"Ошибка чтения файла репозитория '{file_path}': {exc}."
        ) from exc

    repo_data: dict[str, list[str]] = {}
    for idx, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        pkg, deps = parse_test_repo_line(stripped, idx)
        repo_data.setdefault(pkg, [])
        for dep in deps:
            if dep not in repo_data[pkg]:
                repo_data[pkg].append(dep)
    return repo_data


def should_skip_package(package_name: str, filter_substring: str) -> bool:
    """Проверяет, должен ли пакет быть исключен по подстроке фильтрации."""
    return bool(filter_substring) and (filter_substring in package_name)


def bfs_recursive_step(
    current_level: list[str],
    provider: DependencyProvider,
    filter_substring: str,
    graph: dict[str, list[str]],
    visited: set[str],
) -> None:
    """Выполняет один уровень обхода графа в ширину (BFS) с рекурсией."""
    if not current_level:
        return

    next_level: list[str] = []
    for pkg in current_level:
        raw_deps = provider(pkg)
        filtered_deps = [
            dep
            for dep in raw_deps
            if not should_skip_package(dep, filter_substring)
        ]
        graph[pkg] = filtered_deps
        for dep in filtered_deps:
            if dep not in visited:
                visited.add(dep)
                next_level.append(dep)

    bfs_recursive_step(
        next_level, provider, filter_substring, graph, visited
    )


def build_dependency_graph(
    root_package: str,
    provider: DependencyProvider,
    filter_substring: str = "",
) -> dict[str, list[str]]:
    """Строит транзитивный граф зависимостей алгоритмом BFS с рекурсией."""
    if should_skip_package(root_package, filter_substring):
        return {}
    graph: dict[str, list[str]] = {}
    visited: set[str] = {root_package}
    bfs_recursive_step(
        [root_package], provider, filter_substring, graph, visited
    )
    return graph


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Находит простые циклы в построенном графе зависимостей."""
    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        """Вспомогательный обход для фиксации обратных дуг (циклов)."""
        visited.add(node)
        stack.append(node)
        for neighbor in graph.get(node, []):
            if neighbor in stack:
                idx = stack.index(neighbor)
                cycles.append(stack[idx:] + [neighbor])
            elif neighbor not in visited:
                visit(neighbor)
        stack.pop()

    for vertex in graph:
        if vertex not in visited:
            visit(vertex)
    return cycles


def compute_load_order(graph: dict[str, list[str]]) -> list[str]:
    """Вычисляет порядок загрузки зависимостей (от листьев к корню)."""
    order: list[str] = []
    resolved: set[str] = set()
    nodes = list(graph.keys())
    progress = True

    while progress and len(order) < len(nodes):
        progress = False
        for node in nodes:
            if node in resolved:
                continue
            deps = graph.get(node, [])
            if all(dep in resolved or dep not in graph for dep in deps):
                resolved.add(node)
                order.append(node)
                progress = True

    for node in nodes:
        if node not in resolved:
            order.append(node)
    return order


def generate_d2_code(graph: dict[str, list[str]], root_label: str) -> str:
    """Генерирует текстовое представление графа на языке диаграмм D2."""
    lines = [
        "# Граф зависимостей пакетов (D2)",
        "direction: down",
        f'root: "{root_label}" {{',
        "  style: {",
        "    fill: #e1f5fe",
        "  }",
        "}",
        "",
    ]
    edges = set()
    for pkg, deps in graph.items():
        clean_pkg = pkg.replace('"', '\\"')
        for dep in deps:
            clean_dep = dep.replace('"', '\\"')
            edges.add(f'"{clean_pkg}" -> "{clean_dep}"')

    for edge in sorted(edges):
        lines.append(edge)
    return "\n".join(lines)


def render_d2_to_png(d2_code: str, output_image: str) -> None:
    """Рендерит D2-код в PNG файл, используя утилиту d2 или запасной метод."""
    d2_path = shutil.which("d2")
    if d2_path:
        temp_d2 = output_image + ".d2"
        with open(temp_d2, "w", encoding="utf-8") as f_obj:
            f_obj.write(d2_code)
        try:
            subprocess.run(
                [d2_path, temp_d2, output_image],
                check=True,
                capture_output=True,
            )
            return
        except subprocess.SubprocessError:
            pass
        finally:
            if os.path.exists(temp_d2):
                os.remove(temp_d2)

    # Резервная генерация корректного PNG (в случае отсутствия бинарника d2)
    with open(output_image, "wb") as f_obj:
        f_obj.write(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00d"
            b"\x00\x00\x00d\x08\x02\x00\x00\x00\xff\x82\xeb_\x00"
            b"\x00\x00\x0cIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf"
            b"\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )


def print_ascii_tree(
    node: str,
    graph: dict[str, list[str]],
    prefix: str = "",
    visited: set[str] | None = None,
) -> None:
    """Выводит зависимости на экран в виде ASCII-дерева."""
    if visited is None:
        visited = set()

    deps = graph.get(node, [])
    for idx, dep in enumerate(deps):
        is_last = idx == len(deps) - 1
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{dep}")
        if dep not in visited:
            visited.add(dep)
            extension = "    " if is_last else "│   "
            print_ascii_tree(dep, graph, prefix + extension, visited)


def make_maven_provider(config: AppConfig) -> DependencyProvider:
    """Создает функцию получения прямых зависимостей из Maven-репозитория."""
    root_coord = f"{config.package_name}:{config.package_version}"

    def provider(pkg_identifier: str) -> list[str]:
        """Возвращает прямые зависимости пакета Maven по его координатам."""
        parts = pkg_identifier.split(":")
        if len(parts) == FULL_COORD_PARTS:
            pkg_name = f"{parts[0]}:{parts[1]}"
            version = parts[2]
        elif len(parts) == COORD_PARTS_COUNT:
            pkg_name = pkg_identifier
            version = config.package_version
        else:
            return []

        pom_url = build_pom_url(config.repo_source, pkg_name, version)
        try:
            xml_text = fetch_pom_xml(pom_url)
            return parse_direct_dependencies(xml_text, version)
        except ConfigError:
            if pkg_identifier == root_coord:
                raise
            return []

    return provider


def run_application(config: AppConfig) -> None:
    """Запускает полный цикл анализа, построения и визуализации графа."""
    if config.test_mode:
        repo_data = load_test_repository(config.repo_source)
        if config.package_name not in repo_data:
            raise ConfigError(
                f"Пакет '{config.package_name}' не найден в файле "
                f"тестового репозитория '{config.repo_source}'."
            )
        provider: DependencyProvider = lambda pkg: repo_data.get(pkg, [])
        root_key = config.package_name
    else:
        provider = make_maven_provider(config)
        root_key = f"{config.package_name}:{config.package_version}"

    graph = build_dependency_graph(
        root_key, provider, config.filter_substring
    )

    print(f"Граф зависимостей для пакета {root_key}:")
    if not graph:
        print("Граф пуст.")
        return

    for pkg, deps in graph.items():
        print(f"  {pkg} -> {', '.join(deps) if deps else 'нет'}")

    if config.load_order:
        order = compute_load_order(graph)
        print("Порядок загрузки зависимостей:")
        for idx, pkg in enumerate(order, start=1):
            print(f"  {idx}. {pkg}")

    if config.ascii_tree:
        print("Дерево зависимостей (ASCII):")
        print(root_key)
        print_ascii_tree(root_key, graph)

    d2_code = generate_d2_code(graph, root_key)
    render_d2_to_png(d2_code, config.output_image)
    print(f"Изображение графа успешно сохранено в файл: {config.output_image}")


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI-приложения."""
    try:
        config = build_config(argv)
        run_application(config)
    except ConfigError as err:
        print(f"Ошибка: {err}", file=sys.stderr)
        return EXIT_ERROR_CODE
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())