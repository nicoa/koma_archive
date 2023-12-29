"""
Archive Etherpads recursively. Aggressively go through all new links with minimal sanity checks for real pads.
Stores the pad contents as files in separate folders for each server. Also stores a list of edges that link from pads to other pads.

Find the full projekt on: https://github.com/nicoa/koma_archive.
"""

import csv
import logging
import os
import sys
import time
from pathlib import Path

import bs4
import requests


CREATE_ALL_PATHS = False  # if True, do not ask for creating new directories
HEADERS = {
    "User-Agent": "KoMa-pad-archiver/0.1.0 (https://github.com/nicoa/koma_archive)"
}
TIMEOUT = 3


logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s",
    level=logging.INFO,
    datefmt="%I:%M:%S",
    handlers=[  # Log to file and console
        logging.FileHandler("logs.log"),
        logging.StreamHandler(),
    ],
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
        prompt = f"{prompt} [y]|n: "
    else:
        prompt = f"{prompt} [n]|y: "

    out = None
    while True:
        ans = input(prompt)
        if ans == "":
            out = resp
        elif ans.lower() == "y":
            out = True
        elif ans.lower() == "n":
            out = False
        else:
            print("please enter y or n.")
            continue
        return out


def _remove_bad_words(url_list):
    """Sanitize the urls in url_list. Replace bad words by an underscore."""
    assert isinstance(url_list, list)
    good_list = []
    for url in url_list:
        url = url.strip()  # removes leading and trailing blanks
        url = url.replace("/etherpad/p/", "/p/")  # not having two variants
        url = (
            url.replace("https:", "_")
            .replace("http:", "_")
            .replace(":", "_")
            .replace("/", "_")
            .replace(".", "_")
        )
        # removes double underscores and leading/trailing underscores
        url = "_".join(x for x in url.split("_") if x != "")
        good_list.append(url)
    return good_list


def get_pad_content(url, destination):
    """Read Pad content and write to HTML and txt, after that return found links."""
    if "/p/" not in url:
        logger.info(f"IGNORED {url} is not a valid pad url")
        return []

    try:
        response = requests.get(f"{url}/export/txt", headers=HEADERS, timeout=TIMEOUT)
        response.encoding = "utf-8"
        r = requests.get(f"{url}/export/html", headers=HEADERS, timeout=TIMEOUT)
        r.encoding = "utf-8"
    except requests.Timeout as e:
        logger.error(f"Timeout for url '{url}': {e}", stack_info=True)
        return []
    except requests.ConnectionError as e:
        logger.error(f"ConnectionError for url '{url}': {e}", stack_info=True)
        return []

    if r.status_code == 429:
        delay = int(r.headers["Retry-After"])
        logger.warning(
            f"got status code 429 (Too Many Requests), waiting for {delay} seconds, then retrying"
        )
        time.sleep(delay)
        logger.info(f"Retrying {url} now")
        return get_pad_content(url, destination)  # retry after delay
    elif r.status_code != 200:
        logger.warning(f"got status code {r.status_code}, ignoring {url}")
        return []
        #new_url = "{}/p/{}_seenotrettung".format(
        #    "https://fachschaften.rwth-aachen.de/etherpad", url.split("/")[-1]
        #)
        #s = f"{url} -> {new_url}"
        #logger.warning(f"got status code {r.status_code}, consider moving {url}")
        #if False:  # confirm("give Time to save?", resp=True):
        #    print(s)
        #    confirm("Done?")
        #    return [new_url]
        #else:
        #    return []
        # TODO: Don't hard-code URLs
        # TODO: What is the seenotrettung about?

    # create path
    path = destination / Path(*_remove_bad_words(url.split("/p/"))).with_suffix(".txt")
    html_path = path.with_suffix(".html")
    if len(path.parts) < 3:
        logger.warning(f"too few parts in path '{path}'")
        return []

    if not path.parent.exists():
        if not CREATE_ALL_PATHS and not confirm(f"Create dirs '{path.parent}'?"):
            logger.info(f"do NOT create path '{path.parent}'")
            return []
        else:
            logger.info(f"create path '{path.parent}'")
            path.parent.mkdir(parents=True)

    with open(path, "w") as fh:
        fh.write(response.text)
    with open(html_path, "w") as fh:
        fh.write(r.text.replace(' rel="noreferrer noopener"', ""))

    # extract links
    soup = bs4.BeautifulSoup(r.text, features="html.parser")
    links = [a.get("href") for a in soup.find_all("a")]
    return links


class PadGrabber:
    """Stores found urls and connections between these urls."""

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
        """Main function, calls get_pad_content recursively on returned links."""
        logger.info(f"STARTED {url}")
        if url in self.urls:
            logger.info("IGNORE: url already contained")
            return
        self.urls.append(url)

        links = get_pad_content(url, destination)
        for link in links:
            if not link:  # catch None
                continue
            verts = (
                "/".join(_remove_bad_words(url.split("/p/"))),
                "/".join(_remove_bad_words(link.split("/p/"))),
            )
            self.edges.append(verts)
            self.follow_links(link, destination)

    def store_edges(self, destination, encoding="utf-8", filename="edges.csv"):
        """Stores the extracted connections between pads as csv file."""
        # numbered_edges = [(0, e1_start, e1_end), (1, e2_start, e2_end), ...]
        numbered_edges = [(i, *edge) for i, edge in enumerate(self.edges)]
        filepath = Path(destination) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)  # make sure the dir exists
        with open(filepath, "w", newline="") as fh:
            writer = csv.writer(fh, delimiter=",")
            writer.writerow(["", "from", "to"])  # write header
            writer.writerows(numbered_edges)  # write edges
        logger.info(f"Successfully wrote edges csv to '{filepath}'")


def main():
    destination = "../koma-pad-archiv"
    base_url = os.environ.get("PAD_BASE_URL")

    if not base_url:
        logger.error(
            "base URL is empty, please set the 'PAD_BASE_URL' environment variable"
        )
        sys.exit(1)

    pads = PadGrabber(base_url)
    pads.follow_links(pads.base_url, destination)
    pads.store_edges(destination, filename="edges.csv")


if __name__ == "__main__":
    main()
