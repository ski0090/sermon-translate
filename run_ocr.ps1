# --- 설정 ---
# 처리할 비디오 파일 경로
$videoFile = "C:/codes/translate/438 부활.mp4"
# 프레임을 저장할 디렉토리
$imageDir = "images"
# 최종 자막 텍스트 파일
$outputFile = "subtitles.txt"
# 추출할 프레임 (초당 1프레임)
$framerate = "1/1"

# --- 스크립트 시작 ---
Write-Host "자막 추출 프로세스를 시작합니다..."

# 1. 출력 디렉토리 확인 및 생성
if (-not (Test-Path -Path $imageDir)) {
    Write-Host "'$imageDir' 디렉토리를 생성합니다."
    New-Item -ItemType Directory -Path $imageDir
}

# 2. GStreamer를 사용하여 프레임 추출
Write-Host "GStreamer를 사용하여 '$videoFile'에서 프레임을 추출합니다. (시간이 걸릴 수 있습니다)"
$gst_command = "gst-launch-1.0 -v filesrc location=`"$videoFile`" ! decodebin ! videoconvert ! videorate ! `"video/x-raw,framerate=$framerate`" ! pngenc ! multifilesink location=`"$imageDir/frame-%05d.png`""
Invoke-Expression $gst_command

# 3. Tesseract OCR 실행
Write-Host "Tesseract OCR을 실행하여 텍스트를 추출합니다..."
# 기존 출력 파일 삭제
if (Test-Path -Path $outputFile) {
    Remove-Item -Path $outputFile
}

$imageFiles = Get-ChildItem -Path $imageDir -Filter "*.png"
foreach ($file in $imageFiles) {
    # PowerShell에서 tesseract의 표준 출력을 리디렉션할 때 인코딩 문제가 발생할 수 있으므로,
    # tesseract 자체의 파일 출력 기능을 사용하고 그 내용을 가져와서 합칩니다.
    $tempOutputFile = "$($file.FullName)_temp"
    tesseract.exe $file.FullName $tempOutputFile -l kor
    Get-Content "$($tempOutputFile).txt" | Out-File -FilePath $outputFile -Append -Encoding utf8
    Remove-Item "$($tempOutputFile).txt"
}

Write-Host "완료! 추출된 자막이 '$outputFile' 파일에 저장되었습니다."
