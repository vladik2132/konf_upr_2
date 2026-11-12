[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$py = ".\.venv\Scripts\python.exe"
$url = "https://repo.maven.apache.org/maven2"

Write-Host "`n--- 1. Maven Package 1: junit:junit (4.13.2) ---"
& $py -m src.main -p junit:junit -r $url -v 4.13.2 -o junit.png -a true

Write-Host "`n--- 2. Maven Package 2: commons-cli:commons-cli (1.5.0) ---"
& $py -m src.main -p commons-cli:commons-cli -r $url -v 1.5.0 -o commons_cli.png -a true

Write-Host "`n--- 3. Maven Package 3: org.slf4j:slf4j-simple (1.7.36) ---"
& $py -m src.main -p org.slf4j:slf4j-simple -r $url -v 1.7.36 -o slf4j.png -a true

Write-Host "`n--- 4. Test Repository Package A (with ASCII tree & PNG) ---"
& $py -m src.main -p A -r .\tests\test_repo5.txt -t true -o test_a.png -a true
