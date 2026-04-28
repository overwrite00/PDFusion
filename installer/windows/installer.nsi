; PDFusion — NSIS Installer Script
; Uso: makensis /DVERSION=0.1.0 installer.nsi

!ifndef VERSION
  !define VERSION "0.1.0"
!endif

!define APP_NAME     "PDFusion"
!define APP_EXE      "PDFusion.exe"
!define OUTPUT_FILE  "PDFusion-${VERSION}-windows-setup.exe"
!define INSTALL_DIR  "$PROGRAMFILES64\PDFusion"
!define REG_KEY      "Software\Microsoft\Windows\CurrentVersion\Uninstall\PDFusion"
!define DIST_DIR     "..\..\dist\PDFusion"

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

; -----------------------------------------------------------------------
; UI
; -----------------------------------------------------------------------
!define MUI_ABORTWARNING
!define MUI_ICON          "..\..\assets\icons\app.ico"
!define MUI_UNICON        "..\..\assets\icons\app.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH

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
  File /r "${DIST_DIR}\*.*"

  ; Shortcut menu Start
  CreateDirectory "$SMPROGRAMS\PDFusion"
  CreateShortcut  "$SMPROGRAMS\PDFusion\PDFusion.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut  "$SMPROGRAMS\PDFusion\Disinstalla PDFusion.lnk" "$INSTDIR\Uninstall.exe"

  ; Shortcut Desktop (opzionale — chiedi all'utente)
  MessageBox MB_YESNO "Creare un collegamento sul Desktop?" IDNO skip_desktop
    CreateShortcut "$DESKTOP\PDFusion.lnk" "$INSTDIR\${APP_EXE}"
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
