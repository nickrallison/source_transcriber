# Source Transcriber

This is a script that takes input and transcribes it to an output file. It either takes a file as input, or a website URL.

If a file is given, it must be one of the following formats:
- .txt
- .md
- .pdf
- .mp3
- .mp4
- .mkv
- .webm

If a URL is given, the script will download the page and transcribe it.
- If the url is a youtube video, the script will download the video and transcribe it like a video file
- otherwise, the script downloads the html and transcribes it like a text file

## Requirements

- pdf
  - pdfminer
- mp3, mp4, mkv, webm
  - ffmpeg
- youtube
  - youtube-dl
  - ffmpeg
- web
  - pandoc

## Directions

To run the script, use the following command:
```bash
# The file names itself based on the input
python main.py [input] [output directory]
```

## Todo

- Pandoc for PDF
- weblink pdf
- Add Cost for each transcription