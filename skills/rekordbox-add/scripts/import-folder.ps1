# Import one folder into the running rekordbox: File > Import > Import Folder.
# Usage: powershell.exe -File import-folder.ps1 -Folder 'C:\Users\sneak\Music\DJ\Artist'
# Exit: 0 imported, 1 UI step failed, 2 bad folder, 3 rekordbox not running.
param(
  [Parameter(Mandatory = $true)][string]$Folder,
  # Centre of the "File" menu in logical pixels from the window's client origin.
  # rekordbox is a JUCE app and exposes no menu to UI Automation, so this one
  # click is positional; everything after it is keyboard plus the standard
  # Windows folder dialog. Adjust here if a rekordbox update moves the menu bar.
  [int]$MenuX = 23,
  [int]$MenuY = 11
)
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public class W {
  public delegate bool EnumCb(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumCb cb, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
  public static uint PidOf(IntPtr h) { uint p; GetWindowThreadProcessId(h, out p); return p; }
  public static uint PidAt(int x, int y) { var pt = new POINT(); pt.X = x; pt.Y = y; return PidOf(WindowFromPoint(pt)); }
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  public struct RECT { public int L, T, R, B; }
  // Process.MainWindowHandle can point at a short-lived window right after an
  // import, so take the largest visible top-level window: the real main window.
  public static IntPtr MainWindow(uint pid) {
    IntPtr best = IntPtr.Zero; long bestArea = 0;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); RECT r;
      if (p == pid && IsWindowVisible(h) && GetWindowRect(h, out r)) {
        long a = (long)(r.R - r.L) * (r.B - r.T); if (a > bestArea) { bestArea = a; best = h; } }
      return true; }, IntPtr.Zero);
    return best;
  }
  public static RECT RectOf(IntPtr h) { RECT r; GetWindowRect(h, out r); return r; }
  // Largest visible rekordbox window other than the main one and `skip`: an open
  // menu (its drop-shadow windows are thin strips, so they never win).
  public static IntPtr LargestPopup(uint pid, IntPtr main, IntPtr skip) {
    IntPtr best = IntPtr.Zero; long bestArea = 0;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); RECT r;
      if (p == pid && h != main && h != skip && IsWindowVisible(h) && GetWindowRect(h, out r)) {
        long a = (long)(r.R - r.L) * (r.B - r.T); if (a > bestArea) { bestArea = a; best = h; } }
      return true; }, IntPtr.Zero);
    return best;
  }
  // JUCE menus are separate top-level windows, so an open menu shows up here.
  public static int VisibleWindows(uint pid) {
    int n = 0;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p); if (p == pid && IsWindowVisible(h)) n++; return true; }, IntPtr.Zero);
    return n;
  }
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, UIntPtr e);
  [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindow(string c, string t);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, System.Text.StringBuilder l);
  public static string TextOf(IntPtr h) { var sb = new System.Text.StringBuilder(1024); SendMessage(h, 0x000D, (IntPtr)1024, sb); return sb.ToString(); }
  public struct POINT { public int X, Y; }
}
"@

function Fail([int]$code, [string]$msg) { [Console]::Error.WriteLine("error: $msg"); exit $code }
function Get-Dialog { [W]::FindWindow('#32770', 'Import Folder') }
function Wait-Until([scriptblock]$cond, [int]$ms) {
  for ($t = 0; $t -lt $ms; $t += 200) { if (& $cond) { return $true }; Start-Sleep -Milliseconds 200 }
  return [bool](& $cond)
}

[W]::SetProcessDPIAware() | Out-Null

$rb = Get-Process rekordbox -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $rb) { Fail 3 'rekordbox is not running' }
if (-not (Test-Path -LiteralPath $Folder -PathType Container)) { Fail 2 "folder not found: $Folder" }
if ((Get-Dialog) -ne [IntPtr]::Zero) { Fail 1 'an Import Folder dialog is already open in rekordbox; close it and retry' }

$rbPid = [uint32]$rb.Id
$h = [W]::MainWindow($rbPid)
if ($h -eq [IntPtr]::Zero) { Fail 3 'rekordbox is running but has no visible window' }
# Windows ignores SetForegroundWindow from a background process unless a key
# was just pressed, so tap Alt first, then confirm rekordbox really is in front.
function Focus-Rekordbox {
  if ([W]::IsIconic($h)) { [W]::ShowWindow($h, 9) | Out-Null }
  [W]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [W]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
  [W]::SetForegroundWindow($h) | Out-Null
  Wait-Until { [W]::PidOf([W]::GetForegroundWindow()) -eq $rbPid } 1500
}
if (-not (Focus-Rekordbox)) { Fail 1 'could not bring rekordbox to the front' }
Start-Sleep -Milliseconds 400

$pt = New-Object W+POINT
if (-not [W]::ClientToScreen($h, [ref]$pt)) { Fail 1 'could not locate the rekordbox window' }
$scale = [W]::GetDpiForWindow($h) / 96.0
# Only the main window visible = no menu open. Judge "open" absolutely, not
# against a starting count: a click rekordbox processed late can leave a menu
# open, and clicking File again would just toggle it shut.
function Close-Menus {
  for ($i = 0; $i -lt 5; $i++) {
    if ([W]::VisibleWindows($rbPid) -le 1) { return $true }
    [System.Windows.Forms.SendKeys]::SendWait('{ESC}'); Start-Sleep -Milliseconds 300
  }
  [W]::VisibleWindows($rbPid) -le 1
}

# Open File > Import > Import Folder with clicks, confirming each step before the
# next. rekordbox drops input while it analyses freshly imported tracks, and an
# unverified click or key can land on the wrong item (or in the main window).
# Row offsets are logical px from each menu window's top edge.
$importRowY = 14; $folderRowY = 39; $itemX = 40
function Click-At([int]$px, [int]$py) {
  # Never click unless rekordbox is in front and owns that exact pixel.
  if ([W]::PidOf([W]::GetForegroundWindow()) -ne $rbPid -or [W]::PidAt($px, $py) -ne $rbPid) { return $false }
  [W]::SetCursorPos($px, $py) | Out-Null
  [W]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero); [W]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
  $true
}
$x = $pt.X + [int]($MenuX * $scale); $y = $pt.Y + [int]($MenuY * $scale)
$dlgOpen = $false; $stage = 'focusing rekordbox'
for ($try = 1; $try -le 6 -and -not $dlgOpen; $try++) {
  if ($try -gt 1) { Start-Sleep -Seconds 3 }
  if ((Get-Dialog) -ne [IntPtr]::Zero) { $dlgOpen = $true; break }
  if (-not (Focus-Rekordbox) -or -not (Close-Menus)) { continue }

  $stage = 'clicking File'
  if (-not (Click-At $x $y)) { continue }                                     # File
  $stage = 'waiting for the File menu'
  if (-not (Wait-Until { [W]::VisibleWindows($rbPid) -gt 1 } 3000)) { continue }
  Start-Sleep -Milliseconds 300
  $menu = [W]::LargestPopup($rbPid, $h, [IntPtr]::Zero); $m = [W]::RectOf($menu)

  $n = [W]::VisibleWindows($rbPid); $stage = 'clicking Import'

  if (-not (Click-At ($m.L + [int]($itemX * $scale)) ($m.T + [int]($importRowY * $scale)))) { continue }   # Import
  $stage = 'waiting for the Import submenu'
  if (-not (Wait-Until { [W]::VisibleWindows($rbPid) -gt $n } 3000)) { continue }
  Start-Sleep -Milliseconds 300
  $sub = [W]::LargestPopup($rbPid, $h, $menu); $r = [W]::RectOf($sub)
  $stage = "checking the submenu position (menu L$($m.L) T$($m.T) R$($m.R); sub L$($r.L) T$($r.T))"
  # The Import submenu opens flush against the File menu's right edge; anything else is not it.
  if ([Math]::Abs($r.L - $m.R) -gt [int](10 * $scale) -or [Math]::Abs($r.T - $m.T) -gt [int](10 * $scale)) { continue }

  if (-not (Click-At ($r.L + [int]($itemX * $scale)) ($r.T + [int]($folderRowY * $scale)))) { continue }  # Import Folder
  $stage = 'waiting for the Import Folder dialog'
  $dlgOpen = Wait-Until { (Get-Dialog) -ne [IntPtr]::Zero } 10000
}
if (-not $dlgOpen) {
  if ((Focus-Rekordbox)) { Close-Menus | Out-Null }
  Fail 1 "could not open File > Import > Import Folder after 6 tries; last stuck at: $stage (rekordbox busy, another window in front, or its menus moved: see -MenuX/-MenuY and the row offsets)"
}
$dlg = Get-Dialog

# Folder box (id 1152) takes the full path; "Select Folder" is IDOK (1), Cancel is IDCANCEL (2).
# Never press Select Folder until the box provably holds $Folder: with the box
# empty or stale, the dialog selects the folder it is showing - usually the whole
# Music\DJ library - and rekordbox imports all of it.
function Cancel-Dialog { $d = Get-Dialog; if ($d -ne [IntPtr]::Zero) { [W]::PostMessage([W]::GetDlgItem($d, 2), 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null } }
$pathSet = Wait-Until {
  $e = [W]::GetDlgItem($dlg, 1152); $ok = [W]::GetDlgItem($dlg, 1)
  if ($e -eq [IntPtr]::Zero -or $ok -eq [IntPtr]::Zero) { return $false }
  [W]::SendMessage($e, 0x000C, [IntPtr]::Zero, $Folder) | Out-Null   # WM_SETTEXT
  Start-Sleep -Milliseconds 300
  [W]::TextOf($e) -eq $Folder
} 10000
if (-not $pathSet) { Cancel-Dialog; Fail 1 "could not put $Folder into the Import Folder dialog; cancelled it, nothing imported" }
Start-Sleep -Milliseconds 300
if ([W]::TextOf([W]::GetDlgItem($dlg, 1152)) -ne $Folder) { Cancel-Dialog; Fail 1 "the Folder box changed before Select Folder; cancelled it, nothing imported" }
[W]::PostMessage([W]::GetDlgItem($dlg, 1), 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null  # BM_CLICK

if (-not (Wait-Until { (Get-Dialog) -eq [IntPtr]::Zero } 10000)) {
  Cancel-Dialog
  Fail 1 "the Import Folder dialog did not accept $Folder; cancelled it, nothing imported"
}
"imported: $Folder"
exit 0
