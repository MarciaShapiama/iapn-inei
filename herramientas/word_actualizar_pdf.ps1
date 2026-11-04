# Abre un .docx en Microsoft Word, actualiza el índice y los campos, guarda y exporta a PDF.
# Uso: powershell -File herramientas\word_actualizar_pdf.ps1 -Docx ruta.docx [-Pdf ruta.pdf]
param([Parameter(Mandatory=$true)][string]$Docx, [string]$Pdf = "")
$Docx = (Resolve-Path $Docx).Path
if (-not $Pdf) { $Pdf = [IO.Path]::ChangeExtension($Docx, ".pdf") }
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  $d = $w.Documents.Open($Docx, $false, $false)
  foreach ($t in $d.TablesOfContents) { $t.Update() }
  $d.Fields.Update() | Out-Null
  foreach ($t in $d.TablesOfContents) { $t.Update() }
  $d.Save()
  $d.ExportAsFixedFormat($Pdf, 17)   # 17 = wdExportFormatPDF
  "paginas: " + $d.ComputeStatistics(2)
  $d.Close($false)
} finally { $w.Quit() }
"pdf: $Pdf"
