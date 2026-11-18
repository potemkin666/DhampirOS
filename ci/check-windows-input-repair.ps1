# AI-Assisted. Basic host-side regression checks; no actual VirtualBox is run.
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
. (Join-Path $repository 'tools\windows\Repair-DhampirOSInput.ps1')
$scratch = Join-Path ([System.IO.Path]::GetTempPath()) ('dhampir-input-test-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $scratch
$script:RepairRoot = $scratch
$script:MockConfig = Join-Path $scratch 'Fixture.vbox'
$script:TestId = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
$script:TestState = 'poweroff'
$script:LegacyHelp = $false
$script:FailurePending = $false
$script:FilterFailurePending = $false
$script:CloneNames = $false
$script:AttachedIso = 'DhampirOS-0.1.0-alpha.1-amd64.iso'
$script:Mutations = New-Object 'System.Collections.Generic.List[string]'

function New-Fixture {
    @'
<VirtualBox xmlns="http://www.virtualbox.org/" version="1.20-windows"><Machine name="DhampirOS"><Hardware><CPU count="2"/><Memory RAMSize="2048"/><HID Pointing="USBTablet" Keyboard="USBKeyboard"/><Display controller="VMSVGA" accelerate3D="true"/><USB><Controllers><Controller name="xHCI" type="XHCI"/></Controllers><DeviceFilters><DeviceFilter name="Receiver" active="true" vendorId="1234" productId="5678"/><DeviceFilter name="Inactive" active="false" vendorId="abcd"/></DeviceFilters></USB><Network><Adapter slot="0" enabled="true"/></Network></Hardware></Machine></VirtualBox>
'@ | Set-Content -LiteralPath $script:MockConfig -Encoding UTF8
}

function Find-VBoxManage { return 'mock-only' }

function Invoke-VBox([string[]]$Arguments) {
    switch ($Arguments[0]) {
        '--version' { return '7.2.6r172322' }
        'list' {
            if ($script:CloneNames) { return ('"Base Linux" {11111111-2222-3333-4444-555555555555}', ('"Linux Clone" {{{0}}}' -f $script:TestId)) -join "`n" }
            return ('"DhampirOS" {{{0}}}' -f $script:TestId)
        }
        'showvminfo' {
            if ($Arguments[1] -ne $script:TestId) { return ('CfgFile="{0}"' -f $script:MockConfig.Replace('\', '\\')), 'VMState="poweroff"', 'Optical="Other.iso"' -join "`n" }
            return ('name="DhampirOS"', ('CfgFile="{0}"' -f $script:MockConfig.Replace('\', '\\')), ('VMState="{0}"' -f $script:TestState), ('Optical="{0}"' -f $script:AttachedIso)) -join "`n"
        }
        'modifyvm' {
            if ($Arguments[1] -eq '--help') {
                if ($script:LegacyHelp) { return '--keyboard --mouse --usb --usbehci --usbxhci --accelerate3d' }
                return '--keyboard --mouse --usb-ohci --usb-ehci --usb-xhci --accelerate-3d'
            }
            if ($Arguments[1] -ne $script:TestId) { throw 'Wrong VM mutated.' }
            $script:Mutations.Add(($Arguments -join ' '))
            $xml = New-Object System.Xml.XmlDocument
            $xml.Load($script:MockConfig)
            $hardware = $xml.SelectSingleNode('//*[local-name()="Hardware"]')
            $hid = $hardware.SelectSingleNode('*[local-name()="HID"]')
            $controllers = $hardware.SelectSingleNode('*[local-name()="USB"]/*[local-name()="Controllers"]')
            $controllers.RemoveAll()
            for ($index = 2; $index -lt $Arguments.Count; $index += 2) {
                $flag = $Arguments[$index]
                $value = $Arguments[$index + 1]
                switch -Regex ($flag) {
                    '^--keyboard$' { $type = 'PS2Keyboard'; if ($value -eq 'usb') { $type = 'USBKeyboard' }; $hid.SetAttribute('Keyboard', $type) }
                    '^--mouse$' { $type = 'PS2Mouse'; if ($value -eq 'usbtablet') { $type = 'USBTablet' }; $hid.SetAttribute('Pointing', $type) }
                    '^--accelerate-?3d$' { $hardware.SelectSingleNode('*[local-name()="Display"]').SetAttribute('accelerate3D', [string]($value -eq 'on').ToString().ToLowerInvariant()) }
                    '^--(usb(-ohci)?|usb-?ehci|usb-?xhci)$' {
                        if ($value -eq 'on') {
                            $type = 'OHCI'
                            if ($flag -match 'ehci') { $type = 'EHCI' }
                            if ($flag -match 'xhci') { $type = 'XHCI' }
                            $node = $xml.CreateElement('Controller', $xml.DocumentElement.NamespaceURI)
                            $node.SetAttribute('name', $type)
                            $node.SetAttribute('type', $type)
                            $null = $controllers.AppendChild($node)
                        }
                    }
                    default { throw ('Unexpected option: ' + $flag) }
                }
            }
            $xml.Save($script:MockConfig)
            if ($script:FailurePending) { $script:FailurePending = $false; throw 'Simulated mutation failure after partial apply.' }
            return ''
        }
        'usbfilter' {
            if ($Arguments[4] -ne $script:TestId) { throw 'Wrong VM filter mutated.' }
            $script:Mutations.Add(($Arguments -join ' '))
            $xml = New-Object System.Xml.XmlDocument
            $xml.Load($script:MockConfig)
            $filters = @($xml.SelectNodes('//*[local-name()="DeviceFilter"]'))
            $filters[[int]$Arguments[2]].SetAttribute('active', [string]($Arguments[6] -eq 'yes').ToString().ToLowerInvariant())
            $xml.Save($script:MockConfig)
            if ($script:FilterFailurePending) { $script:FilterFailurePending = $false; throw 'Simulated filter failure after partial apply.' }
            return ''
        }
        default { throw ('Unexpected command: ' + $Arguments[0]) }
    }
}

function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }

New-Fixture
$script:CloneNames = $true
Assert-True ((Select-RepairVM '').Id -eq $script:TestId) 'A renamed VM with the DhampirOS ISO was not detected.'
$script:AttachedIso = 'Renamed.iso'
function Read-Host { return '2' }
Assert-True ((Select-RepairVM '').Id -eq $script:TestId) 'Ambiguous VM selection failed.'
$script:CloneNames = $false
$script:AttachedIso = 'DhampirOS-0.1.0-alpha.1-amd64.iso'
$original = Get-InputProfile $script:MockConfig
$originalFilters = @(Get-FilterStates $script:MockConfig)
$originalHash = (Get-FileHash -LiteralPath $script:MockConfig).Hash
Invoke-DhampirInputRepair -PlanOnly 6>$null
Assert-True ($script:Mutations.Count -eq 0) 'Plan-only mutated a VM.'
Assert-True (@(Get-ChildItem -LiteralPath $scratch -Directory).Count -eq 0) 'Plan-only wrote backups.'

foreach ($state in @('running', 'paused', 'saved')) {
    $script:TestState = $state
    $refused = $false
    try { Invoke-DhampirInputRepair 6>$null } catch { $refused = $true }
    Assert-True $refused ('VM state was not refused: ' + $state)
    Assert-True ($script:Mutations.Count -eq 0) 'A non-stopped VM was mutated.'
}
$script:TestState = 'poweroff'
Invoke-DhampirInputRepair 6>$null
$applied = Get-InputProfile $script:MockConfig
Assert-True ($applied.Keyboard -eq 'ps2' -and $applied.Mouse -eq 'ps2' -and $applied.XHCI -eq 'off' -and $applied.Acceleration3D -eq 'off') 'Compatibility profile failed.'
Assert-True (@(Get-FilterStates $script:MockConfig | Where-Object { $_.Active -eq 'yes' }).Count -eq 0) 'USB auto-capture stayed active.'
$backup = Get-ChildItem -LiteralPath $scratch -Directory | Select-Object -First 1
Assert-True ((Get-FileHash -LiteralPath (Join-Path $backup.FullName 'original.vbox')).Hash -eq $originalHash) 'Original configuration backup was not exact.'
Assert-True (Test-Path -LiteralPath (Join-Path $backup.FullName 'Undo.cmd')) 'Undo launcher missing.'
Invoke-DhampirInputRepair -RestorePath (Join-Path $backup.FullName 'state.json') 6>$null
Assert-Profile (Get-InputProfile $script:MockConfig) $original
$restoredFilters = @(Get-FilterStates $script:MockConfig)
Assert-True ($restoredFilters[0].Active -eq 'yes' -and $restoredFilters[1].Active -eq 'no') 'Undo did not preserve original filter activation.'

New-Fixture
$script:FailurePending = $true
$failed = $false
try { Invoke-DhampirInputRepair 6>$null } catch { $failed = $true }
Assert-True $failed 'Simulated failure was hidden.'
Assert-Profile (Get-InputProfile $script:MockConfig) $original
Assert-True (@(Get-FilterStates $script:MockConfig)[0].Active -eq 'yes') 'Failure recovery did not restore filters.'

$script:FilterFailurePending = $true
$failed = $false
try { Invoke-DhampirInputRepair 6>$null } catch { $failed = $true }
Assert-True $failed 'Simulated filter failure was hidden.'
Assert-Profile (Get-InputProfile $script:MockConfig) $original
Assert-True (@(Get-FilterStates $script:MockConfig)[0].Active -eq 'yes') 'Partially changed filter activation was not restored.'

$script:LegacyHelp = $true
Invoke-DhampirInputRepair 6>$null
Assert-True (@($script:Mutations | Where-Object { $_ -match ' --usb off ' -and $_ -match ' --accelerate3d off' }).Count -gt 0) 'Legacy CLI option selection failed.'

# Reject an Undo whose filter identity no longer matches the current device.
$mismatch = @([pscustomobject]@{ Index = 0; Signature = 'changed'; Active = 'yes' })
$blocked = $false
try { Set-FilterStates $script:TestId $mismatch } catch { $blocked = $true }
Assert-True $blocked 'Changed filters were not refused.'
$currentXml = New-Object System.Xml.XmlDocument
$currentXml.Load($script:MockConfig)
Assert-True ($currentXml.SelectSingleNode('//*[local-name()="Adapter"]').GetAttribute('enabled') -eq 'true') 'Unrelated VM configuration changed.'

$currentXml.SelectSingleNode('//*[local-name()="DeviceFilters"]').RemoveAll()
$currentXml.Save($script:MockConfig)
Invoke-DhampirInputRepair 6>$null
$latestBackup = Get-ChildItem -LiteralPath $scratch -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
Invoke-DhampirInputRepair -RestorePath (Join-Path $latestBackup.FullName 'state.json') 6>$null
Assert-True (@(Get-FilterStates $script:MockConfig).Count -eq 0) 'Empty filter list did not survive repair and Undo.'

Write-Host 'PASS: VM selection; plan-only; powered-off guard; modern/legacy flags; filter isolation; exact backup; Undo; failure recovery; changed-filter refusal.'
Write-Host ('Fixture evidence: {0}' -f $scratch)
