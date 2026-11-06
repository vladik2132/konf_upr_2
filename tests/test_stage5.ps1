[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$py = ".\.venv\Scripts\python.exe"
$url = "https://repo1.maven.org/maven2"

Write-Host "`n--- 1. Визуализация пакета A (D2 код + PNG + ASCII-дерево) ---"
& $py -m src.main -p A -r .\tests\test_repo3.txt -t true -o graph_a.png -a true

Write-Host "`n--- 2. Визуализация пакета B с фильтрацией ---"
& $py -m src.main -p B -r .\tests\test_repo4.txt -t true -o graph_b.png -a true -f E

Write-Host "`n--- 3. Визуализация реального пакета Maven (commons-cli:1.5.0) ---"
& $py -m src.main -p commons-cli:commons-cli -r $url -v 1.5.0 -o graph_cli.png -a true