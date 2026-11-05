"""Модульные тесты для проверки Этапов 1 и 2."""

import os
import tempfile
import unittest
from src.main import (
    ConfigError,
    build_config,
    build_pom_url,
    parse_direct_dependencies,
)

SAMPLE_POM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.example</groupId>
  <artifactId>demo-app</artifactId>
  <version>1.0.0</version>
  <properties>
    <slf4j.version>2.0.9</slf4j.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
    </dependency>
    <dependency>
      <groupId>org.slf4j</groupId>
      <artifactId>slf4j-api</artifactId>
      <version>${slf4j.version}</version>
    </dependency>
  </dependencies>
</project>
"""


class TestCliAndMaven(unittest.TestCase):
    """Набор тестов для проверки конфигурации CLI и парсера Maven POM."""

    def test_valid_url_config(self) -> None:
        """Проверяет корректную конфигурацию с URL репозитория."""
        argv = [
            "--package",
            "org.apache.commons:commons-lang3",
            "--repo",
            "https://repo1.maven.org/maven2",
            "--test-mode",
            "false",
            "--version",
            "3.12.0",
            "--output",
            "deps.png",
            "--ascii-tree",
            "true",
            "--filter",
            "test",
        ]
        cfg = build_config(argv)
        self.assertEqual(cfg.package_name, "org.apache.commons:commons-lang3")
        self.assertFalse(cfg.test_mode)
        self.assertTrue(cfg.ascii_tree)

    def test_valid_test_repo_file(self) -> None:
        """Проверяет корректную работу в режиме тестового файла."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            argv = [
                "--package",
                "A",
                "--repo",
                tmp_path,
                "--test-mode",
                "true",
                "--version",
                "1.0",
                "--output",
                "out.png",
            ]
            cfg = build_config(argv)
            self.assertTrue(cfg.test_mode)
            self.assertEqual(cfg.repo_source, tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_invalid_package_name(self) -> None:
        """Проверяет ошибку при пустом имени пакета."""
        argv = [
            "--package",
            "   ",
            "--repo",
            "https://repo1.maven.org/maven2",
            "--version",
            "1.0.0",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)

    def test_invalid_repo_url(self) -> None:
        """Проверяет ошибку при некорректном URL репозитория."""
        argv = [
            "--package",
            "junit:junit",
            "--repo",
            "ftp://invalid-url",
            "--version",
            "4.13",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)

    def test_build_pom_url_success(self) -> None:
        """Проверяет формирование URL до POM-файла пакета."""
        url = build_pom_url(
            "https://repo1.maven.org/maven2",
            "org.apache.commons:commons-lang3",
            "3.12.0",
        )
        expected = (
            "https://repo1.maven.org/maven2/org/apache/commons/"
            "commons-lang3/3.12.0/commons-lang3-3.12.0.pom"
        )
        self.assertEqual(url, expected)

    def test_build_pom_url_invalid_coords(self) -> None:
        """Проверяет ошибку при отсутствии двоеточия в имени пакета Maven."""
        with self.assertRaises(ConfigError):
            build_pom_url(
                "https://repo1.maven.org/maven2", "invalid_package", "1.0"
            )

    def test_parse_direct_dependencies(self) -> None:
        """Проверяет извлечение прямых зависимостей и свойств из POM XML."""
        deps = parse_direct_dependencies(SAMPLE_POM_XML, "1.0.0")
        self.assertEqual(
            deps, ["junit:junit:4.13.2", "org.slf4j:slf4j-api:2.0.9"]
        )

    def test_parse_broken_xml(self) -> None:
        """Проверяет обработку ошибки при некорректном XML."""
        with self.assertRaises(ConfigError):
            parse_direct_dependencies("<project><broken></project>", "1.0.0")


if __name__ == "__main__":
    unittest.main()