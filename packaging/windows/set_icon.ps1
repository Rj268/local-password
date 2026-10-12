# Put the current local-password.ico on the installed Local Password app.
$ErrorActionPreference = "Stop"
Get-Process -Name LocalPassword -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
$dest = Join-Path $env:LOCALAPPDATA "Programs\Local Password"
$exe = Join-Path $dest "LocalPassword.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Local Password is not installed at $dest"
}

$icon = Join-Path $dest "local-password.ico"
$scriptRoot = $PSScriptRoot
$iconCandidates = @(
    (Join-Path $scriptRoot "local-password.ico"),
    (Join-Path $scriptRoot "..\..\dist\windows\LocalPassword\local-password.ico"),
    (Join-Path $dest "local-password.ico")
)
$iconSource = $null
foreach ($candidate in $iconCandidates) {
    $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($candidate)
    if (Test-Path -LiteralPath $resolved) {
        $iconSource = $resolved
        break
    }
}
if (-not $iconSource) {
    throw "local-password.ico was not found beside this script or in the install folder."
}
Copy-Item -LiteralPath $iconSource -Destination $icon -Force

$wsh = New-Object -ComObject WScript.Shell
foreach ($lnk in @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Local Password.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Local Password.lnk")
)) {
    if (-not (Test-Path -LiteralPath $lnk)) { continue }
    $shortcut = $wsh.CreateShortcut($lnk)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $dest
    $shortcut.WindowStyle = 1
    $shortcut.Description = "Local Password"
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Save()
}

# PyInstaller stores its archive after the normal Windows icon data. A plain
# icon rewrite drops that archive, so keep those bytes and put them back.
$repoExe = Join-Path $scriptRoot "..\..\dist\windows\LocalPassword\LocalPassword.exe"
$sourceExe = if (Test-Path -LiteralPath $repoExe) {
    (Resolve-Path -LiteralPath $repoExe).Path
} else {
    $exe
}
$work = Join-Path $env:TEMP "LocalPassword-with-icon.exe"
Copy-Item -LiteralPath $sourceExe -Destination $work -Force

function Test-PyiCookie([byte[]]$data) {
    if ($data.Length -lt 88) { return $false }
    $magic = [byte[]](0x4D, 0x45, 0x49, 0x0C, 0x0D, 0x0A, 0x0D, 0x0B)
    $at = $data.Length - 88
    for ($i = 0; $i -lt 8; $i++) {
        if ($data[$at + $i] -ne $magic[$i]) { return $false }
    }
    return $true
}
$original = [IO.File]::ReadAllBytes($work)
if (-not (Test-PyiCookie $original)) { throw "The program file has no archive to keep." }
$pkgLen = [BitConverter]::ToUInt32($original, $original.Length - 80)
$overlay = New-Object byte[] $pkgLen
[Buffer]::BlockCopy($original, $original.Length - $pkgLen, $overlay, 0, $pkgLen)

Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
public class LocalPasswordIconKeep {
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr BeginUpdateResource(string file, bool deleteExisting);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool UpdateResource(IntPtr handle, IntPtr type, IntPtr name, ushort lang, byte[] data, uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool EndUpdateResource(IntPtr handle, bool discard);
    public static void Apply(string exePath, string icoPath) {
        byte[] ico = File.ReadAllBytes(icoPath);
        if (ico.Length < 22 || BitConverter.ToUInt16(ico, 0) != 0 || BitConverter.ToUInt16(ico, 2) != 1)
            throw new InvalidDataException("The icon file is not an .ico.");
        int count = BitConverter.ToUInt16(ico, 4);
        byte[] group = new byte[6 + (count * 14)];
        group[2] = 1;
        group[4] = (byte)(count & 255);
        group[5] = (byte)((count >> 8) & 255);
        byte[][] images = new byte[count][];
        for (int i = 0; i < count; i++) {
            int entry = 6 + (i * 16);
            ushort planes = BitConverter.ToUInt16(ico, entry + 4);
            ushort bits = BitConverter.ToUInt16(ico, entry + 6);
            uint nbytes = BitConverter.ToUInt32(ico, entry + 8);
            uint offset = BitConverter.ToUInt32(ico, entry + 12);
            if (planes == 0) planes = 1;
            if (bits == 0) bits = 32;
            int slot = 6 + (i * 14);
            group[slot] = ico[entry];
            group[slot + 1] = ico[entry + 1];
            group[slot + 2] = ico[entry + 2];
            group[slot + 3] = ico[entry + 3];
            BitConverter.GetBytes(planes).CopyTo(group, slot + 4);
            BitConverter.GetBytes(bits).CopyTo(group, slot + 6);
            BitConverter.GetBytes(nbytes).CopyTo(group, slot + 8);
            BitConverter.GetBytes((ushort)(i + 1)).CopyTo(group, slot + 12);
            images[i] = new byte[nbytes];
            Buffer.BlockCopy(ico, (int)offset, images[i], 0, (int)nbytes);
        }
        IntPtr handle = BeginUpdateResource(exePath, false);
        if (handle == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        try {
            foreach (ushort lang in new ushort[] { 0, 1033 }) {
                if (!UpdateResource(handle, (IntPtr)14, (IntPtr)1, lang, group, (uint)group.Length))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                for (int i = 0; i < count; i++) {
                    if (!UpdateResource(handle, (IntPtr)3, (IntPtr)(i + 1), lang, images[i], (uint)images[i].Length))
                        throw new Win32Exception(Marshal.GetLastWin32Error());
                }
            }
        } catch {
            EndUpdateResource(handle, true);
            throw;
        }
        if (!EndUpdateResource(handle, false)) throw new Win32Exception(Marshal.GetLastWin32Error());
    }
}
"@
[LocalPasswordIconKeep]::Apply($work, $icon)
$patched = [IO.File]::ReadAllBytes($work)
if (-not (Test-PyiCookie $patched)) {
    $stream = [IO.File]::Open($work, [IO.FileMode]::Append, [IO.FileAccess]::Write)
    $stream.Write($overlay, 0, $overlay.Length)
    $stream.Close()
    $patched = [IO.File]::ReadAllBytes($work)
}
if (-not (Test-PyiCookie $patched)) {
    throw "The icon change would break the program, so the installed copy was left as it is."
}
Copy-Item -LiteralPath $work -Destination $exe -Force
$reg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalPassword"
if (Test-Path -LiteralPath $reg) {
    Set-ItemProperty -LiteralPath $reg -Name DisplayIcon -Value "$icon,0"
}
Write-Host "The Premium Emerald icon is on Local Password."
Start-Process -FilePath $exe
