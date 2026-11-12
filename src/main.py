"""Модуль CLI для визуализации графа зависимостей (Этап 5, Вариант 13)."""

import argparse
import base64
import os
import re
import shutil
import ssl
import struct
import subprocess
import sys
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse
from xml.etree.ElementTree import Element, ParseError, fromstring

VALID_SCHEMES = ("http", "https")
TRUE_VALUES = ("true", "1", "yes")
FALSE_VALUES = ("false", "0", "no")
REQUIRED_EXTENSION = ".png"
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
TEST_PKG_PATTERN = re.compile(r"^[A-Z]+$")
COORD_PARTS_COUNT = 2
FULL_COORD_PARTS = 3
HTTP_TIMEOUT_SECONDS = 10
SINGLE_OFFSET = 1
ZLIB_COMPRESSION_LEVEL = 9
EXIT_SUCCESS = 0
EXIT_ERROR_CODE = 1
KROKI_D2_BASE_URL = "https://kroki.io/d2/png/"
DEFAULT_D2_WIN_PATH = r"C:\Program Files\D2\d2.exe"

CANVAS_WIDTH = 720
CANVAS_CENTER_X = 360
LEFT_COL_X = 190
RIGHT_COL_X = 530
NODE_START_Y = 55
ROW_STEP_Y = 90
MIN_CANVAS_HEIGHT = 260
BOTTOM_PADDING = 70
NODES_PER_ROW = 2
BOX_HALF_W = 145
BOX_HALF_H = 22
BORDER_WIDTH = 2
RGB_CHANNELS = 3
MAX_LABEL_LEN = 32
CHAR_STEP_X = 8
CHAR_HALF_W = 4
CHAR_HALF_H = 5
GLYPH_BITS = 15
GLYPH_LAST_BIT = 14
GLYPH_WIDTH = 3
FONT_SCALE = 2
CRC_MASK = 0xFFFFFFFF
WHITE_BYTE = 255
DEFAULT_GLYPH = 0o00700
EDGE_COLOR = b"\x25\x63\xeb"
BOX_FILL_COLOR = b"\xf0\xf7\xff"
BOX_BORDER_COLOR = b"\x1e\x40\xaf"
TEXT_COLOR = b"\x0f\x17\x2a"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

FONT_MAP: dict[str, int] = {
    "A": 0o25755, "B": 0o65656, "C": 0o34443, "D": 0o65556,
    "E": 0o74647, "F": 0o74644, "G": 0o34553, "H": 0o55755,
    "I": 0o72227, "J": 0o11152, "K": 0o55655, "L": 0o44447,
    "M": 0o57755, "N": 0o57555, "O": 0o25552, "P": 0o65644,
    "Q": 0o25521, "R": 0o65655, "S": 0o34216, "T": 0o72222,
    "U": 0o55557, "V": 0o55552, "W": 0o55775, "X": 0o55255,
    "Y": 0o55222, "Z": 0o71247, "0": 0o75557, "1": 0o26227,
    "2": 0o71747, "3": 0o71717, "4": 0o55711, "5": 0o74717,
    "6": 0o74757, "7": 0o71111, "8": 0o75757, "9": 0o75717,
    ":": 0o02020, ".": 0o00002, "-": 0o00700, "_": 0o00007,
}

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
    parser.add_argument("-p", "--package", required=True)
    parser.add_argument("-r", "--repo", required=True)
    parser.add_argument(
        "-t", "--test-mode", nargs="?", const="true", default="false"
    )
    parser.add_argument("-v", "--version", default="1.0.0")
    parser.add_argument("-o", "--output", default="graph.png")
    parser.add_argument(
        "-a", "--ascii-tree", nargs="?", const="true", default="false"
    )
    parser.add_argument("-f", "--filter", default="")
    parser.add_argument(
        "-l", "--load-order", nargs="?", const="true", default="false"
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
    root: Element, package_version: str
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
    dep_elem: Element, props: dict[str, str]
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
        root = fromstring(xml_text)
    except ParseError as exc:
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


def generate_d2_code(graph: dict[str, list[str]]) -> str:
    """Формирует текстовое представление графа на языке диаграмм D2."""
    lines = ["direction: down"]
    edges: list[str] = []
    for pkg, deps in graph.items():
        clean_pkg = pkg.replace('"', '\\"')
        if not deps:
            lines.append(f'"{clean_pkg}"')
        for dep in deps:
            clean_dep = dep.replace('"', '\\"')
            edges.append(f'"{clean_pkg}" -> "{clean_dep}"')
    lines.extend(sorted(set(edges)))
    return "\n".join(lines)


def collect_graph_nodes(graph: dict[str, list[str]]) -> list[str]:
    """Возвращает упорядоченный список всех уникальных узлов графа."""
    nodes = list(graph.keys())
    for deps in graph.values():
        for dep in deps:
            if dep not in nodes:
                nodes.append(dep)
    return nodes


def compute_node_positions(
    nodes: list[str],
) -> dict[str, tuple[int, int]]:
    """Вычисляет координаты центров узлов графа на графическом холсте."""
    if not nodes:
        return {}
    positions: dict[str, tuple[int, int]] = {
        nodes[0]: (CANVAS_CENTER_X, NODE_START_Y)
    }
    rest = nodes[SINGLE_OFFSET:]
    for idx, node in enumerate(rest):
        row = idx // NODES_PER_ROW + SINGLE_OFFSET
        pos_y = NODE_START_Y + row * ROW_STEP_Y
        is_right = idx % NODES_PER_ROW == SINGLE_OFFSET
        is_alone = (not is_right) and (idx == len(rest) - SINGLE_OFFSET)
        pos_x = (
            CANVAS_CENTER_X
            if is_alone
            else (RIGHT_COL_X if is_right else LEFT_COL_X)
        )
        positions[node] = (pos_x, pos_y)
    return positions


def set_pixel_thick(
    canvas: list[bytearray], pos_x: int, pos_y: int, color: bytes
) -> None:
    """Закрашивает точку 2x2 пикселя на холсте заданным RGB-цветом."""
    height = len(canvas)
    for dy in range(FONT_SCALE):
        ry = pos_y + dy
        if ry in range(height):
            row = canvas[ry]
            for dx in range(FONT_SCALE):
                rx = (pos_x + dx) * RGB_CHANNELS
                if rx in range(len(row) - BORDER_WIDTH):
                    row[rx : rx + RGB_CHANNELS] = color


def draw_line(
    canvas: list[bytearray],
    start: tuple[int, int],
    end: tuple[int, int],
    color: bytes,
) -> None:
    """Рисует соединительную линию между двумя узлами на холсте."""
    x1, y1 = start
    x2, y2 = end
    steps = max(abs(x2 - x1), abs(y2 - y1), SINGLE_OFFSET)
    for step in range(steps + SINGLE_OFFSET):
        px = x1 + (x2 - x1) * step // steps
        py = y1 + (y2 - y1) * step // steps
        set_pixel_thick(canvas, px, py, color)


def draw_glyph(
    canvas: list[bytearray], mask: int, x0: int, y0: int
) -> None:
    """Отрисовывает один символ размером 3x5 в масштабе 2x."""
    for bit_idx in range(GLYPH_BITS):
        if (mask >> (GLYPH_LAST_BIT - bit_idx)) & SINGLE_OFFSET:
            gx = x0 + (bit_idx % GLYPH_WIDTH) * FONT_SCALE
            gy = y0 + (bit_idx // GLYPH_WIDTH) * FONT_SCALE
            set_pixel_thick(canvas, gx, gy, TEXT_COLOR)


def draw_text(
    canvas: list[bytearray], text: str, start_x: int, start_y: int
) -> None:
    """Отрисовывает текстовую подпись узла встроенным растровым шрифтом."""
    cursor_x = start_x
    for ch in text.upper():
        mask = FONT_MAP.get(ch, DEFAULT_GLYPH)
        draw_glyph(canvas, mask, cursor_x, start_y)
        cursor_x += CHAR_STEP_X


def draw_box(
    canvas: list[bytearray], center_x: int, center_y: int, label: str
) -> None:
    """Рисует прямоугольный блок узла с рамкой и текстовой подписью."""
    x_min = center_x - BOX_HALF_W
    x_max = center_x + BOX_HALF_W
    y_min = center_y - BOX_HALF_H
    y_max = center_y + BOX_HALF_H
    for py in range(y_min, y_max):
        if py not in range(len(canvas)):
            continue
        is_v_border = (
            py < y_min + BORDER_WIDTH or py >= y_max - BORDER_WIDTH
        )
        row = canvas[py]
        for px in range(x_min, x_max):
            is_h_border = (
                px < x_min + BORDER_WIDTH or px >= x_max - BORDER_WIDTH
            )
            color = (
                BOX_BORDER_COLOR
                if (is_v_border or is_h_border)
                else BOX_FILL_COLOR
            )
            offset = px * RGB_CHANNELS
            row[offset : offset + RGB_CHANNELS] = color
    trimmed = label[:MAX_LABEL_LEN]
    text_x = center_x - len(trimmed) * CHAR_HALF_W
    draw_text(canvas, trimmed, text_x, center_y - CHAR_HALF_H)


def make_png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Формирует бинарный чанк формата PNG с контрольной суммой CRC32."""
    crc = zlib.crc32(chunk_type + data) & CRC_MASK
    return (
        struct.pack("!I", len(data))
        + chunk_type
        + data
        + struct.pack("!I", crc)
    )


def render_fallback_graph_png(
    graph: dict[str, list[str]], output_image: str
) -> None:
    """Генерирует PNG-изображение графа средствами стандартной библиотеки."""
    nodes = collect_graph_nodes(graph)
    positions = compute_node_positions(nodes)
    max_y = max(
        (pos[SINGLE_OFFSET] for pos in positions.values()),
        default=MIN_CANVAS_HEIGHT,
    )
    height = max(MIN_CANVAS_HEIGHT, max_y + BOTTOM_PADDING)
    row_len = CANVAS_WIDTH * RGB_CHANNELS
    canvas = [bytearray([WHITE_BYTE] * row_len) for _ in range(height)]

    for src, deps in graph.items():
        for dst in deps:
            if src in positions and dst in positions:
                draw_line(canvas, positions[src], positions[dst], EDGE_COLOR)

    for node, (cx, cy) in positions.items():
        draw_box(canvas, cx, cy, node)

    raw_data = b"".join(b"\x00" + bytes(row) for row in canvas)
    ihdr = struct.pack("!IIBBBBB", CANVAS_WIDTH, height, 8, 2, 0, 0, 0)
    png_bytes = (
        PNG_SIGNATURE
        + make_png_chunk(b"IHDR", ihdr)
        + make_png_chunk(
            b"IDAT", zlib.compress(raw_data, ZLIB_COMPRESSION_LEVEL)
        )
        + make_png_chunk(b"IEND", b"")
    )
    with open(output_image, "wb") as file_obj:
        file_obj.write(png_bytes)


def render_via_local_d2(d2_code: str, output_image: str) -> bool:
    """Пытается сгенерировать PNG-файл с помощью локальной утилиты D2."""
    d2_bin = shutil.which("d2")
    if not d2_bin and os.path.isfile(DEFAULT_D2_WIN_PATH):
        d2_bin = DEFAULT_D2_WIN_PATH
    if not d2_bin:
        return False
    temp_d2 = f"{output_image}.d2"
    try:
        with open(temp_d2, "w", encoding="utf-8") as file_obj:
            file_obj.write(d2_code)
        subprocess.run(
            [d2_bin, temp_d2, output_image],
            check=True,
            capture_output=True,
        )
        return os.path.isfile(output_image)
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        if os.path.exists(temp_d2):
            os.remove(temp_d2)


def render_d2_to_png(
    d2_code: str, graph: dict[str, list[str]], output_image: str
) -> None:
    """Сохраняет изображение графа в файл формата PNG."""
    if render_via_local_d2(d2_code, output_image):
        return
    compressed = zlib.compress(
        d2_code.encode("utf-8"), ZLIB_COMPRESSION_LEVEL
    )
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    req = urllib.request.Request(
        f"{KROKI_D2_BASE_URL}{encoded}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        ssl_ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(
            req, timeout=HTTP_TIMEOUT_SECONDS, context=ssl_ctx
        ) as resp:
            with open(output_image, "wb") as file_obj:
                file_obj.write(resp.read())
        return
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    render_fallback_graph_png(graph, output_image)


def print_ascii_tree(
    node: str,
    graph: dict[str, list[str]],
    prefix: str = "",
    ancestors: set[str] | None = None,
) -> None:
    """Выводит зависимости пакета в виде ASCII-дерева."""
    current_path = set(ancestors) if ancestors else {node}
    deps = graph.get(node, [])
    for idx, dep in enumerate(deps):
        is_last = idx == len(deps) - SINGLE_OFFSET
        connector = "└── " if is_last else "├── "
        if dep in current_path:
            print(f"{prefix}{connector}{dep} (цикл)")
        else:
            print(f"{prefix}{connector}{dep}")
            next_prefix = prefix + ("    " if is_last else "│   ")
            print_ascii_tree(
                dep, graph, next_prefix, current_path | {dep}
            )


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


def print_visualization_results(
    root_key: str, graph: dict[str, list[str]], config: AppConfig
) -> None:
    """Формирует D2-описание, сохраняет PNG и выводит ASCII-дерево."""
    print(f"Граф зависимостей для пакета {root_key}:")
    if not graph:
        print("Граф пуст.")
        return

    d2_code = generate_d2_code(graph)
    print("Текстовое представление графа на языке D2:")
    print(d2_code)

    if config.load_order:
        order = compute_load_order(graph)
        print("Порядок загрузки зависимостей:")
        for idx, pkg in enumerate(order, start=1):
            print(f"  {idx}. {pkg}")

    if config.ascii_tree:
        print("Дерево зависимостей (ASCII):")
        print(root_key)
        print_ascii_tree(root_key, graph)

    render_d2_to_png(d2_code, graph, config.output_image)
    print(f"Изображение графа сохранено в файл: {config.output_image}")


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
    print_visualization_results(root_key, graph, config)


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