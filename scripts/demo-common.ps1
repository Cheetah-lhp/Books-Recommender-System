# Probe the same loopback address used by all demo services; no CIM/admin access needed.
function Test-DemoPort {
    param([int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync('127.0.0.1', $Port)
        return $connection.Wait(500) -and $client.Connected
    }
    catch { return $false }
    finally { $client.Dispose() }
}
