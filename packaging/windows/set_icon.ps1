# Put the green key icon on the installed Local Password app.
$ErrorActionPreference = "Stop"
Get-Process -Name LocalPassword -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
$dest = Join-Path $env:LOCALAPPDATA "Programs\Local Password"
$exe = Join-Path $dest "LocalPassword.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Local Password is not installed at $dest"
}
$icon = Join-Path $dest "local-password.ico"
$iconBytes = [Convert]::FromBase64String(@"
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
"@)
[IO.File]::WriteAllBytes($icon, $iconBytes)

$wsh = New-Object -ComObject WScript.Shell
foreach ($lnk in @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Local Password.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Local Password.lnk")
)) {
    $shortcut = $wsh.CreateShortcut($lnk)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $dest
    $shortcut.WindowStyle = 1
    $shortcut.Description = "Local Password"
    $shortcut.IconLocation = $icon
    $shortcut.Save()
}

# PyInstaller stores its archive after the normal Windows icon data. A plain
# icon rewrite drops that archive, so keep those bytes and put them back.
$sourceExe = "C:\Users\<you>\passgen\dist\windows\LocalPassword\LocalPassword.exe"
if (-not (Test-Path -LiteralPath $sourceExe)) { $sourceExe = $exe }
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
    Set-ItemProperty -LiteralPath $reg -Name DisplayIcon -Value $icon
}
Write-Host "The green key icon is on Local Password."
Start-Process -FilePath $exe
