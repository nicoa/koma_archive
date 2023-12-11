"""Archive Etherpads. Aggresively go through all links.
"""
import logging
import sys
import os

import bs4
import pandas as pd
from pathlib2 import PosixPath
import requests

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s",
    level=logging.INFO,
    datefmt="%I:%M:%S",
)
logger = logging.getLogger("padgrapper")
logger.setLevel(logging.INFO)


def confirm(prompt=None, resp=False):
    """Prompt for yes or no response from the user.

    Returns True for yes and False for no.
    """
    if prompt is None:
        prompt = "Confirm"

    if resp:
        prompt = "%s [%s]|%s: " % (prompt, "y", "n")
    else:
        prompt = "%s [%s]|%s: " % (prompt, "n", "y")

    while True:
        ans = input(prompt)
        if not ans:
            return resp
        if ans not in ["y", "Y", "n", "N"]:
            print("please enter y or n.")
            continue
        if ans == "y" or ans == "Y":
            return True
        if ans == "n" or ans == "N":
            return False


def _remove_bad_words(url):
    url = url.replace("/etherpad/p/", "/p/")  # not having two variants
    url = "_".join(
        x
        for x in (
            url.replace("https", "_")
            .replace("http", "_")
            .replace(":", "_")
            .replace("/", "_")
            .replace(".", "_")
            .split("_")
        )
        if x != ""
    )
    return url


def get_pad_content(url, destination):
    """Read Pad content and write to HTML, after that return found links."""
    if "/p/" not in url:
        logger.info("IGNORED {} is not a valid pad url".format(url.encode("utf-8")))
        return []

    try:
        r = requests.get(url + "/export/html")
        r.encoding = "utf-8"
    except requests.ConnectionError as e:
        logger.error(e)
        return []

    if r.status_code != 200:
        new_url = "{}/p/{}_seenotrettung".format(
            "https://fachschaften.rwth-aachen.de/etherpad", url.split("/")[-1]
        )
        s = "{} -> {}".format(url, new_url)
        logger.warn("got status code {}, consider moving {}".format(r.status_code, url))
        if confirm("give Time to save?", resp=True):
            print(s)
            confirm("Done?")
            return [new_url]
        else:
            return []
    # TODO: Don't hard-code URLs

    # create path
    path = PosixPath(
        "/".join([destination] + list(map(_remove_bad_words, url.split("/p/"))))
        + ".txt"
    )
    html_path = PosixPath(
        "/".join([destination] + list(map(_remove_bad_words, url.split("/p/"))))
        + ".html"
    )
    if len(path.parts) < 3:
        logger.warn("too few parts in path {}".format(path.as_posix()))
        return []

    if not path.parent.exists():
        logger.info("create path {}".format(path.parent.as_posix()))
        if not confirm():
            return []
        os.makedirs(path.parent.as_posix())
    else:
        pass

    response = requests.get(url + "/export/txt")
    response.encoding = "utf-8"

    with open(path.as_posix(), "w") as fh:
        fh.write(response.text)

    with open(html_path.as_posix(), "w") as fh:
        fh.write(r.text)

    # call other files
    soup = bs4.BeautifulSoup(r.text, features="html.parser")
    links = [a.get("href") for a in soup.find_all("a")]
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

    def follow_links(self, url, destination):
        """Main, call get_pad_content recursively on returned links."""
        if url in self.urls:
            logger.info("IGNORE: url already contained")
            return
        self.urls.append(url)
        links = get_pad_content(url, destination)
        for link in links:
            if link:
                pass
            else:
                continue  # catch None
            verts = (
                "/".join(map(_remove_bad_words, url.split("/p/"))),
                "/".join(map(_remove_bad_words, link.split("/p/"))),
            )
            self.edges.append(verts)
            logger.info("STARTED {}".format(link.encode("utf-8")))
            self.follow_links(link, destination)


def main():
    destination = "../koma-pad-archiv"
    base_url = os.environ.get("PAD_BASE_URL")

    if not base_url:
        logger.error(
            "base URL is empty, please set the `PAD_BASE_URL' environment variable"
        )
        sys.exit(1)

    pads = PadGrabber(os.environ.get("PAD_BASE_URL"))
    pads.follow_links(pads.base_url, destination)

    edges = pd.DataFrame(pads.edges, columns=["from", "to"])
    edges.to_csv("{}/edges.csv".format(destination), encoding="utf-8")
    logger.info("Successfully wrote edges csv")


if __name__ == "__main__":
    main()
