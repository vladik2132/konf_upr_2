$py = ".\.venv\Scripts\python.exe"
$url = "https://repo1.maven.org/maven2"

Write-Host "`n--- 1. Корректный запуск: прямые зависимости junit:junit ---"
& $py -m src.main -p junit:junit -r $url -v 4.13.2

Write-Host "`n--- 2. Корректный запуск: прямые зависимости commons-lang3 ---"
& $py -m src.main -p org.apache.commons:commons-lang3 -r $url -v 3.12.0

Write-Host "`n--- 3. Ошибка формата пакета Maven (нет двоеточия) ---"
& $py -m src.main -p invalid_maven_name -r $url -v 1.0.0

Write-Host "`n--- 4. Ошибка загрузки POM-файла (несуществующая версия, HTTP 404) ---"
& $py -m src.main -p junit:junit -r $url -v 999.999.999

Write-Host "`n--- 5. Ошибка некорректного URL репозитория ---"
& $py -m src.main -p junit:junit -r invalid_url -v 4.13.2