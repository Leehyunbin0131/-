$ports = 8000, 3000
foreach ($port in $ports) {
    $seen = @{}
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        $procId = $_.OwningProcess
        if ($procId -and -not $seen.ContainsKey($procId)) {
            $seen[$procId] = $true
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}
