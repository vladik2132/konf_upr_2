[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$py = ".\.venv\Scripts\python.exe"
$url = "https://repo1.maven.org/maven2"

Write-Host "`n--- 1. Load order: standard graph from package A ---"
& $py -m src.main -p A -r .\tests\test_repo.txt -t true -l true

Write-Host "`n--- 2. Load order: filtered graph (-f E excludes E) ---"
& $py -m src.main -p A -r .\tests\test_repo.txt -t true -f E -l true

Write-Host "`n--- 3. Load order: subgraph from package B ---"
& $py -m src.main -p B -r .\tests\test_repo.txt -t true -l true

Write-Host "`n--- 4. Load order: cyclic graph (G <-> H) ---"
& $py -m src.main -p G -r .\tests\test_repo.txt -t true -l true

Write-Host "`n--- 5. Real Maven package load order (commons-cli:1.5.0) ---"
& $py -m src.main -p commons-cli:commons-cli -r$url -v 1.5.0 -l true