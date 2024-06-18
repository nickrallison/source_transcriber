import os
import re

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import XMLConverter, HTMLConverter, TextConverter
from pdfminer.layout import LAParams
from io import StringIO

from openai import OpenAI

def convert_pdf_to_txt(path):
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = open(path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos=set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password,caching=caching, check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()
    return text

def convert_mp4_to_mp3(video_path, audio_path):
    os.system(f"ffmpeg -y -i \"{video_path}\" -b:a 128K -vn \"{audio_path}\"")

def transcode_mp3_to_mp3(audio_path_in, audio_path_out):
    os.system(f"ffmpeg -y -i \"{audio_path_in}\" -b:a 128K \"{audio_path_out}\"")

def convert_mp3_to_txt(audio_path):
    return convert_mp3_to_txt_whisper_api(audio_path)

def convert_mp3_to_txt_whisper_api(audio_path):
    assert 'OPENAI_API_KEY' in os.environ, 'OPENAI_API_KEY environment variable must be set'
    file_size = os.path.getsize(audio_path)
    assert file_size < 25000000, 'File size is too large, must be less than 25MB, must cut into chunks or compress audio file'

    client = OpenAI()
    audio_file = open(audio_path, "rb")
    translation = client.audio.translations.create(
        model="whisper-1",
        file=audio_file
    )
    return translation.text

def parse_filepath(path):
    # assert that the file is a txt file, an md file, a pdf, an mp3, or an mp4
    extension = path.split('.')[-1]
    video_extensions = ['mp4', 'mkv', 'webm']
    audio_extensions = ['mp3']
    text_extensions = ['txt', 'md']
    base_name = os.path.basename(path)
    without_ext = ".".join(base_name.split('.')[0:-1])
    filename = without_ext + '.md'

    assert extension in video_extensions + audio_extensions + text_extensions + ['pdf'], 'File must be a txt, md, pdf, mp3, mp4, mkv, or webm file'
    if extension in video_extensions + audio_extensions:
        assert os.system('ffmpeg -version') == 0, 'ffmpeg is not installed, please install ffmpeg'


    if extension in text_extensions:
        with open(path, 'r') as f:
            content = f.read()
        return content, filename

    if extension == 'pdf':
        base_name = os.path.basename(path)
        return convert_pdf_to_txt(path), filename

    if extension in audio_extensions:
        temp_dir = os.environ.get('TMPDIR', os.environ.get('TMP', os.environ.get('TEMP', '/tmp')))
        base_name = os.path.basename(path)
        with_ext = ".".join(base_name.split('.')[0:-1]) + '.mp3'
        audio_path = os.path.join(temp_dir, with_ext)
        transcode_mp3_to_mp3(path, audio_path)
        text = convert_mp3_to_txt(audio_path)
        # os.remove(audio_path)
        return text, filename

    if extension in video_extensions:
        temp_dir = os.environ.get('TMPDIR', os.environ.get('TMP', os.environ.get('TEMP', '/tmp')))
        base_name = os.path.basename(path)
        with_ext = ".".join(base_name.split('.')[0:-1]) + '.mp3'
        audio_path = os.path.join(temp_dir, with_ext)
        convert_mp4_to_mp3(path, audio_path)
        text = convert_mp3_to_txt(audio_path)
        # os.remove(audio_path)
        return text, filename

def parse_weblink(link):
    # check if the link is a youtube link
    if 'youtube.com' in link:
        return convert_yt_link_to_txt(link)

    else:
        return convert_article_link_to_txt(link)


# use yt-dlp to download the video
# https://github.com/yt-dlp/yt-dlp
# f'yt-dlp -o "%(title)s.%(ext)s" {link}'
def convert_yt_link_to_txt(link):
    # assert that yt-dlp is installed
    assert os.system('yt-dlp --version') == 0, 'yt-dlp is not installed, please install yt-dlp'

    temp_dir = os.environ.get('TMPDIR', os.environ.get('TMP', os.environ.get('TEMP', '/tmp')))
    if not os.path.exists(f'{temp_dir}/ytdlp'):
        os.mkdir(f'{temp_dir}/ytdlp')
    for file in os.listdir(f'{temp_dir}/ytdlp'):
        os.remove(f'{temp_dir}/ytdlp/{file}')

    os.system(f'yt-dlp -o "{temp_dir}/ytdlp/%(title)s.%(ext)s" {link}')

    # should only be one file in the directory
    assert len(os.listdir(f'{temp_dir}/ytdlp')) == 1, 'More than one file downloaded, please specify the file'
    for file in os.listdir(f'{temp_dir}/ytdlp'):
        filepath = f'{temp_dir}/ytdlp/{file}'

    base_name = os.path.basename(filepath)
    with_ext = ".".join(base_name.split('.')[0:-1]) + '.mp3'
    audio_path = os.path.join(temp_dir, with_ext)

    convert_mp4_to_mp3(filepath, audio_path)
    text = convert_mp3_to_txt(audio_path)
    filename = ".".join(base_name.split('.')[0:-1]) + '.md'


    return text, filename


def convert_article_link_to_txt(link):
    # assert that pandoc is installed
    assert os.system('pandoc --version') == 0, 'pandoc is not installed, please install pandoc'

    temp_dir = os.environ.get('TMPDIR', os.environ.get('TMP', os.environ.get('TEMP', '/tmp')))
    if os.path.exists(f'{temp_dir}/article.html'):
        os.remove(f'{temp_dir}/article.html')

    os.system(f'curl {link} -o {temp_dir}/article.html')
    with open(f'{temp_dir}/article.html', 'r', encoding='utf-8') as f:
        html_contents = f.read()

    title = re.search(r'(?<=<title>)\s*(.*?)\s*(?=</title>)', html_contents).group(1)
    os.system(f'pandoc {temp_dir}/article.html -o {temp_dir}/article.md')
    with open(f'{temp_dir}/article.md', 'r', encoding='utf-8') as f:
        md_contents = f.read()
    return md_contents, title + '.md'