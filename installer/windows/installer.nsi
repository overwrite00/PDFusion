; PDFusion — NSIS Installer Script
; Uso: makensis /DVERSION=0.1.0 installer.nsi

!ifndef VERSION
  !define VERSION "0.2.9"
!endif

!define APP_NAME     "PDFusion"
!define APP_EXE      "PDFusion.exe"
!define OUTPUT_FILE  "${__FILEDIR__}\PDFusion-${VERSION}-windows-setup.exe"
!define INSTALL_DIR  "$PROGRAMFILES64\PDFusion"
!define REG_KEY      "Software\Microsoft\Windows\CurrentVersion\Uninstall\PDFusion"
; Use the icon embedded in the EXE. PyInstaller 6.x places bundled datas under
; $INSTDIR\_internal\..., so the old "$INSTDIR\assets\icons\app.ico" path did
; not exist at install time and shortcuts fell back to a blank white icon.
; The EXE has the icon embedded by PyInstaller (icon= in PDFusion.spec), so we
; reference it directly with icon index 0 in the CreateShortcut calls below.
!define APP_ICON     "$INSTDIR\${APP_EXE}"

; DIST_DIR is provided via /DDIST_DIR=<absolute_path> from GitHub Actions build script
; For local builds without the parameter, fallback to relative path
!ifndef DIST_DIR
  !define DIST_DIR   "${__FILEDIR__}\dist_staging"
!endif

; -----------------------------------------------------------------------
; UI — MUI_ICON / MUI_UNICON MUST be defined BEFORE "!include MUI2.nsh".
; MUI2.nsh applies "Icon ${MUI_ICON}" / "UninstallIcon ${MUI_UNICON}" to the
; compiled EXE the moment it is included; if MUI_ICON is still undefined at
; that point, MUI2.nsh silently falls back to its own default NSIS icon
; (or none), which is exactly why the setup.exe kept showing a blank/white
; icon even though the icon file itself was correct. See CLAUDE.md.
; -----------------------------------------------------------------------
!define MUI_ABORTWARNING
!define MUI_ICON          "..\..\assets\icons\app.ico"
!define MUI_UNICON        "..\..\assets\icons\app.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH

; Includi moderni UI
!include "MUI2.nsh"

; -----------------------------------------------------------------------
; Configurazione generale
; -----------------------------------------------------------------------
Name            "${APP_NAME} ${VERSION}"
OutFile         "${OUTPUT_FILE}"
InstallDir      "${INSTALL_DIR}"
InstallDirRegKey HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor   /SOLID lzma

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "English"

; -----------------------------------------------------------------------
; Sezione principale
; -----------------------------------------------------------------------
Section "PDFusion (obbligatorio)" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  ; Copy main executable
  File "${DIST_DIR}\PDFusion.exe"
  ; Copy all support files and libraries (exclude duplicate .exe)
  File /r /x "*.exe" "${DIST_DIR}\*.*"

  ; Shortcut menu Start
  CreateDirectory "$SMPROGRAMS\PDFusion"
  CreateShortcut  "$SMPROGRAMS\PDFusion\PDFusion.lnk" "$INSTDIR\${APP_EXE}" "" "${APP_ICON}" 0
  CreateShortcut  "$SMPROGRAMS\PDFusion\Disinstalla PDFusion.lnk" "$INSTDIR\Uninstall.exe"

  ; Shortcut Desktop (opzionale — chiedi all'utente)
  MessageBox MB_YESNO "Creare un collegamento sul Desktop?" IDNO skip_desktop
    CreateShortcut "$DESKTOP\PDFusion.lnk" "$INSTDIR\${APP_EXE}" "" "${APP_ICON}" 0
  skip_desktop:

  ; Registrazione uninstaller
  WriteRegStr   HKLM "${REG_KEY}" "DisplayName"      "${APP_NAME}"
  WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"    "${VERSION}"
  WriteRegStr   HKLM "${REG_KEY}" "Publisher"         "PDFusion"
  WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"   "$INSTDIR"
  WriteRegStr   HKLM "${REG_KEY}" "UninstallString"   "$INSTDIR\Uninstall.exe"
  WriteRegDWORD HKLM "${REG_KEY}" "NoModify"          1
  WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"          1

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; -----------------------------------------------------------------------
; Associazione file .pdf (opzionale)
; -----------------------------------------------------------------------
Section "Associa file .pdf a PDFusion" SecFileAssoc
  WriteRegStr HKCR ".pdf\OpenWithProgids" "PDFusion.pdf" ""
  WriteRegStr HKCR "PDFusion.pdf"         ""              "File PDF"
  WriteRegStr HKCR "PDFusion.pdf\shell\open\command" "" '"$INSTDIR\${APP_EXE}" "%1"'
SectionEnd

; -----------------------------------------------------------------------
; Disinstallazione
; -----------------------------------------------------------------------
Section "Uninstall"
  ; Rimuovi file installati
  RMDir /r "$INSTDIR"

  ; Rimuovi shortcut
  Delete "$SMPROGRAMS\PDFusion\PDFusion.lnk"
  Delete "$SMPROGRAMS\PDFusion\Disinstalla PDFusion.lnk"
  RMDir  "$SMPROGRAMS\PDFusion"
  Delete "$DESKTOP\PDFusion.lnk"

  ; Rimuovi chiavi registro
  DeleteRegKey HKLM "${REG_KEY}"
  DeleteRegKey HKCR "PDFusion.pdf"
SectionEnd
