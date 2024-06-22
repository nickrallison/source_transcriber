import sys
import os
import re

from parse_file import parse_filepath, parse_weblink, convert_mp3_to_txt

def add_yaml_header(content, filename, source):
    yaml_header = f'---\naliases:\ntags:\nbad_links:\ntitle: {filename}\nsource: {source}\n---\n\n'
    return yaml_header + content



if __name__ == '__main__':
    assert len(sys.argv) == 3, 'Usage: python main.py <input md file> <sources dir>'

    arg = sys.argv[1]

    # assert that the arg is either a website or a file
    valid_url = False
    valid_file = False

    url_pattern = r'((http|https):\/\/)?([\w]+\.)+\w+(\/\w+)*'
    if re.match(url_pattern, arg):
        valid_url = True

    if os.path.exists(arg) and os.path.isfile(arg):
        valid_file = True

    assert valid_url or valid_file, 'Input must be a valid URL or file path'
    assert not (valid_url and valid_file), 'Input is both a URL and a valid file path, if it is a URL, specify with http:// or https://, if it it a file, prefix it with ./'

    if valid_url:
        content, filename, directory = parse_weblink(arg)

    if valid_file:
        content, filename = parse_filepath(arg)
        directory = "local"

    filename = re.sub(r'[^a-zA-Z0-9_ ]+', '', filename) + '.md'
    filename = re.sub(r'\s+', ' ', filename)

    directory = re.sub(r'[^a-zA-Z0-9_/\\ ]+', '', directory)
    directory = re.sub(r'\s+', ' ', directory)

    content = re.sub(r'[‘’‛]', "'", content)
    content = re.sub(r'[“”‟]', '"', content)

    content = add_yaml_header(content, filename, arg)

    new_file = os.path.join(sys.argv[2], directory, filename)
    if not os.path.exists(os.path.join(sys.argv[2], directory)):
        print(f'Creating directory {directory}')
        os.makedirs(os.path.join(sys.argv[2], directory))
    print(f'Writing to {new_file}')
    with open(new_file, 'w', encoding='utf-8') as f:
        f.write(content)

    ####
    # path = 'C:\\Users\\nickr\\AppData\\Local\\Temp\\ytdlp\\Computer Architecture Lecture 15： Introduction to Pipelining.mkv'
    # parse_filepath(path)


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
