"""Archive Etherpads. Aggresively go throug all links."""
import logging
import os

import bs4
import pandas as pd
from pathlib import PosixPath
import requests

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s",
    level=logging.INFO,
    datefmt="%I:%M:%S",
    filename="logs.log",
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
        if ans.lower() not in ["y", "n"]:
            print("please enter y or n.")
            continue
        if ans.lower() == "y":
            return True
        if ans.lower() == "n":
            return False


def _remove_bad_words(url):
    if isinstance(url, list):
        # allows to use this for lists instead of `list(map(_remove_bad_words, urls))`
        return [_remove_bad_words(u) for u in url]

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
        logger.info(f"IGNORED {url.encode('utf-8')} is not a valid pad url")
        return []

    try:
        r_html = requests.get(f"{url}/export/html", timeout=3)
        exported_text = requests.get(f"{url}/export/txt", timeout=3).text
    except requests.ConnectionError as e:
        logger.error(f"ConnectionError in {url}: {e.message}")
        return []
    except requests.ConnectionTimeout as e:
        logger.error(f"ConnectionTimeout in {url}: {e}")
        return []

    if r_html.status_code != 200:
        new_url = "{}/p/{}_seenotrettung".format(
            "https://fachschaften.rwth-aachen.de/etherpad", url.split("/")[-1]
        )
        s = f"{url} -> {new_url}"
        logger.warning(f"got status code {r_html.status_code}, consider moving {url}")
        if False:  # confirm("give Time to save?", resp=True):
            print(s)
            confirm("Done?")
            return [new_url]
        else:
            return []
    # TODO: Don't hard-code URLs

    # create path
    path = PosixPath(
        "/".join([destination] + _remove_bad_words(url.split("/p/"))) + ".txt"
    )
    html_path = PosixPath(
        "/".join([destination] + _remove_bad_words(url.split("/p/"))) + ".html"
    )
    if len(path.parts) < 3:
        logger.warning(f"too few parts in path {path.as_posix()}")
        return []

    if not path.parent.exists():
        logger.info(f"create path {path.parent.as_posix()}")
        if not confirm():
            return []
        os.makedirs(path.parent.as_posix())
    else:
        pass

    # # write file  # TODO: re-write
    # if not path.exists():
    #     with open(path.as_posix(), 'w') as fh:
    #         fh.write(requests.get(url + '/export/txt').text.encode('utf-8'))
    # else:
    #     logger.debug("path exists already, not saving pad")
    with open(path.as_posix(), "w") as fh:
        fh.write(exported_text)
    with open(html_path.as_posix(), "w") as fh:
        fh.write(r_html.text.replace(' rel="noreferrer noopener"', ""))
    # call other files
    soup = bs4.BeautifulSoup(r_html.text, features="html.parser")
    links = map(lambda a: a.get("href"), soup.find_all("a"))
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
                "/".join(_remove_bad_words(url.split("/p/"))),
                "/".join(_remove_bad_words(link.split("/p/"))),
            )
            self.edges.append(verts)
            logger.info(f"STARTED {link}")
            self.follow_links(link, destination)


if __name__ == "__main__":
    destination = "../koma-pad-archiv"
    pads = PadGrabber(os.environ.get("PAD_BASE_URL"))
    pads.follow_links(pads.base_url, destination)

    edges = pd.DataFrame(pads.edges, columns=["from", "to"])
    edges.to_csv(f"{destination}/edges.csv", encoding="utf-8")
    logger.info("Successfully wrote edges csv")
