# AI-Assisted. Reversible host-side compatibility settings for one stopped VM.
[CmdletBinding()]
param([string]$VM, [string]$RestoreFrom, [switch]$WhatIf)

$ErrorActionPreference = 'Stop'
$script:RepairScript = $PSCommandPath
$script:RepairRoot = Split-Path -Parent $PSCommandPath

function Find-VBoxManage {
    $command = Get-Command VBoxManage.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $directories = @()
    foreach ($key in @('HKLM:\SOFTWARE\Oracle\VirtualBox', 'HKLM:\SOFTWARE\WOW6432Node\Oracle\VirtualBox')) {
        if (Test-Path -LiteralPath $key) {
            $item = Get-ItemProperty -LiteralPath $key
            if ($item.InstallDir) { $directories += [string]$item.InstallDir }
        }
    }
    if ($env:ProgramFiles) { $directories += (Join-Path $env:ProgramFiles 'Oracle\VirtualBox') }
    foreach ($directory in $directories) {
        $path = Join-Path $directory 'VBoxManage.exe'
        if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    }
    throw 'VirtualBox was not found. Run this repair on the Windows desktop where the VM is registered.'
}

function Invoke-VBox([string[]]$Arguments) {
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $script:VBoxManage @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    $text = ($output | Out-String).Trim()
    if ($code -ne 0) { throw ('VBoxManage failed ({0}): {1}' -f $code, $text) }
    return $text
}

function Get-VMInfo([string]$Identity) {
    $info = @{}
    $text = Invoke-VBox -Arguments @('showvminfo', $Identity, '--machinereadable')
    foreach ($line in ($text -split '\r?\n')) {
        if ($line -match '^([^=]+)=(.*)$') {
            $value = $Matches[2]
            if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2).Replace('\"', '"').Replace('\\', '\')
            }
            $info[$Matches[1].Trim('"')] = $value
        }
    }
    if (-not $info['CfgFile'] -or -not $info['VMState']) { throw 'Incomplete VirtualBox VM information; nothing changed.' }
    return $info
}

function Select-RepairVM([string]$Name) {
    $machines = @()
    $listing = Invoke-VBox -Arguments @('list', 'vms')
    foreach ($line in ($listing -split '\r?\n')) {
        if ($line -match '^"(.*)"\s+\{([0-9a-fA-F-]{36})\}$') {
            $machines += [pscustomobject]@{ Name = $Matches[1]; Id = $Matches[2] }
        }
    }
    if ($Name) {
        $selected = @($machines | Where-Object { $_.Name -eq $Name -or $_.Id -eq $Name.Trim('{}') })
        if ($selected.Count -ne 1) { throw 'The named VM is not uniquely registered for this Windows user.' }
        return $selected[0]
    }
    $candidates = @()
    foreach ($machine in $machines) {
        if ($machine.Name -match '(?i)dhampir') { $candidates += $machine; continue }
        try {
            $info = Get-VMInfo $machine.Id
            if (@($info.Values | Where-Object { $_ -match '(?i)DhampirOS[^\\/]*\.iso$' }).Count -gt 0) {
                $candidates += $machine
            }
        } catch { Write-Host ('Could not inspect VM: {0}' -f $machine.Name) }
    }
    if ($candidates.Count -eq 1) { return $candidates[0] }
    if ($candidates.Count -eq 0) { $candidates = $machines }
    if ($candidates.Count -eq 0) { throw 'No registered VMs found. Run this on the affected desktop, under your usual Windows account.' }
    Write-Host 'Select the DhampirOS VM. Other VMs will be left alone:'
    for ($index = 0; $index -lt $candidates.Count; $index++) {
        Write-Host ('  {0}. {1}' -f ($index + 1), $candidates[$index].Name)
    }
    $answer = Read-Host 'VM number (Enter cancels)'
    $number = 0
    if (-not [int]::TryParse($answer, [ref]$number) -or $number -lt 1 -or $number -gt $candidates.Count) {
        throw 'Cancelled; no settings changed.'
    }
    return $candidates[$number - 1]
}

function Get-InputProfile([string]$ConfigPath) {
    $settings = New-Object System.Xml.XmlReaderSettings
    $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $reader = [System.Xml.XmlReader]::Create($ConfigPath, $settings)
    try {
        $document = New-Object System.Xml.XmlDocument
        $document.XmlResolver = $null
        $document.Load($reader)
    } finally { $reader.Dispose() }
    $hardware = $document.SelectSingleNode('/*[local-name()="VirtualBox"]/*[local-name()="Machine"]/*[local-name()="Hardware"]')
    if (-not $hardware) { throw 'Unsupported VM configuration; nothing changed.' }
    $profile = [ordered]@{ Keyboard = 'ps2'; Mouse = 'ps2'; OHCI = 'off'; EHCI = 'off'; XHCI = 'off'; Acceleration3D = 'off' }
    $hid = $hardware.SelectSingleNode('*[local-name()="HID"]')
    if ($hid) {
        $keyboards = @{ PS2Keyboard = 'ps2'; USBKeyboard = 'usb' }
        $mice = @{ PS2Mouse = 'ps2'; USBMouse = 'usb'; USBTablet = 'usbtablet'; USBMultiTouch = 'usbmultitouch'; USBMultiTouchScreenPlusPad = 'usbmtscreenpluspad' }
        if ($hid.HasAttribute('Keyboard')) {
            $profile.Keyboard = $keyboards[$hid.GetAttribute('Keyboard')]
            if (-not $profile.Keyboard) { throw 'Unknown virtual keyboard type; nothing changed.' }
        }
        if ($hid.HasAttribute('Pointing')) {
            $profile.Mouse = $mice[$hid.GetAttribute('Pointing')]
            if (-not $profile.Mouse) { throw 'Unknown virtual pointer type; nothing changed.' }
        }
    }
    foreach ($controller in @($hardware.SelectNodes('*[local-name()="USB"]/*[local-name()="Controllers"]/*[local-name()="Controller"]'))) {
        $type = $controller.GetAttribute('type').ToUpperInvariant()
        if ($type -notin @('OHCI', 'EHCI', 'XHCI')) { throw 'Unknown USB controller; nothing changed.' }
        $profile[$type] = 'on'
    }
    $legacy = $hardware.SelectSingleNode('*[local-name()="USBController"]')
    if ($legacy) {
        if ($legacy.GetAttribute('enabled') -eq 'true') { $profile.OHCI = 'on' }
        if ($legacy.GetAttribute('enabledEhci') -eq 'true') { $profile.EHCI = 'on' }
    }
    $display = $hardware.SelectSingleNode('*[local-name()="Display"]')
    if ($display -and $display.GetAttribute('accelerate3D') -eq 'true') { $profile.Acceleration3D = 'on' }
    return [pscustomobject]$profile
}

function Get-ModifyFlags {
    $helpText = Invoke-VBox -Arguments @('modifyvm', '--help')
    $flags = @{}
    foreach ($pair in @(@('OHCI', '--usb-ohci', '--usb'), @('EHCI', '--usb-ehci', '--usbehci'),
        @('XHCI', '--usb-xhci', '--usbxhci'), @('Acceleration3D', '--accelerate-3d', '--accelerate3d'))) {
        $option = $pair[1]
        if (-not $helpText.Contains($option)) { $option = $pair[2] }
        if (-not $helpText.Contains($option)) { throw 'Unsupported VBoxManage options; nothing changed.' }
        $flags[$pair[0]] = $option
    }
    return $flags
}

function Get-FilterStates([string]$ConfigPath) {
    $settings = New-Object System.Xml.XmlReaderSettings
    $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $reader = [System.Xml.XmlReader]::Create($ConfigPath, $settings)
    try {
        $document = New-Object System.Xml.XmlDocument
        $document.XmlResolver = $null
        $document.Load($reader)
    } finally { $reader.Dispose() }
    $hardware = $document.SelectSingleNode('/*[local-name()="VirtualBox"]/*[local-name()="Machine"]/*[local-name()="Hardware"]')
    $nodes = @($hardware.SelectNodes('*[local-name()="USB"]/*[local-name()="DeviceFilters"]/*[local-name()="DeviceFilter"] | *[local-name()="USBDeviceFilters"]/*[local-name()="DeviceFilter"]'))
    $index = 0
    foreach ($node in $nodes) {
        # Identity excludes activation, so Undo cannot enable a different, newly added filter.
        $parts = @($node.Attributes | Where-Object { $_.Name -ne 'active' } | Sort-Object Name |
            ForEach-Object { $_.Name + "`0" + $_.Value })
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try { $signature = [BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes(($parts -join "`0")))).Replace('-', '') }
        finally { $sha.Dispose() }
        $active = 'no'
        if ($node.GetAttribute('active') -eq 'true') { $active = 'yes' }
        [pscustomobject]@{ Index = $index; Signature = $signature; Active = $active }
        $index++
    }
}

function Assert-FilterIdentity($Actual, $Expected) {
    if (@($Actual).Count -ne @($Expected).Count) { throw 'The USB filter list changed; automatic restore is unsafe.' }
    for ($index = 0; $index -lt @($Expected).Count; $index++) {
        if ($Actual[$index].Signature -ne $Expected[$index].Signature -or $Expected[$index].Index -ne $index -or $Expected[$index].Active -notin @('yes', 'no')) {
            throw 'The USB filter identities changed; automatic restore is unsafe.'
        }
    }
}

function Set-FilterStates([string]$Identity, $States) {
    $info = Get-VMInfo $Identity
    Assert-Stopped $info
    $actual = @(Get-FilterStates $info['CfgFile'])
    Assert-FilterIdentity $actual $States
    foreach ($item in $States) {
        $null = Invoke-VBox -Arguments @('usbfilter', 'modify', [string]$item.Index, '--target', $Identity, '--active', $item.Active)
    }
    $result = @(Get-FilterStates (Get-VMInfo $Identity)['CfgFile'])
    for ($index = 0; $index -lt @($States).Count; $index++) {
        if ($result[$index].Active -ne $States[$index].Active) { throw 'USB filter activation could not be verified.' }
    }
}

function Set-InputProfile([string]$Identity, $Profile, $Flags) {
    if ($Profile.Keyboard -notin @('ps2', 'usb') -or $Profile.Mouse -notin @('ps2', 'usb', 'usbtablet', 'usbmultitouch', 'usbmtscreenpluspad')) {
        throw 'Invalid saved input profile.'
    }
    $arguments = @('modifyvm', $Identity, '--keyboard', $Profile.Keyboard, '--mouse', $Profile.Mouse)
    foreach ($key in @('OHCI', 'EHCI', 'XHCI', 'Acceleration3D')) {
        if ($Profile.$key -notin @('on', 'off')) { throw 'Invalid saved controller/display profile.' }
        $arguments += @($Flags[$key], $Profile.$key)
    }
    $null = Invoke-VBox -Arguments $arguments
}

function Assert-Stopped($Info) {
    if ($Info['VMState'] -ne 'poweroff') {
        throw 'The VM must be fully powered off first. Running, paused and saved-state VMs are left unchanged.'
    }
}

function Assert-Profile($Actual, $Expected) {
    foreach ($key in @('Keyboard', 'Mouse', 'OHCI', 'EHCI', 'XHCI', 'Acceleration3D')) {
        if ($Actual.$key -ne $Expected.$key) { throw ('Could not verify setting: {0}' -f $key) }
    }
}

function Invoke-DhampirInputRepair([string]$Name, [string]$RestorePath, [switch]$PlanOnly) {
    $script:VBoxManage = Find-VBoxManage
    $version = Invoke-VBox -Arguments @('--version')
    $flags = Get-ModifyFlags
    if ($RestorePath) {
        $saved = Get-Content -LiteralPath $RestorePath -Raw | ConvertFrom-Json
        $guid = [guid]::Empty
        if ($saved.Schema -ne 1 -or -not [guid]::TryParse([string]$saved.VMId, [ref]$guid)) { throw 'Invalid undo record.' }
        $identity = $guid.ToString()
        $info = Get-VMInfo $identity
        Assert-Stopped $info
        Assert-FilterIdentity @(Get-FilterStates $info['CfgFile']) @($saved.BeforeFilters)
        if ($PlanOnly) { Write-Host 'Plan: restore saved input/USB/display settings and USB filter activation. No changes made.'; return }
        Set-InputProfile $identity $saved.Before $flags
        Set-FilterStates $identity @($saved.BeforeFilters)
        $info = Get-VMInfo $identity
        Assert-Stopped $info
        Assert-Profile (Get-InputProfile $info['CfgFile']) $saved.Before
        Write-Host 'Original input, USB filters/controllers and 3D settings restored. The VM is still stopped.'
        return
    }
    $machine = Select-RepairVM $Name
    $info = Get-VMInfo $machine.Id
    Assert-Stopped $info
    $before = Get-InputProfile $info['CfgFile']
    $beforeFilters = @(Get-FilterStates $info['CfgFile'])
    $disabledFilters = @($beforeFilters | ForEach-Object { [pscustomobject]@{ Index = $_.Index; Signature = $_.Signature; Active = 'no' } })
    $target = [pscustomobject]@{ Keyboard = 'ps2'; Mouse = 'ps2'; OHCI = 'off'; EHCI = 'off'; XHCI = 'off'; Acceleration3D = 'off' }
    Write-Host ('VM: {0}; VirtualBox: {1}' -f $machine.Name, $version)
    if ($PlanOnly) { Write-Host 'Plan: PS/2 input; VM USB filters/controllers off; 3D acceleration off. No changes made.'; return }
    $backupName = 'backup-{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), ([guid]::NewGuid().ToString('N').Substring(0,6))
    $backup = Join-Path $script:RepairRoot $backupName
    $null = New-Item -ItemType Directory -Path $backup
    Copy-Item -LiteralPath $info['CfgFile'] -Destination (Join-Path $backup 'original.vbox')
    Copy-Item -LiteralPath $script:RepairScript -Destination (Join-Path $backup 'Repair-DhampirOSInput.ps1')
    $state = [ordered]@{ Schema = 1; VMId = $machine.Id; VMName = $machine.Name; VirtualBox = $version; Before = $before; BeforeFilters = $beforeFilters; Applied = $target }
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backup 'state.json') -Encoding UTF8
    $undo = @('@echo off', 'setlocal', 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair-DhampirOSInput.ps1" -RestoreFrom "%~dp0state.json"', 'pause') -join "`r`n"
    [System.IO.File]::WriteAllText((Join-Path $backup 'Undo.cmd'), $undo + "`r`n", [System.Text.Encoding]::ASCII)
    try {
        # Recheck after backup, before changing the selected VM settings.
        Assert-Stopped (Get-VMInfo $machine.Id)
        Set-InputProfile $machine.Id $target $flags
        Set-FilterStates $machine.Id $disabledFilters
        $after = Get-VMInfo $machine.Id
        Assert-Stopped $after
        Assert-Profile (Get-InputProfile $after['CfgFile']) $target
    } catch {
        $failure = $_.Exception.Message
        try {
            Assert-Stopped (Get-VMInfo $machine.Id)
            Set-InputProfile $machine.Id $before $flags
            Set-FilterStates $machine.Id $beforeFilters
            $rollbackInfo = Get-VMInfo $machine.Id
            Assert-Profile (Get-InputProfile $rollbackInfo['CfgFile']) $before
            Write-Host 'Repair failed; original settings were restored.'
        } catch { Write-Host ('Automatic restore did not complete. Backup and Undo are at: {0}' -f $backup) }
        throw $failure
    }
    Write-Host ''
    Write-Host 'Applied and verified: PS/2 keyboard/mouse; VM USB filters/controllers off; 3D acceleration off.'
    Write-Host 'Windows Bluetooth, other VMs, virtual disks and the ISO were left unchanged.'
    Write-Host ('Backup and Undo.cmd: {0}' -f $backup)
    Write-Host 'The VM is still stopped. Test it in a normal window; Right Ctrl releases captured input by default.'
    Write-Host 'This is a compatibility mitigation. It does not establish the cause of a Windows freeze.'
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-DhampirInputRepair -Name $VM -RestorePath $RestoreFrom -PlanOnly:$WhatIf }
    catch { Write-Host ('Repair stopped: {0}' -f $_.Exception.Message); exit 1 }
}
