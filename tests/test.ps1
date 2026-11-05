$py = ".\.venv\Scripts\python.exe"
$url = "https://repo1.maven.org/maven2"

Write-Host "`n--- 1. Корректный запуск ---"
& $py -m src.main -p junit:junit -r $url -t false -v 4.13.2 -o deps.png -a true -f core

Write-Host "`n--- 2. Ошибка --package (пустое имя) ---"
& $py -m src.main -p " " -r $url -v 1.0

Write-Host "`n--- 3. Ошибка --repo (некорректный URL) ---"
& $py -m src.main -p app -r invalid_url -v 1.0

Write-Host "`n--- 4. Ошибка --repo (файл тестового репозитория не найден) ---"
& $py -m src.main -p A -r missing.txt -t true -v 1.0

Write-Host "`n--- 5. Ошибка --test-mode (неверное булево значение) ---"
& $py -m src.main -p app -r $url -t maybe -v 1.0

Write-Host "`n--- 6. Ошибка --version (недопустимые символы) ---"
& $py -m src.main -p app -r $url -v "1.0 beta!"

Write-Host "`n--- 7. Ошибка --output (неверное расширение файла) ---"
& $py -m src.main -p app -r $url -v 1.0 -o graph.jpg

Write-Host "`n--- 8. Ошибка --ascii-tree (неверное булево значение) ---"
& $py -m src.main -p app -r $url -v 1.0 -a 123

Write-Host "`n--- 9. Ошибка --filter (пробелы в подстроке) ---"
& $py -m src.main -p app -r $url -v 1.0 -f "two words"