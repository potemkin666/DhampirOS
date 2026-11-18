# AI-Assisted. Boot the reviewed USB ISO in a dedicated, host-local live VM.
[CmdletBinding()]
param([string]$IsoPath)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Repair-DhampirOSInput.ps1')

function Find-ReviewedIso([string]$RequestedPath) {
    $filename = 'DhampirOS-0.1.0-alpha.1-amd64.iso'
    if ($RequestedPath) { $candidates = @($RequestedPath) }
    else {
        $parent = Split-Path -Parent $PSScriptRoot
        $candidates = @((Join-Path $PSScriptRoot $filename), (Join-Path $parent $filename),
            (Join-Path (Join-Path $parent 'DhampirOS') $filename))
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            Write-Host 'Checking the ISO fingerprint. This can take a moment on USB...'
            $item = Get-Item -LiteralPath $candidate
            if ($item.Length -ne 1471897600 -or (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'eb1ca786925cd90c937878aafc0075c669a961ed439e11dc1550a9e516b9972f') {
                throw 'ISO identity check failed. The VM was not started. Use the reviewed 0.1.0-alpha.1 ISO.'
            }
            return $item.FullName
        }
    }
    throw 'ISO not found. Keep this folder beside DhampirOS-0.1.0-alpha.1-amd64.iso.'
}

function Start-DhampirLive([string]$ImagePath) {
    $script:VBoxManage = Find-VBoxManage
    $iso = Find-ReviewedIso $ImagePath
    $running = Invoke-VBox -Arguments @('list', 'runningvms')
    if ($running.Trim()) { throw 'Close the running VirtualBox VM(s) first, then run this launcher again. No VM was stopped or changed.' }
    $name = 'DhampirOS USB Live'
    $identity = $null
    $listing = Invoke-VBox -Arguments @('list', 'vms')
    foreach ($line in ($listing -split '\r?\n')) {
        if ($line -match '^"DhampirOS USB Live"\s+\{([0-9a-fA-F-]{36})\}$') { $identity = $Matches[1] }
    }
    if ($identity) {
        $marker = Invoke-VBox -Arguments @('getextradata', $identity, 'DhampirOS/USBLauncher')
        if ($marker.Trim() -ne 'Value: dhampiros-usb-live-v1') { throw 'An unrelated VM already uses this name. It was left unchanged.' }
        Assert-Stopped (Get-VMInfo $identity)
    } else {
        $base = Join-Path $env:LOCALAPPDATA 'DhampirOS\VirtualBox'
        $null = Invoke-VBox -Arguments @('createvm', '--name', $name, '--ostype', 'Debian_64', '--basefolder', $base, '--register')
        $listing = Invoke-VBox -Arguments @('list', 'vms')
        foreach ($line in ($listing -split '\r?\n')) {
            if ($line -match '^"DhampirOS USB Live"\s+\{([0-9a-fA-F-]{36})\}$') { $identity = $Matches[1] }
        }
        if (-not $identity) { throw 'Could not identify the newly registered VM. Nothing was started.' }
        $null = Invoke-VBox -Arguments @('setextradata', $identity, 'DhampirOS/USBLauncher', 'dhampiros-usb-live-v1')
    }
    $flags = Get-ModifyFlags
    $profile = [pscustomobject]@{ Keyboard = 'ps2'; Mouse = 'ps2'; OHCI = 'off'; EHCI = 'off'; XHCI = 'off'; Acceleration3D = 'off' }
    # Configure only the VM bearing our ownership marker, never a Kali/other VM.
    Set-InputProfile $identity $profile $flags
    $info = Get-VMInfo $identity
    $filters = @(Get-FilterStates $info['CfgFile'] | ForEach-Object {
        [pscustomobject]@{ Index = $_.Index; Signature = $_.Signature; Active = 'no' }
    })
    Set-FilterStates $identity $filters
    $null = Invoke-VBox -Arguments @('modifyvm', $identity, '--memory', '4096', '--cpus', '2', '--ioapic', 'on',
        '--graphicscontroller', 'vmsvga', '--vram', '128', '--firmware', 'bios', '--nic1', 'nat',
        '--clipboard-mode', 'disabled', '--draganddrop', 'disabled', '--vrde', 'off',
        '--boot1', 'dvd', '--boot2', 'none', '--boot3', 'none', '--boot4', 'none')
    $controller = 'DhampirOS Optical'
    $info = Get-VMInfo $identity
    $controllers = @($info.Keys | Where-Object { $_ -match '^storagecontrollername\d+$' -and $info[$_] -eq $controller })
    if ($controllers.Count -eq 0) {
        $null = Invoke-VBox -Arguments @('storagectl', $identity, '--name', $controller, '--add', 'sata', '--controller', 'IntelAhci', '--portcount', '1')
    }
    $null = Invoke-VBox -Arguments @('storageattach', $identity, '--storagectl', $controller, '--port', '0', '--device', '0', '--type', 'dvddrive', '--medium', $iso)
    $info = Get-VMInfo $identity
    Assert-Stopped $info
    Assert-Profile (Get-InputProfile $info['CfgFile']) $profile
    if (@(Get-FilterStates $info['CfgFile'] | Where-Object { $_.Active -eq 'yes' }).Count -gt 0) { throw 'USB filter verification failed; the VM was not started.' }
    Write-Host 'Starting DhampirOS USB Live with virtual PS/2 input and USB capture disabled.'
    Write-Host 'This is a live ISO session: no virtual hard disk is created. Save files before shutting it down.'
    Write-Host 'Windows Bluetooth and existing VMs have not been reconfigured.'
    $null = Invoke-VBox -Arguments @('startvm', $identity, '--type', 'gui')
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Start-DhampirLive $IsoPath }
    catch { Write-Host ('Launch stopped: {0}' -f $_.Exception.Message); exit 1 }
}
