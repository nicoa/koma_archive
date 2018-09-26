"""Archive Etherpads. Aggresively go throug all links.

Attributes:

Warnings:
    This is python2 (raw_input etc). But, still in mind one might switch at
    some time, so used paths and mostly easy convertible syntax.
"""
from pathlib2 import PosixPath
import bs4
import logging
import os
import pandas as pd
import requests

logging.basicConfig(
    format='%(asctime)s %(levelname)s:%(message)s',
    level=logging.DEBUG, datefmt='%I:%M:%S'
)
logger = logging.getLogger('padgrapper')
logger.setLevel(logging.INFO)


def confirm(prompt=None, resp=False):
    """Prompt for yes or no response from the user.

    Returns True for yes and False for no.
    """
    if prompt is None:
        prompt = 'Confirm'

    if resp:
        prompt = '%s [%s]|%s: ' % (prompt, 'y', 'n')
    else:
        prompt = '%s [%s]|%s: ' % (prompt, 'n', 'y')

    while True:
        ans = raw_input(prompt)
        if not ans:
            return resp
        if ans not in ['y', 'Y', 'n', 'N']:
            print('please enter y or n.')
            continue
        if ans == 'y' or ans == 'Y':
            return True
        if ans == 'n' or ans == 'N':
            return False


def _remove_bad_words(url):
    url = url.replace("/etherpad/p/", "/p/")  # not having two variants
    url = "_".join(
        x for x in (
            url.replace("https", "_").replace("http", "_")
            .replace(":", "_").replace("/", "_").replace(".", "_")
            .split("_"))
        if x != "")
    return url


def get_pad_content(url):
    """Read Pad content and write to HTML, after that return found links."""
    if "/p/" not in url:
        logger.info(
            'IGNORED {} is not a valid pad url'.format(url.encode('utf-8')))
        return []

    r = requests.get(url + '/export/html')

    # create path
    path = PosixPath(
        "/".join(
            ['pads'] + map(_remove_bad_words, url.split("/p/"))) + '.html')
    if len(path.parts) < 3:
        logger.warn("too few parts in path {}".format(path.as_posix()))
        return []

    if not path.parent.exists():
        logger.info('create path {}'.format(path.parent.as_posix()))
        if not confirm():
            return []
        os.makedirs(path.parent.as_posix())
    else:
        pass

    # write file
    if not path.exists():
        with open(path.as_posix(), 'w') as fh:
            fh.write(r.text.encode('utf-8'))
    else:
        logger.debug("path exists already, not saving pad")

    # call other files
    soup = bs4.BeautifulSoup(r.text)
    links = map(lambda a: a.get('href'), soup.find_all('a'))
    return links


class PadGrabber(object):
    """docstring for PadGrabber."""

    def __init__(self, url):
        """Initialize PadGrabber.

        Args:
            url (basestring): Must be provided. Base url to start.

        """
        super(PadGrabber, self).__init__()
        self.edges = []
        self.base_url = url
        self.urls = []

    def follow_links(self, url):
        """Main, call get_pad_content recursively on returned links."""
        if url in self.urls:
            logger.info("IGNORE: url already contained")
            return
        self.urls.append(url)
        links = get_pad_content(url)
        for link in links:
            if link:
                pass
            else:
                continue  # catch None
            verts = (
                "/".join(map(_remove_bad_words, url.split("/p/"))),
                "/".join(map(_remove_bad_words, link.split("/p/")))
            )
            self.edges.append(verts)
            logger.info('STARTED {}'.format(link.encode('utf-8')))
            self.follow_links(link)


if __name__ == '__main__':
    pads = PadGrabber(
        "https://fachschaften.rwth-aachen.de/etherpad/p/KoMaAPSammlung")
    pads.follow_links(pads.base_url)

    edges = pd.DataFrame(pads.edges, columns=['from', 'to'])
    edges.to_csv("pads/edges.csv")
