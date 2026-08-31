param(
    [Parameter(Mandatory = $true)]
    [string]$TextFile,
    [Parameter(Mandatory = $true)]
    [string]$OutputWav,
    [string]$VoiceName = "",
    [ValidateRange(-10, 10)]
    [int]$Rate = 0,
    [ValidateRange(0, 100)]
    [int]$Volume = 100
)

$ErrorActionPreference = "Stop"
$text = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($TextFile), [System.Text.Encoding]::UTF8)
if ([string]::IsNullOrWhiteSpace($text)) { throw "Narration text is empty" }

$output = [System.IO.Path]::GetFullPath($OutputWav)
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($output)) | Out-Null

$voice = New-Object -ComObject SAPI.SpVoice
if (-not [string]::IsNullOrWhiteSpace($VoiceName)) {
    $match = $voice.GetVoices() | Where-Object { $_.GetDescription() -eq $VoiceName } | Select-Object -First 1
    if ($null -eq $match) {
        $available = ($voice.GetVoices() | ForEach-Object { $_.GetDescription() }) -join "; "
        throw "Voice '$VoiceName' is not installed. Available: $available"
    }
    $voice.Voice = $match
}

$stream = New-Object -ComObject SAPI.SpFileStream
$format = New-Object -ComObject SAPI.SpAudioFormat
try {
    # SAFT22kHz16BitMono. Explicitly setting it avoids SPERR_UNSUPPORTED_FORMAT
    # on Windows installations whose default output device format is unavailable.
    $format.Type = 22
    $stream.Format = $format
    $stream.Open($output, 3, $false)
    $voice.AudioOutputStream = $stream
    $voice.Rate = $Rate
    $voice.Volume = $Volume
    [void]$voice.Speak($text)
}
finally {
    if ($null -ne $stream) { $stream.Close() }
}

Write-Output $output
