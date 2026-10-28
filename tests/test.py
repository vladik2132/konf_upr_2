"""Модульные тесты для проверки конфигурации Этапа 1."""

import tempfile
import unittest
from src.main import ConfigError, build_config


class TestCliConfig(unittest.TestCase):
    """Набор тестов для проверки парсинга и валидации параметров CLI."""

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
        with tempfile.NamedTemporaryFile(mode="w", delete=True) as tmp:
            argv = [
                "--package",
                "A",
                "--repo",
                tmp.name,
                "--test-mode",
                "true",
                "--version",
                "1.0",
                "--output",
                "out.png",
            ]
            cfg = build_config(argv)
            self.assertTrue(cfg.test_mode)
            self.assertEqual(cfg.repo_source, tmp.name)

    def test_invalid_package_name(self) -> None:
        """Проверяет ошибку при пустом или содержащем пробелы имени пакета."""
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

    def test_missing_test_repo_file(self) -> None:
        """Проверяет ошибку при несуществующем файле тестового репозитория."""
        argv = [
            "--package",
            "A",
            "--repo",
            "non_existent_repo.txt",
            "--test-mode",
            "true",
            "--version",
            "1.0",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)

    def test_invalid_test_mode_value(self) -> None:
        """Проверяет ошибку при некорректном значении --test-mode."""
        argv = [
            "--package",
            "junit:junit",
            "--repo",
            "https://repo1.maven.org/maven2",
            "--test-mode",
            "not_a_bool",
            "--version",
            "4.13",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)

    def test_invalid_version(self) -> None:
        """Проверяет ошибку при некорректном формате версии пакета."""
        argv = [
            "--package",
            "junit:junit",
            "--repo",
            "https://repo1.maven.org/maven2",
            "--version",
            "4.13 $$$",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)

    def test_invalid_output_extension(self) -> None:
        """Проверяет ошибку при неверном расширении выходного файла."""
        argv = [
            "--package",
            "junit:junit",
            "--repo",
            "https://repo1.maven.org/maven2",
            "--version",
            "4.13",
            "--output",
            "graph.svg",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)

    def test_invalid_ascii_tree_value(self) -> None:
        """Проверяет ошибку при некорректном значении --ascii-tree."""
        argv = [
            "--package",
            "junit:junit",
            "--repo",
            "https://repo1.maven.org/maven2",
            "--version",
            "4.13",
            "--ascii-tree",
            "invalid",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)

    def test_invalid_filter_substring(self) -> None:
        """Проверяет ошибку при наличии пробелов в подстроке фильтрации."""
        argv = [
            "--package",
            "junit:junit",
            "--repo",
            "https://repo1.maven.org/maven2",
            "--version",
            "4.13",
            "--filter",
            "bad filter",
        ]
        with self.assertRaises(ConfigError):
            build_config(argv)


if __name__ == "__main__":
    unittest.main()