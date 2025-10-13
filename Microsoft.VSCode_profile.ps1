chcp 65001 > $null
$env:PYTHONIOENCODING = 'utf-8'
[Console]::InputEncoding  = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding           = New-Object System.Text.UTF8Encoding($false)