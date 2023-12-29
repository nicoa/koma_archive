"""Archive Etherpads. Aggresively go through all links."""
import logging
import time
import sys
import os

import bs4
import pandas as pd
from pathlib import PosixPath
import requests


HEADERS = {
    "User-Agent": "KoMa-pad-archiver/0.1.0 (https://github.com/nicoa/koma_archive)"
}
TIMEOUT = 3

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

    if resp:  # TODO MAKE BETTER: use f-strings
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
        if ans.lower() == "y":  # TODO MAKE BETTER: if not ans; == y; elif == n; else print(please enter....) cont
            return True
        if ans.lower() == "n":
            return False


def _remove_bad_words(url):
    if isinstance(url, list):  # TODO MAKE BETTER
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
        r = requests.get(f"{url}/export/html", headers=HEADERS, timeout=TIMEOUT)
        r.encoding = "utf-8"
        #r_html = requests.get(f"{url}/export/html", timeout=3)
        #exported_text = requests.get(f"{url}/export/txt", timeout=TIMEOUT).text
    except requests.Timeout as e:
        logger.error(f"Timeout for url '{url}': {e}", stack_info=True)
        return []
    except requests.ConnectionError as e:
        logger.error(f"ConnectionError for url '{url}': {e}", stack_info=True)
        return []

    if r.status_code == 429:
        delay = int(r.headers["Retry-After"])
        logger.warn(
            f"got status code 429 (Too Many Requests), waiting for {delay} seconds"
        )
        time.sleep(delay)
    elif r.status_code != 200:
        new_url = "{}/p/{}_seenotrettung".format(
            "https://fachschaften.rwth-aachen.de/etherpad", url.split("/")[-1]
        )
        s = f"{url} -> {new_url}"
        logger.warning(f"got status code {r.status_code}, consider moving {url}")
        if False:  # confirm("give Time to save?", resp=True):
            print(s)
            confirm("Done?")
            return [new_url]
        else:
            return []
    # TODO: Don't hard-code URLs
    # TODO: What is the seenotrettung about?

    # create path
    path = PosixPath(  # TODO MAKE BETTER: do not join paths like this. Do: Path(destination) / Path(*_remove_bad_words(...)).with_suffix(".txt")
        "/".join([destination] + _remove_bad_words(url.split("/p/"))) + ".txt"
    )
    html_path = PosixPath(  # TODO MAKE BETTER
        "/".join([destination] + _remove_bad_words(url.split("/p/"))) + ".html"
    )
    if len(path.parts) < 3:  # TODO MAKE BETTER: remove .as_posix()
        logger.warning(f"too few parts in path {path.as_posix()}")
        return []

    if not path.parent.exists():
        if not confirm(f"Create dirs '{path.parent}'?"):
            logger.info(f"do NOT create path '{path.parent}'")
            return []
        else:
            logger.info(f"create path '{path.parent}'")
            # TODO MAKE BETTER: path.parent.mkdir(parents=True)
            os.makedirs(path.parent.as_posix())

    response = requests.get(f"{url}/export/txt", headers=HEADERS, timeout=TIMEOUT)
    response.encoding = "utf-8"
    with open(path.as_posix(), "w") as fh:  # TODO MAKE BETTER: remove .as_posix()
        fh.write(response.text)
    with open(html_path.as_posix(), "w") as fh:  # TODO MAKE BETTER: remove .as_posix()
        fh.write(r.text.replace(' rel="noreferrer noopener"', ""))
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
            if link:  # TODO MAKE BETTER
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

    edges = pd.DataFrame(pads.edges, columns=["from", "to"])
    edges.to_csv(f"{destination}/edges.csv", encoding="utf-8")
    logger.info("Successfully wrote edges csv")


if __name__ == "__main__":
    main()
