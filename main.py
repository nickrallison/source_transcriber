import sys
import os
import re

from parse_file import parse_filepath, parse_weblink

def add_yaml_header(content, filename, source):
    yaml_header = f'---\ntitle: {filename}\nsource: {source}\n---\n\n'
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
        content, filename = parse_weblink(arg)

    if valid_file:
        content, filename = parse_filepath(arg)

    content = add_yaml_header(content, filename, arg)

    new_file = os.path.join(sys.argv[2], filename)
    with open(new_file, 'w') as f:
        f.write(content)


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
