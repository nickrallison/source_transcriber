import sys
import os
import re

from parse_file import parse_filepath

def parse_weblink(link):
    pass



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
        content = parse_weblink(arg)

    if valid_file:
        content = parse_filepath(arg)

    print(content)


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
