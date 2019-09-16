#!/usr/bin/env python3
# -*- coding: latin-1 -*- ######################################################
#                                                                              #
# wordlistctl - Fetch, install and search wordlist archives from websites and  #
# torrent peers.                                                               #
#                                                                              #
# DESCRIPTION                                                                  #
# Script to fetch, install, update and search wordlist archives from websites  #
# offering wordlists with more than 2900 wordlists available.                  #
#                                                                              #
# AUTHORS                                                                      #
# sepehrdad.dev@gmail.com                                                      #
#                                                                              #
# CONTRIBUTERS                                                                 #
# noptrix@nullsecurity.net                                                     #
#                                                                              #
################################################################################


# Load Deps
import warnings
import sys
import os
import getopt
import requests
import re
import time
import json
from gzip import GzipFile
from bz2 import BZ2File
from lzma import LZMAFile
from hashlib import md5
from shutil import copyfileobj
from concurrent.futures import ThreadPoolExecutor

try:
    import libtorrent
    import libarchive
    from rarfile import RarFile
    from bs4 import BeautifulSoup
    from termcolor import colored
except Exception as ex:
    print(f"Error while loading dependencies: {str(ex)}", file=sys.stderr)
    exit(-1)


__version__: str = "0.8.8-dev"
__project__: str = "wordlistctl"
__organization__: str = "blackarch.org"

__wordlist_path__: str = "/usr/share/wordlists"
__category__: str = ""
__config__: dict = {}
__decompress__: bool = False
__remove__: bool = False
__prefer_http__: bool = False
__torrent_dl__: bool = True

__executer__ = None
__max_parallel__: int = 5
__session__ = None
__useragent__: str = "Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0"
__proxy__: dict = {}
__proxy_http__: bool = False
__proxy_torrent__: bool = False
__chunk_size__: int = 1024
__no_confirm__: bool = False
__no_integrity_check__: bool = False
__max_retry__: int = 3


def err(string: str) -> None:
    print(colored("[-]", "red", attrs=["bold"]), f" {string}", file=sys.stderr)


def warn(string: str) -> None:
    print(colored("[!]", "yellow", attrs=["bold"]), f" {string}")


def info(string: str) -> None:
    print(colored("[*]", "blue", attrs=["bold"]), f" {string}")


def success(string: str) -> None:
    print(colored("[+]", "green", attrs=["bold"]), f" {string}")



def usage() -> None:
    str_usage: str = "usage:\n\n"
    str_usage += f"  {__project__} -f <arg> [options] | -s <arg> [options] | -S <arg> | <misc>\n\n"
    str_usage += "options:\n\n"
    str_usage += "  -f <num>   - download chosen wordlist - ? to list wordlists with id\n"
    str_usage += "  -d <dir>   - wordlists base directory (default: /usr/share/wordlists)\n"
    str_usage += "  -c <num>   - change wordlists category - ? to list wordlists categories\n"
    str_usage += "  -s <regex> - wordlist to search using <regex> in base directory\n"
    str_usage += "  -S <regex> - wordlist to search using <regex> in sites\n"
    str_usage += "  -h         - prefer http\n"
    str_usage += "  -X         - decompress wordlist\n"
    str_usage += "  -F <str>   - list wordlists in categories given\n"
    str_usage += "  -r         - remove compressed file after decompression\n"
    str_usage += "  -t <num>   - max parallel downloads (default: 5)\n\n"
    str_usage += "misc:\n\n"
    str_usage += "  -T         - disable torrent download\n"
    str_usage += "  -P <str>   - set proxy (format: proto://user:pass@host:port)\n"
    str_usage += "  -A <str>   - set useragent string\n"
    str_usage += "  -Y         - proxy http\n"
    str_usage += "  -Z         - proxy torrent\n"
    str_usage += "  -N         - do not ask for any confirmation\n"
    str_usage += "  -I         - skip integrity checks\n"
    str_usage += f"  -V         - print version of {__project__} and exit\n"
    str_usage += "  -H         - print this help and exit\n\n"
    str_usage += "example:\n\n"
    str_usage += "  # download and decompress all wordlists and remove archive\n"
    str_usage += f"  $ {__project__} -f 0 -Xr\n\n"
    str_usage += "  # download all wordlists in username category\n"
    str_usage += f"  $ {__project__} -f 0 -c 0\n\n"
    str_usage += "  # list all wordlists in password category with id\n"
    str_usage += f"  $ {__project__} -f ? -c 1\n\n"
    str_usage += "  # download and decompress all wordlists in misc category\n"
    str_usage += f"  $ {__project__} -f 0 -c 4 -X\n\n"
    str_usage += "  # download all wordlists in filename category using 20 threads\n"
    str_usage += f"  $ {__project__} -c 3 -f 0 -t 20\n\n"
    str_usage += "  # download wordlist with id 2 to \"~/wordlists\" directory using http\n"
    str_usage += f"  $ {__project__} -f 2 -d ~/wordlists -h\n\n"
    str_usage += "  # print wordlists in username and password categories\n"
    str_usage += f"  $ {__project__} -F username,password\n\n"
    str_usage += "  # download all wordlists with using tor socks5 proxy\n"
    str_usage += f"  $ {__project__} -f 0 -P \"socks5://127.0.0.1:9050\" -Y\n\n"
    str_usage += "  # download all wordlists with using http proxy and noleak useragent\n"
    str_usage += f"  $ {__project__} -f 0 -P \"http://127.0.0.1:9060\" -Y -A \"noleak\"\n\n"
    str_usage += "notes:\n\n"
    str_usage += "  * Wordlist's id are relative to the category that is chosen\n"
    str_usage += "    and are not global, so by changing the category Wordlist's\n"
    str_usage += "    id changes. E.g.: -f 1337 != -c 1 -f 1337. use -f ? -c 1\n"
    str_usage += "    to get the real id for a given password list.\n\n"
    str_usage += "  * In order to disable color terminal set ANSI_COLORS_DISABLED\n"
    str_usage += "    enviroment variable to 1.\n"
    str_usage += f"    E.g.: ANSI_COLORS_DISABLED=1 {__project__} -H\n"

    print(str_usage)


def version() -> None:
    print(f"{__project__} v{__version__}")


def banner():
    print(colored(f"--==[ {__project__} by {__organization__} ]==--\n", 
                                                        "red", attrs=["bold"]))


def decompress(filepath: str) -> None:
    filename: str = os.path.basename(filepath)
    info(f"decompressing {filename}")
    if re.fullmatch(r"^.*\.(rar)$", filename.lower()):
        os.chdir(os.path.dirname(filepath))
        infile = RarFile(filepath)
        infile.extractall()
    elif re.fullmatch(r"^.*\.(zip|7z|tar|tar.gz|tar.xz|tar.bz2)$", filename.lower()):
        os.chdir(os.path.dirname(filepath))
        libarchive.extract_file(filepath)
    else:
        if re.fullmatch(r"^.*\.(gz)$", filepath.lower()):
            infile = GzipFile(filepath, "rb")
        elif re.fullmatch(r"^.*\.(bz|bz2)$", filepath.lower()):
            infile = BZ2File(filepath, "rb")
        elif re.fullmatch(r"^.*\.(lzma|xz)$", filepath.lower()):
            infile = LZMAFile(filepath, "rb")
        else:
            raise ValueError("unknown file type")
        outfile = open(os.path.splitext(filepath)[0], "wb")
        copyfileobj(infile, outfile)
        outfile.close()
    success(f"decompressing {filename} completed")


def clean(filename: str) -> None:
    if __remove__:
        remove(filename)


def remove(filename: str) -> None:
    try:
        os.remove(filename)
    except:
        pass


def resolve_mediafire(url: str) -> str:
    try:
        page = requests.head(url,
                             headers={"User-Agent": ""},
                             allow_redirects=True)
        if page.url != url and "text/html" not in page.headers["Content-Type"]:
            return page.url
        else:
            page = requests.get(
                url, headers={"User-Agent": ""}, allow_redirects=True)
            html = BeautifulSoup(page.text, "html.parser")
            for i in html.find_all('a', {"class": "input"}):
                if str(i.text).strip().startswith("Download ("):
                    return i["href"]
        return url
    except:
        return ''


def resolve_sourceforge(url: str) -> str:
    try:
        rq = requests.get(url, stream=True,
                          headers={"User-Agent": ""},
                          allow_redirects=True)
        return rq.url
    except:
        return ''


def resolve(url: str) -> str:
    resolver = None
    resolved = ""
    if str(url).startswith("http://downloads.sourceforge.net/"):
        resolver = resolve_sourceforge
    elif str(url).startswith("http://www.mediafire.com/file/"):
        resolver = resolve_mediafire
    if resolver is None:
        resolved = url
    else:
        count = 0
        while (resolved == "") and (count < 10):
            resolved = resolver(url)
            time.sleep(10)
            count += 1
    return resolved


def to_readable_size(size: int) -> str:
    units: dict = {0: 'bytes',
                   1: 'Kbytes',
                   2: 'Mbytes',
                   3: 'Gbytes',
                   4: 'Tbytes'}
    i: int = 0
    while size > 1000:
        size = size / 1000
        i += 1
    return f"{size:.2f} {units[i]}"


def torrent_setup_proxy() -> None:
    global __session__
    global __proxy__

    if __session__ is None:
        err("session not initialized")
        exit(-1)
    elif __proxy__ == {}:
        err("proxy is empty")
        exit(-1)
    elif not __proxy_torrent__:
        return
    regex = r"^(http|https|socks4|socks5)://([a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+@)?[a-z0-9.]+:[0-9]{1,5}$"
    if re.match(regex, str(__proxy__['http']).lower()):
        username, password, host, port = "", "", "", ""
        proxy = str(__proxy__['http'])
        proxy_settings = libtorrent.proxy_settings()
        proto = proxy.split("://")[0]
        proxy = proxy.replace(f"{proto}://", "")
        if proxy.__contains__('@'):
            creds = proxy.split('@')[0]
            username, password = creds.split(':')
            proxy_settings.username, proxy_settings.password = username, password
            proxy = proxy.replace(f"{creds}@", "")
        host, port = proxy.split(':')
        proxy_settings.proxy_hostnames = True
        proxy_settings.proxy_peer_connections = True
        proxy_settings.hostname = host
        proxy_settings.proxy_port = port
        if username != "" and password != "":
            if proto in ("http", "https"):
                proxy_settings.proxy_type = libtorrent.proxy_type().http_pw
            elif proto in ("socks4", "socks5"):
                proxy_settings.proxy_type = libtorrent.proxy_type().socks5_pw
        else:
            if proto in ("http", "https"):
                proxy_settings.proxy_type = libtorrent.proxy_type().http
            elif proto in ("socks4", "socks5"):
                proxy_settings.proxy_type = libtorrent.proxy_type().socks5
        __session__.set_dht_proxy(proxy_settings)
        __session__.set_peer_proxy(proxy_settings)
        __session__.set_tracker_proxy(proxy_settings)
        __session__.set_web_seed_proxy(proxy_settings)
        __session__.set_proxy(proxy_settings)
        settings = __session__.settings()
        settings.force_proxy = True
        settings.proxy_hostnames = True
        settings.proxy_peer_connections = True
        settings.proxy_tracker_connections = True
        settings.anonymous_mode = True
        __session__.dht_proxy()
        __session__.peer_proxy()
        __session__.tracker_proxy()
        __session__.web_seed_proxy()
        __session__.proxy()
        __session__.set_settings(settings)
    else:
        err("invalid proxy format")
        exit(-1)


def integrity_check(checksum: str, path: str) -> None:
    global __chunk_size__
    global __no_integrity_check__
    filename = os.path.basename(path)
    info(f"checking {filename} integrity")
    if checksum == 'SKIP' or __no_integrity_check__:
        warn(f"{filename} integrity check -- skipping")
    hashagent = md5()
    fp = open(path, 'rb')
    while True:
        data = fp.read(__chunk_size__)
        if not data:
            break
        hashagent.update(data)
    if checksum != hashagent.hexdigest():
        raise IOError(f"{filename} integrity check -- failed")


def fetch_file(url: str, path: str) -> None:
    global __proxy__
    global __proxy_http__
    global __chunk_size__
    proxy: dict = {}
    if __proxy_http__:
        proxy = __proxy__
    filename: str = os.path.basename(path)
    if check_file(path):
        warn(f"{filename} already exists -- skipping")
    else:
        info(f"downloading {filename} to {path}")
        dlurl = resolve(url)
        rq = requests.get(dlurl, stream=True,
                            headers={"User-Agent": __useragent__},
                            proxies=proxy)
        fp = open(path, "wb")
        for data in rq.iter_content(chunk_size=__chunk_size__):
            fp.write(data)
        fp.close()
        success(f"downloading {filename} completed")


def fetch_torrent(url: str, path: str) -> None:
    global __session__
    global __proxy__
    global __torrent_dl__
    if __session__ is None:
        __session__ = libtorrent.session({"listen_interfaces": "0.0.0.0:6881"})
        if __proxy__ != {}:
            torrent_setup_proxy()
        __session__.start_dht()
    magnet = False
    if str(url).startswith("magnet:?"):
        magnet = True
    handle = None
    if magnet:
        handle = libtorrent.add_magnet_uri(
            __session__, url,
            {
                "save_path": os.path.dirname(path),
                "storage_mode": libtorrent.storage_mode_t(2),
                "paused": False,
                "auto_managed": True,
                "duplicate_is_error": True
            }
        )
        info("downloading metadata\n")
        while not handle.has_metadata():
            time.sleep(0.1)
        success("downloaded metadata")
    else:

        if not __torrent_dl__:
            return
        if os.path.isfile(path):
            handle = __session__.add_torrent(
                {
                    "ti": libtorrent.torrent_info(path),
                    "save_path": os.path.dirname(path)
                }
            )
            remove(path)
        else:
            err(f"{path} not found")
            exit(-1)
    __outfilename__ = f"{os.path.dirname(path)}/{handle.name()}"
    info(f"downloading {handle.name()} to {__outfilename__}")
    while not handle.is_seed():
        time.sleep(0.1)
    __session__.remove_torrent(handle)
    success(f"downloading {handle.name()} completed")
    decompress(__outfilename__)


def download_wordlist(config: dict, wordlistname: str, category: str) -> None:
    filename: str = ""
    file_directory: str = ""
    file_path: str = ""
    check_dir(f"{__wordlist_path__}/{category}")
    file_directory = f"{__wordlist_path__}/{category}"

    try:
        for _ in range(0, __max_retry__ +1):
            try:

                urls: list = config["url"]
                urls.sort()
                url: str = ""
                if __prefer_http__:
                    url = urls[0]
                else:
                    url = urls[-1]
                filename = url.split('/')[-1]
                file_path = f"{file_directory}/{filename}"
                csum = config["sum"][config["url"].index(url)]
                if url.startswith("http"):
                    fetch_file(url, file_path)
                    integrity_check(csum, file_path)
                    decompress(file_path)
                else:
                    if url.replace("torrent+", "").startswith("magnet:?"):
                        fetch_torrent(url.replace("torrent+", ""), file_path)
                    else:
                        fetch_file(url.replace("torrent+", ""), file_path)
                        integrity_check(csum, file_path)
                        fetch_torrent(url, file_path)
                break
            except Exception as ex:
                err(f"Error while downloading {wordlistname}: {str(ex)}")
                remove(file_path)



def download_wordlists(code: str) -> None:
    global __config__
    global __executer__
    __wordlist_id__: int = 0

    check_dir(__wordlist_path__)

    __wordlist_id__: int = to_int(code)
    __wordlists_count__: int = 0
    for i in __config__.keys():
        __wordlists_count__ += __config__[i]["count"]

    lst: dict = {}

    try:
        if (__wordlist_id__ >= __wordlists_count__ + 1) or __wordlist_id__ < 0:
            raise IndexError(f"{code} is not a valid wordlist id")
        elif __wordlist_id__ == 0:
            if __category__ == "":
                lst = __config__
            else:
                lst[__category__] = __config__[__category__]
        elif __category__ != "":
            lst[__category__] = {
                "files": [__config__[__category__]["files"][__wordlist_id__ - 1]]
            }
        else:
            cat: str = ""
            count: int = 0
            wid: int = 0
            for i in __config__.keys():
                count += __config__[i]["count"]
                if (__wordlist_id__ - 1) < (count):
                    cat = i
                    break
            wid = (__wordlist_id__ - 1) - count
            lst[cat] = {"files": [__config__[cat]["files"][wid]]}
        for i in lst.keys():
            for j in lst[i]["files"]:
                __executer__.submit(download_wordlist, j, j["name"], i)
        __executer__.shutdown(wait=True)
        errored: int = 0
    except Exception as ex:
        err(f"Error unable to download wordlist: {str(ex)}")


def print_wordlists(categories: str = "") -> None:
    global __config__
    if categories == "":
        lst: list = []
        success("available wordlists:\n")
        print("    > 0  - all wordlists")
        if __category__ != "":
            lst = __config__[__category__]["files"]
        else:
            for i in __config__.keys():
                lst += __config__[i]["files"]

        for i in lst:
            id = lst.index(i) + 1
            name = i["name"]
            compsize = to_readable_size(i["size"][0])
            decompsize = to_readable_size(i["size"][1])
            print(f"    > {id}  - {name} ({compsize}, {decompsize})")
        print("")
    else:
        categories_list: set = set([i.strip() for i in categories.split(',')])
        for i in categories_list:
            if i not in __config__.keys():
                err(f"category {i} is unavailable")
                exit(-1)
        for i in categories_list:
            success(f"{i}:")
            for j in __config__[i]["files"]:
                name = j["name"]
                compsize = to_readable_size(j["size"][0])
                decompsize = to_readable_size(j["size"][1])
                print(f"    > {name} ({compsize}, {decompsize})")
            print("")


def search_dir(regex: str) -> None:
    global __wordlist_path__
    count: int = 0
    try:
        for root, _, files in os.walk(__wordlist_path__):
            for f in files:
                if re.match(regex, f):
                    info(f"wordlist found: {os.path.join(root, f)}")
                    count += 1
        if count == 0:
            err("wordlist not found")
    except:
        pass


def search_sites(regex: str) -> None:
    count: int = 0
    lst: list = []
    info(f"searching for {regex} in config.json\n")
    try:
        if __category__ != "":
            lst = __config__[__category__]["files"]
        else:
            for i in __config__.keys():
                lst += __config__[i]["files"]

        for i in lst:
            name = i["name"]
            id = lst.index(i) + 1
            if re.match(regex, name):
                success(f"wordlist {name} found: id={id}")
                count += 1

        if count == 0:
            err("no wordlist found")
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        err(f"Error while searching: {str(ex)}")


def check_dir(dir_name: str) -> None:
    try:
        if os.path.isdir(dir_name):
            pass
        else:
            info(f"creating directory {dir_name}")
            os.mkdir(dir_name)
    except Exception as ex:
        err(f"unable to create directory: {str(ex)}")
        exit(-1)


def check_file(path: str) -> bool:
    return os.path.isfile(str(path))


def check_proxy(proxy: dict) -> bool:
    try:
        reg: str = r"^(http|https|socks4|socks5)://([a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+@)?[a-z0-9.]+:[0-9]{1,5}$"
        if re.match(reg, proxy['http']):
            return True
        return False
    except Exception as ex:
        err(f"unable to use proxy: {str(ex)}")
        exit(-1)


def change_category(code: str) -> None:
    global __category__
    global __config__
    __category_id__: int = to_int(code)
    try:
        if (__category_id__ >= list(__config__.keys()).__len__()) or __category_id__ < 0:
            raise IndexError(f"{code} is not a valid category id")
        __category__ = list(__config__.keys())[__category_id__]
    except Exception as ex:
        err(f"Error while changing category: {str(ex)}")
        exit(-1)


def print_categories() -> None:
    index: int = 0
    success("available wordlists category:\n")
    for i in __config__.keys():
        count = __config__[i]["count"]
        compsize = to_readable_size(__config__[i]["size"][0])
        decompsize = to_readable_size(__config__[i]["size"][1])
        print(f"    > {index}  - {i} ({count} lsts, {compsize}, {decompsize})")
        index += 1
    print("")


def load_config() -> None:
    global __config__
    configfile: str = f"{os.path.dirname(os.path.realpath(__file__))}/config.json"
    if __config__.__len__() <= 0:
        try:
            if not os.path.isfile(configfile):
                raise FileNotFoundError("Config file not found")
            __config__ = json.load(open(configfile, 'r'))
        except Exception as ex:
            err(f"Error while loading config files: {str(ex)}")
            exit(-1)


def to_int(string: str) -> int:
    try:
        return int(string)
    except:
        err(f"{string} is not a valid number")
        exit(-1)


def arg_parse(argv: list) -> tuple:
    global __wordlist_path__
    global __decompress__
    global __remove__
    global __prefer_http__
    global __max_parallel__
    global __torrent_dl__
    global __useragent__
    global __proxy__
    global __proxy_http__
    global __proxy_torrent__
    global __no_confirm__
    global __no_integrity_check__
    __operation__ = None
    __arg__ = None
    opFlag: int = 0

    try:
        opts, _ = getopt.getopt(argv[1:], "ZIYHNVXThrd:c:f:s:S:t:F:A:P:")

        if opts.__len__() <= 0:
            __operation__ = usage
            return __operation__, None

        for opt, arg in opts:
            if opFlag and re.fullmatch(r"^-([VfsSF])", opt):
                raise getopt.GetoptError("multiple operations selected")
            if opt == "-H":
                __operation__ = usage
                return __operation__, None
            elif opt == "-V":
                __operation__ = version
                opFlag += 1
            elif opt == "-d":
                dirname = os.path.abspath(arg)
                check_dir(dirname)
                __wordlist_path__ = dirname
            elif opt == "-f":
                if arg == '?':
                    __operation__ = print_wordlists
                else:
                    __operation__ = download_wordlists
                    __arg__ = arg
                opFlag += 1
            elif opt == "-s":
                __operation__ = search_dir
                __arg__ = arg
                opFlag += 1
            elif opt == "-X":
                __decompress__ = True
            elif opt == "-r":
                __remove__ = True
            elif opt == "-T":
                __torrent_dl__ = False
            elif opt == "-Z":
                __proxy_torrent__ = True
            elif opt == "-Y":
                __proxy_http__ = True
            elif opt == "-N":
                __no_confirm__ = True
            elif opt == "-I":
                __no_integrity_check__ = True
            elif opt == "-A":
                __useragent__ = arg
            elif opt == "-P":
                if arg.startswith('http://'):
                    proxy = {"http": arg}
                else:
                    proxy = {"http": arg, "https": arg}
                check_proxy(proxy)
                __proxy__ = proxy
            elif opt == "-S":
                __operation__ = search_sites
                __arg__ = arg
                opFlag += 1
            elif opt == "-c":
                if arg == '?':
                    __operation__ = print_categories
                    return __operation__, None
                else:
                    load_config()
                    change_category(arg)
            elif opt == "-h":
                __prefer_http__ = True
            elif opt == "-t":
                __max_parallel__ = to_int(arg)
                if __max_parallel__ <= 0:
                    raise Exception("threads number can't be less than 1")
            elif opt == "-F":
                __operation__ = print_wordlists
                __arg__ = arg
                opFlag += 1
    except getopt.GetoptError as ex:
        err(f"Error while parsing arguments: {str(ex)}")
        warn("-H for help and usage")
        exit(-1)
    except Exception as ex:
        err(f"Error while parsing arguments: {str(ex)}")
        exit(-1)
    return __operation__, __arg__


def main(argv: list) -> int:
    global __max_parallel__
    global __executer__
    banner()

    __operation__, __arg__ = arg_parse(argv)

    try:
        if __operation__ not in [version, usage]:
            load_config()
        if __executer__ is None:
            __executer__ = ThreadPoolExecutor(__max_parallel__)
        if __operation__ is not None:
            if __arg__ is not None:
                __operation__(__arg__)
            else:
                __operation__()
        else:
            raise getopt.GetoptError("no operation selected")
        return 0
    except getopt.GetoptError as ex:
        err(f"Error while running operation: {str(ex)}")
        warn("-H for help and usage")
        return -1
    except Exception as ex:
        err(f"Error while running operation: {str(ex)}")
        return -1


if __name__ == "__main__":
    warnings.simplefilter('ignore')
    sys.exit(main(sys.argv))
