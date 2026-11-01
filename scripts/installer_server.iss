; ============================================================
; Inno Setup script — Server POS Kasirin (LAN)
; Compiled with: ISCC.exe
; Build entry: python scripts/build_server_installer.py
;
; Ini installer SERVER, bukan aplikasi kasir.
;   Kasirin.exe       -> aplikasi kasir (klien), dipasang di tiap PC kasir
;   KasirinServer.exe -> server LAN, dipasang di SATU PC toko
; ============================================================

#ifndef AppVersion
#define AppVersion "0.5.0"
#endif
#ifndef SourceDir
#define SourceDir "dist\KasirinServer"
#endif
#ifndef OutputDir
#define OutputDir "build\installer_server"
#endif

[Setup]
AppName=Kasirin Server
AppVersion={#AppVersion}
AppPublisher=AnjaySoft Dev
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=
; Server dipasang per-mesin karena harus hidup terus dan dibuka admin toko.
DefaultDirName={autopf}\Kasirin Server
DefaultGroupName=Kasirin Server
AllowNoIcons=yes
LicenseFile=
OutputDir={#OutputDir}
OutputBaseFilename=KasirinServer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline dialog
UninstallDisplayIcon={app}\KasirinServer.exe
ChangesAssociations=no
SetupIconFile=
UninstallIconFile={app}\KasirinServer.exe
MinVersion=6.1
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
; Versi ditampilkan di Properties > Details, supaya admin toko bisa
; membedakan build lama dan baru saat menelepon dukungan.
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Kasirin Server
VersionInfoCompany=AnjaySoft Dev
VersionInfoDescription=Server POS Kasirin (LAN)

[Dirs]
Name: "{app}"; Permissions: users-full

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Jalankan Server Kasirin"; Filename: "{app}\KasirinServer.exe"
Name: "{group}\Buka Folder Data Server"; Filename: "{app}\KasirinServer.exe"; Parameters: "--open-data"
Name: "{group}\Uninstall Kasirin Server"; Filename: "{uninstallexe}"

[Run]
; Server dijalankan manual oleh admin toko, bukan otomatis setelah install:
; alamat LAN dan firewall perlu dijelaskan dulu.
Filename: "{app}\KasirinServer.exe"; Description: "{cm:LaunchProgram,Server Kasirin}"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM KasirinServer.exe /F"; Flags: runascurrentuser; RunOnceId: "TerminateKasirinServer"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
