# AI-Assisted. Basic launcher integration checks with a mock CLI, not a real VM.
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
. (Join-Path $repository 'tools\windows\Start-DhampirOS.ps1')
$scratch = Join-Path ([System.IO.Path]::GetTempPath()) ('dhampir-launch-test-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $scratch
$script:MockConfig = Join-Path $scratch 'Live.vbox'
$script:TestId = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
$script:Exists = $false
$script:Marker = ''
$script:Controller = $false
$script:Running = ''
$script:Commands = New-Object 'System.Collections.Generic.List[string]'

# The real hash validator must reject a short/incorrect ISO before any VM call.
$invalidIso = Join-Path $scratch 'bad.iso'
'invalid' | Set-Content -LiteralPath $invalidIso
$rejected = $false
try { Find-ReviewedIso $invalidIso 6>$null } catch { $rejected = $true }
if (-not $rejected) { throw 'Incorrect ISO was accepted.' }

function Find-VBoxManage { return 'mock-only' }
function Find-ReviewedIso([string]$RequestedPath) { return (Join-Path $scratch 'reviewed.iso') }
function Invoke-VBox([string[]]$Arguments) {
    $script:Commands.Add(($Arguments -join ' '))
    switch ($Arguments[0]) {
        'list' {
            if ($Arguments[1] -eq 'runningvms') { return $script:Running }
            if ($script:Exists) { return ('"DhampirOS USB Live" {{{0}}}' -f $script:TestId) }
            return ''
        }
        'createvm' {
            $script:Exists = $true
            '<VirtualBox xmlns="http://www.virtualbox.org/"><Machine><Hardware><CPU count="1"/><Memory RAMSize="128"/><HID/><Display/><USB><Controllers/><DeviceFilters/></USB></Hardware></Machine></VirtualBox>' | Set-Content -LiteralPath $script:MockConfig -Encoding UTF8
            return ''
        }
        'setextradata' { $script:Marker = $Arguments[3]; return '' }
        'getextradata' { return ('Value: ' + $script:Marker) }
        'showvminfo' {
            if ($Arguments[1] -ne $script:TestId) { throw 'Wrong VM queried.' }
            $text = ('CfgFile="{0}"' -f $script:MockConfig.Replace('\', '\\')) + "`nVMState=`"poweroff`""
            if ($script:Controller) { $text += "`nstoragecontrollername0=`"DhampirOS Optical`"" }
            return $text
        }
        'modifyvm' {
            if ($Arguments[1] -eq '--help') { return '--mouse --keyboard --usb-ohci --usb-ehci --usb-xhci --accelerate-3d' }
            if ($Arguments[1] -ne $script:TestId) { throw 'Wrong VM modified.' }
            if ($Arguments -contains '--mouse') {
                $xml = New-Object System.Xml.XmlDocument
                $xml.Load($script:MockConfig)
                $hid = $xml.SelectSingleNode('//*[local-name()="HID"]')
                $hid.SetAttribute('Pointing', 'PS2Mouse')
                $hid.SetAttribute('Keyboard', 'PS2Keyboard')
                $xml.Save($script:MockConfig)
            }
            return ''
        }
        'storagectl' { $script:Controller = $true; return '' }
        'storageattach' {
            if ($Arguments -notcontains 'dvddrive') { throw 'The launcher must attach only a virtual DVD.' }
            return ''
        }
        'startvm' {
            Assert-Profile (Get-InputProfile $script:MockConfig) ([pscustomobject]@{
                Keyboard = 'ps2'; Mouse = 'ps2'; OHCI = 'off'; EHCI = 'off'; XHCI = 'off'; Acceleration3D = 'off'
            })
            return ''
        }
        default { throw ('Unexpected command: ' + $Arguments[0]) }
    }
}

Start-DhampirLive '' 6>$null
if (@($script:Commands | Where-Object { $_ -like 'createvm*' }).Count -ne 1 -or @($script:Commands | Where-Object { $_ -like 'startvm*' }).Count -ne 1) { throw 'Create/start sequence failed.' }
if (@($script:Commands | Where-Object { $_ -match 'createmedium|hostonly|usbfilter add|unregistervm|delete' }).Count -gt 0) { throw 'Unexpected destructive or storage operation.' }
Start-DhampirLive '' 6>$null
if (@($script:Commands | Where-Object { $_ -like 'createvm*' }).Count -ne 1 -or @($script:Commands | Where-Object { $_ -like 'storagectl*' }).Count -ne 1) { throw 'Repeated launch created duplicate configuration.' }

$before = $script:Commands.Count
$script:Marker = 'someone-elses-vm'
$blocked = $false
try { Start-DhampirLive '' 6>$null } catch { $blocked = $true }
if (-not $blocked -or @($script:Commands | Select-Object -Skip $before | Where-Object { $_ -match '^(modifyvm|storageattach|startvm)' }).Count -gt 0) { throw 'An unowned VM was changed.' }

$script:Running = '"Other Linux VM" {11111111-2222-3333-4444-555555555555}'
$before = $script:Commands.Count
$blocked = $false
try { Start-DhampirLive '' 6>$null } catch { $blocked = $true }
if (-not $blocked -or @($script:Commands | Select-Object -Skip $before | Where-Object { $_ -match '^(createvm|modifyvm|storageattach|startvm)' }).Count -gt 0) { throw 'Other running guests were not respected.' }
Write-Host 'PASS: wrong-ISO refusal; dedicated VM creation/reuse; ownership guard; PS/2 and USB isolation before start; virtual DVD only; running-guest guard.'
Write-Host ('Fixture evidence: {0}' -f $scratch)
