import os
import re
import math
import threading
import json
import subprocess

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import XMLConverter, HTMLConverter, TextConverter
from pdfminer.layout import LAParams
from io import StringIO

from openai import OpenAI
from pydub import AudioSegment

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

def  convert_mp4_to_mp3(video_path, audio_path):
    cmd = f"ffmpeg -y -i \"{video_path}\" -b:a 128K -vn \"{audio_path}\""
    with open(os.devnull, 'wb') as devnull:
        subprocess.run(cmd, stdout=devnull, stderr=subprocess.STDOUT)


def transcode_mp3_to_mp3(audio_path_in, audio_path_out):
    cmd = f"ffmpeg -y -i \"{audio_path_in}\" -b:a 128K \"{audio_path_out}\""
    with open(os.devnull, 'wb') as devnull:
        subprocess.run(cmd, stdout=devnull, stderr=subprocess.STDOUT)

def convert_mp3_to_txt(audio_path):
    assert 'OPENAI_API_KEY' in os.environ, 'OPENAI_API_KEY environment variable must be set'

    temp_dir = os.environ.get('TMPDIR', os.environ.get('TMP', os.environ.get('TEMP', '/tmp')))
    file_size = os.path.getsize(audio_path)
    file_num = file_size / 25000000 # 25MB
    file_num = math.ceil(file_num)

    song = AudioSegment.from_mp3(audio_path)
    song_length = len(song)
    chunk_length = song_length // file_num

    overlap = 10 * 1000 # 10 seconds
    song_min = 0
    song_max = song_length - 1

    cuts = []

    for i in range(file_num):
        initial_lower = (i * chunk_length) - overlap
        initial_upper = ((i + 1) * chunk_length) + overlap

        lower = max(song_min, initial_lower)
        upper = min(song_max, initial_upper)

        cuts.append((lower, upper))

    base_name = os.path.basename(audio_path).split('.')[0]


    song_sections = [song[lower:upper] for lower, upper in cuts]
    if not os.path.exists(f'{temp_dir}/{base_name}'):
        os.mkdir(f'{temp_dir}/{base_name}')
    song_paths = [os.path.join(temp_dir, base_name, f'{i}.mp3') for i in range(file_num)]

    client = OpenAI()

    responses = ["" for _ in range(len(song_sections))]
    def raw_convert_mp3_to_txt(audio_path, index):
        audio_file = open(audio_path, "rb")
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )
        responses[index] = transcript.words

    threads = []
    for i, section in enumerate(song_sections):
        section.export(song_paths[i], format="mp3")
        thread = threading.Thread(target=raw_convert_mp3_to_txt, args=(song_paths[i], i))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()
    #
    # for i in range(len(song_paths)):
    #     with open(f"out/{i}.json", 'w') as f:
    #         json.dump(responses[i], f)
    #
    # for i, section in enumerate(song_sections):
    #     with open(f"out/{i}.json", 'r') as f:
    #         responses[i] = json.load(f)

    for i, response in enumerate(responses):
        offset = cuts[i][0] / 1000
        for index, word in enumerate(responses[i]):
            responses[i][index]['start'] += offset
            responses[i][index]['end'] += offset
            responses[i][index]['response_index'] = i

    final_response = []
    if len(responses) == 0:
        raise Exception("No responses")
    if len(responses) == 1:
        words = []
        for word_json in responses[0]:
            words.append(word_json['word'])
        return ' '.join(words)

    section = responses.pop(0)
    while len(responses) > 0:
        next_section = responses.pop(0)
        section = merge_overlapping_sections(section, next_section)

    words = ' '.join([word_json['word'] for word_json in section])

    return words


    # sections = to_non_overlapping_sections(responses)
    #
    # words = []
    # for section in sections:
    #     for word_json in section:
    #         # print(f"word_json: {word_json}")
    #         # print(word_json['word'])
    #         words.append(word_json['word'])
    # text = ' '.join(words)
    # return text

def to_non_overlapping_sections(responses):
    # Take in a list of responses, each response is a list of words with timestamps
    # The return format should look like this
    # [[response], [response, response], [response], [response, response], [response]]
    # where each response is a list of words with timestamps, and the double responses are overlapping
    # and the single responses are non-overlapping

    section_time_stamps = []
    for i, response in enumerate(responses):
        section_time_stamps.append((response[0]['start'], response[-1]['end']))

    intersections = []
    for i in range(len(section_time_stamps) - 1):
        first_section = section_time_stamps[i]
        second_section = section_time_stamps[i + 1]
        intersections.append((second_section[0], first_section[1]))

    time_zones = []
    for i, response in enumerate(responses):
        if i == 0:
            if len(intersections) == 0:
                time_zones.append((0, response[-1]['end']))
            else:
                time_zones.append((0, intersections[i][0] - 0.001))
        else:
            time_zones.append((intersections[i - 1][0], intersections[i - 1][1]))
            time_zones.append((intersections[i - 1][1], response[-1]['end']))

    responses_stacked = []
    for i, response in enumerate(responses):
        inner_response = {}
        time_zone = 0
        for index, word in enumerate(response):
            response[index]['response_index'] = i
            start = response[index]['start']
            for j, zone in enumerate(time_zones):
                if start >= zone[0] and start <= zone[1]:
                    time_zone = j
                    break
            if time_zone not in inner_response:
                inner_response[time_zone] = []
            inner_response[time_zone].append(word)
        responses_stacked.append(inner_response)

    # print(json.dumps(responses_stacked, indent=4))

    sections = {}
    for response in responses_stacked:
        for key in response:
            if key not in sections:
                sections[key] = []
            sections[key].append(response[key])

    padding_time = 2
    merged_sections = []
    for i in range(len(sections)):
        # section is a list of lists
        # each list is a response with a time zone and they are all overlapping
        section = sections[i]
        if len(section) == 1:
            merged_sections.append(section[0])
        elif len(section) == 2:
            section1 = sections[i][0]
            section2 = sections[i][1]
            merged_section = merge_overlapping_sections(section1, section2, padding_time=padding_time)
            merged_sections.append(merged_section)
        else:
            raise Exception(f"Too many overlapping sections at time zone {i}")

    return merged_sections



    # responses_out = []
    # for i, response in enumerate(responses):
    #     if i == 0:
    #         responses_out.append(response)
    #     else:
    #         responses_out.append(response)
    #         responses_out.append(response)

def merge_overlapping_sections(section1, section2):
    section_merged = []

    # words_1 = [word_json['word'] for word_json in section1]
    # words_2 = [word_json['word'] for word_json in section2]
    #
    # print(f"words_1: {words_1}")
    # print(f"words_2: {words_2}")

    result, best_1_index_start, best_2_index_start = LCSubSeq(section1, section2)

    # print(f"result: {result}")
    # print(f"best_1_index_start: {best_1_index_start}")
    # print(f"best_2_index_start: {best_2_index_start}")
    #
    # best_1 = [word['word'] for word in section1[best_1_index_start:best_1_index_start + result]]
    # best_2 = [word['word'] for word in section2[best_2_index_start:best_2_index_start + result]]

    # print(f"best_1: {best_1}")
    # print(f"best_2: {best_2}")


    index = 0
    while index < best_1_index_start:
        section_merged.append(section1[index])
        index += 1

    start_section = section1[0:best_1_index_start]
    middle_section = section1[best_1_index_start:best_1_index_start + result]
    if best_2_index_start + result + 1 >= len(section2):
        end_section = []
    else:
        end_section = section2[best_2_index_start + result + 1:]

    # start_words = [word_json['word'] for word_json in start_section]
    # middle_words = [word_json['word'] for word_json in middle_section]
    # end_words = [word_json['word'] for word_json in end_section]

    # print(f"start_section: {start_words}")
    # print(f"middle_section: {middle_words}")
    # print(f"end_section: {end_words}")

    words = []
    words.extend(start_section)
    words.extend(middle_section)
    words.extend(end_section)
    return words

def LCSubSeq(X, Y, padding_time=2):

    m = len(X)
    n = len(Y)

    X_json = X
    Y_json = Y

    X = [word_json['word'].lower() for word_json in X]
    Y = [word_json['word'].lower() for word_json in Y]

    # (best_current, best_x_current_index, best_y_current_index, best_total, best_total_x_index, best_y_total_index)
    result_table = [[(0, i, j, 0, i, j) for i in range(n + 1)] for j in range(m + 1)]

    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 or j == 0:
                result_table[i][j] = (0, i, j, 0, i, j)
            elif X[i - 1] == Y[j - 1]:
                best_current = result_table[i - 1][j - 1][0] + 1
                best_x_current_index = result_table[i - 1][j - 1][1]
                best_y_current_index = result_table[i - 1][j - 1][2]
                best_so_far = result_table[i - 1][j - 1][3]
                best_x_index_so_far = result_table[i - 1][j - 1][4]
                best_y_index_so_far = result_table[i - 1][j - 1][5]

                if best_current > best_so_far:
                    best_so_far = best_current
                    best_x_index_so_far = best_x_current_index
                    best_y_index_so_far = best_y_current_index

                result_table[i][j] = (best_current, best_x_current_index, best_y_current_index, best_so_far, best_x_index_so_far, best_y_index_so_far)

            else:
                best_current = 0
                best_x_current_index = i
                best_y_current_index = j
                if result_table[i - 1][j][3] > result_table[i][j - 1][3]:
                    best_so_far = result_table[i - 1][j][3]
                    best_x_index_so_far = result_table[i - 1][j][4]
                    best_y_index_so_far = result_table[i - 1][j][5]
                else:
                    best_so_far = result_table[i][j - 1][3]
                    best_x_index_so_far = result_table[i][j - 1][4]
                    best_y_index_so_far = result_table[i][j - 1][5]
                result_table[i][j] = (best_current, best_x_current_index, best_y_current_index, best_so_far, best_x_index_so_far, best_y_index_so_far)
    best_so_far = result_table[m][n][3]
    best_x_index = result_table[m][n][4]
    best_y_index = result_table[m][n][5]

    return (best_so_far, best_x_index, best_y_index)




def convert_mp3_to_txt_whisper_api(audio_path):
    assert 'OPENAI_API_KEY' in os.environ, 'OPENAI_API_KEY environment variable must be set'
    file_size = os.path.getsize(audio_path)

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
    filename = without_ext

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

    cmd = f'yt-dlp -o "{temp_dir}/ytdlp/%(title)s.%(ext)s" {link}'
    with open(os.devnull, 'wb') as devnull:
        subprocess.run(cmd, stdout=devnull, stderr=subprocess.STDOUT)

    # should only be one file in the directory
    assert len(os.listdir(f'{temp_dir}/ytdlp')) == 1, 'More than one file downloaded, please specify the file'
    for file in os.listdir(f'{temp_dir}/ytdlp'):
        filepath = f'{temp_dir}/ytdlp/{file}'

    base_name = os.path.basename(filepath)
    with_ext = ".".join(base_name.split('.')[0:-1]) + '.mp3'
    audio_path = os.path.join(temp_dir, with_ext)

    convert_mp4_to_mp3(filepath, audio_path)
    text = convert_mp3_to_txt(audio_path)
    filename = ".".join(base_name.split('.')[0:-1])


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
    return md_contents, title