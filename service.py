# -*- coding: utf-8 -*- 

import os
import re
import shutil
import sys
import urllib
from urllib.parse import unquote

import unicodedata
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

__addon__ = xbmcaddon.Addon()
__scriptid__ = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__language__ = __addon__.getLocalizedString

__cwd__ = xbmc.translatePath(__addon__.getAddonInfo('path'))
__profile__ = xbmc.translatePath(__addon__.getAddonInfo('profile'))
__resource__ = xbmc.translatePath(os.path.join(__cwd__, 'resources', 'lib'))
__temp__ = xbmc.translatePath(os.path.join(__profile__, 'temp', ''))

sys.path.append(__resource__)

# sys.path.append("C:\\Program Files\\Brainwy\\LiClipse 3.6.0\\plugins\\org.python.pydev_5.7.0.201704111135\\pysrc")
# import pydevd
# pydevd.settrace('localhost', port=34099, stdoutToServer=True, stderrToServer=True, suspend=False)

from NapiProjekt import NapiProjektKatalog

def log(msg=None, ex=None):
    if ex:
        level = xbmc.LOGERROR
        msg = traceback.format_exc()
    else:
        level = xbmc.LOGINFO

    xbmc.log((u"### [%s] - %s" % (__scriptname__, msg)), level=level)


def Search(item):
    filename = '.'.join(os.path.basename(item["file_original_path"]).split(".")[:-1])
    helper = NapiProjektKatalog()
    results = helper.search(item)

    for result in results:
        listitem = xbmcgui.ListItem(label=xbmc.convertLanguage(result["language"], xbmc.ENGLISH_NAME),
                                    # language name for the found subtitle
                                    label2=result['label'],  # file name for the found subtitle
                                    # language flag, ISO_639_1 language + gif extention, e.g - "en.gif"
                                    )
        listitem.setArt({'icon': "5", 'thumb': xbmc.convertLanguage(result["language"], xbmc.ISO_639_1)})
        if result["sync"]:
            listitem.setProperty("sync", "true")

        # # below arguments are optional, it can be used to pass any info needed in download function
        # # anything after "action=download&" will be sent to addon once user clicks listed subtitle to download
        url = "plugin://%s/?action=download&l=%s&f=%s&filename=%s" % (
            __scriptid__, result["language"], result['link_hash'], filename)
        # # add it to list, this can be done as many times as needed for all subtitles found
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=url, listitem=listitem, isFolder=False)


def Download(language, hash, filename):
    subtitle_list = []
    # # Cleanup temp dir, we recomend you download/unzip your subs in temp folder and
    # # pass that to XBMC to copy and activate
    if xbmcvfs.exists(__temp__):
        shutil.rmtree(__temp__)
    xbmcvfs.mkdirs(__temp__)

    filename = os.path.join(__temp__, filename + ".zip")
    napiHelper = NapiProjektKatalog()
    filename = napiHelper.download(hash, filename, language)
    subtitle_list.append(filename)  # this can be url, local path or network path.

    return subtitle_list


def normalizeString(title):
    try:
        return str(''.join(
            c for c in unicodedata.normalize('NFKD', convert(title)) if unicodedata.category(c) != 'Mn')).replace('ł',
                                                                                                                  'l')
    except:
        title = convert(title).replace('ą', 'a').replace('ę', 'e').replace('ć', 'c').replace('ź', 'z').replace('ż',
                                                                                                               'z').replace(
            'ó', 'o').replace('ł', 'l').replace('ń', 'n').replace('ś', 's')
        return title


def convert(data):
    if isinstance(data, bytes):
        return data.decode()
    if isinstance(data, (str, int)):
        return str(data)
    if isinstance(data, dict):
        return dict(map(convert, data.items()))
    if isinstance(data, tuple):
        return tuple(map(convert, data))
    if isinstance(data, list):
        return list(map(convert, data))
    if isinstance(data, set):
        return set(map(convert, data))


def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring) >= 2:
        params = paramstring
        cleanedparams = params.replace('?', '')
        if (params[len(params) - 1] == '/'):
            params = params[0:len(params) - 2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]

    return param


def fill_item_from_name(name, item):
    try:
        tv = re.findall(r"""(.*)          # Title
                            [ .]
                            (?:S|s)(\d{1,2})    # Season
                            (?:E|e)(\d{1,2})    # Episode
                            [ .a-zA-Z]*  # Space, period, or words like PROPER/Buried
                            (\d{3,4}p)?   # Quality
                        """, name, re.VERBOSE | re.IGNORECASE)
        if len(tv) > 0:
            item['tvshow'] = tv[0][0].replace(".", " ")
            item['season'] = str(int(tv[0][1]))
            item['episode'] = str(int(tv[0][2]))
        else:
            movie = re.findall(r"""(.*?[ .]\d{4})  # Title including year
                                   [ .a-zA-Z]*     # Space, period, or words
                                   (\d{3,4}p)?      # Quality
                                """, name, re.VERBOSE)
            if len(movie) > 0:
                title = movie[0][0].replace(".", " ")
                if len(title) > 4:
                    year = try_read_year(title)
                    if (year):
                        item['year'] = year
                        title = title[:-4].strip()
                item['title'] = title
            else:
                item['title'] = name
    except Exception as e:
        pass


def try_read_year(title):
    try:
        year = title[-4:]
        return str(int(year))
    except:
        pass


params = get_params()
log(params)
# params = {'action': 'search', 'languages': 'English%2cPolish', 'preferredlanguage': 'Polish'}

if params['action'] == 'search' or params['action'] == 'manualsearch':
    item = {}
    item['temp'] = False
    item['rar'] = False
    item['year'] = xbmc.getInfoLabel("VideoPlayer.Year")  # Year
    item['season'] = str(xbmc.getInfoLabel("VideoPlayer.Season"))  # Season
    item['episode'] = str(xbmc.getInfoLabel("VideoPlayer.Episode"))  # Episode
    item['tvshow'] = normalizeString(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))  # Show
    item['videoplayer_title'] = normalizeString(xbmc.getInfoLabel("VideoPlayer.Title"))  # try to get original title
    item['title'] = normalizeString(xbmc.getInfoLabel("VideoPlayer.OriginalTitle"))  # try to get original title
    item['file_original_path'] = urllib.parse.unquote(
        xbmc.Player().getPlayingFile())  # Full path of a playing file
    item["file_original_size"] = xbmcvfs.File(item["file_original_path"]).size()
    item['3let_language'] = []
    item['preferredlanguage'] = urllib.parse.unquote(params.get('preferredlanguage', ''))
    item['preferredlanguage'] = xbmc.convertLanguage(item['preferredlanguage'], xbmc.ISO_639_2)

    for lang in urllib.parse.unquote(params['languages']).split(","):
        item['3let_language'].append(xbmc.convertLanguage(lang, xbmc.ISO_639_2))

    possible_file = False
    if item['title'] == "":
        possible_file = True
        item['title'] = normalizeString(xbmc.getInfoLabel("VideoPlayer.Title"))  # no original title, get just Title

    if item['episode'].lower().find("s") > -1:  # Check if season is "Special"
        item['season'] = "0"  #
        item['episode'] = item['episode'][-1:]

    if item['file_original_path'].find("http") > -1:
        item['temp'] = True

    elif item['file_original_path'].find("rar://") > -1:
        item['rar'] = True
        item['file_original_path'] = os.path.dirname(item['file_original_path'][6:])

    elif item['file_original_path'].find("stack://") > -1:
        stackPath = item['file_original_path'].split(" , ")
        item['file_original_path'] = stackPath[0][8:]

    # if search string defined try filling data from search string
    if params['action'] == 'manualsearch' and params.get('searchstring'):
        possible_file = False
        search_string = urllib.parse.unquote(params['searchstring'])
        fill_item_from_name(search_string, item)

    # if no metadata then load from file
    if possible_file and item['file_original_path']:
        file_name = os.path.basename(item['file_original_path'])
        if file_name == item['title']:
            file_name = os.path.splitext(file_name)[0]
            fill_item_from_name(file_name, item)

    # item = {'temp': False, 'rar': False, 'year': '2017', 'season': '6', 'episode': '4', 'tvshow': 'Scandal (2012)', 'videoplayer_title': 'The Belt', 'title': 'The Belt', 'file_original_path': 'nfs://192.168.120.6/mnt/user/Seriale/Scandal (2012)/Scandal.2012.S06E04.HD.TV-AVS.mkv', 'file_original_size': 1077465459, '3let_language': ['eng', 'pl'], 'preferredlanguage': 'pl'}
    log(item)

    Search(item)


elif params['action'] == 'download':
    # # we pickup all our arguments sent from def Search()
    subs = Download(params["l"], params["f"], params["filename"])
    # # we can return more than one subtitle for multi CD versions, for now we are still working out how to handle that in XBMC core
    for sub in subs:
        listitem = xbmcgui.ListItem(label=sub)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=sub, listitem=listitem, isFolder=False)

xbmcplugin.endOfDirectory(int(sys.argv[1]))  # # send end of directory to XBMC
