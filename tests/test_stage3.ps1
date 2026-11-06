[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$py = ".\.venv\Scripts\python.exe"

Write-Host "`n--- 1. Standard graph traversal (A) ---"
& $py -m src.main -p A -r .\tests\test_repo.txt -t true

Write-Host "`n--- 2. Substring filter (-f C excludes C) ---"
& $py -m src.main -p A -r .\tests\test_repo.txt -t true -f C

Write-Host "`n--- 3. Substring filter (-f D excludes D) ---"
& $py -m src.main -p A -r .\tests\test_repo.txt -t true -f D

Write-Host "`n--- 4. Error: package not found in test repo ---"
& $py -m src.main -p Z -r .\tests\test_repo.txt -t true

Write-Host "`n--- 5. Error: lowercase package name in test mode ---"
& $py -m src.main -p abc -r .\tests\test_repo.txt -t true

Write-Host "`n--- 6. Error: missing test repo file ---"
& $py -m src.main -p A -r .\tests\missing.txt -t true