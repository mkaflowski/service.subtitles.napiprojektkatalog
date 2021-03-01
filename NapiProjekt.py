# *-* coding: utf-8 *-*

import base64
import re
import traceback
from urllib.parse import urljoin
from xml.dom import minidom

import dom_parser
import requests
import xbmc
import xbmcaddon
import PTN

__addon__ = xbmcaddon.Addon()
__scriptname__ = __addon__.getAddonInfo('name')


class NapiProjektKatalog:
    def __init__(self):
        self.download_url = "http://napiprojekt.pl/api/api-napiprojekt3.php"
        self.base_url = "http://www.napiprojekt.pl"
        self.search_url = "/ajax/search_catalog.php"

    def log(self, msg=None, ex=None):
        if ex:
            level = xbmc.LOGERROR
            msg = traceback.format_exc()
        else:
            level = xbmc.LOGINFO

        xbmc.log((u"### [%s] - %s" % (__scriptname__, msg)), level=level)

    def notify(self, msg):
        xbmc.executebuiltin((u'Notification(%s,%s)' % (__scriptname__, msg)))

    def try_get_org_title(self, title):
        start_index = title.find("(")
        end_index = title.find(")")
        if start_index != -1 and end_index != -1:
            return title[start_index + 1:end_index]
        return None

    def find_subtitle_page(self, item, counter = 0):
        if not any((True for x in item["3let_language"] if x in ["pl", "pol"])):
            self.log('Only polish supported')
            self.notify('Only Polish supported')
            return None

        if item['tvshow'] or ('showTraktId' in item["file_original_path"] and 'showTraktId=null' not in item["file_original_path"]):
            if 'showTraktId' in item["file_original_path"]:
                showTraktId = re.findall("showTraktId=(.*?)&", item["file_original_path"])[0]
                title_to_find = requests.get("https://trakt.tv/shows/%s" % showTraktId, allow_redirects=False).headers['location'].split("/")[-1].replace("-", " ")
                query_kind = 1
                query_year = re.findall(r"\d{4}", title_to_find)[-1]
            else:
                title_to_find = item['tvshow']
                query_kind = 1
                query_year = ''
        else:
            if 'movieTraktId' in item["file_original_path"]:
                movieTraktId = re.findall("movieTraktId=(.*?)&", item["file_original_path"])[0]
                title_to_find = requests.get("https://trakt.tv/movies/%s" % movieTraktId, allow_redirects=False).headers['location'].split("/")[-1].replace("-", " ")
                query_kind = 2
                query_year = re.findall(r"\d{4}", title_to_find)[-1]
            else:
                parsed = PTN.parse(item['title'])
                try:
                    title_to_find = parsed['title']
                except:
                    title_to_find = item['title']
                try:
                    query_year = str(parsed['year'])
                except:
                    query_year = item['year']
                query_kind = 2

        post = {'queryKind': query_kind,
                'queryString': self.getsearch(title_to_find),
                'queryYear': query_year,
                'associate': ''}
        self.log('searching for movie: ' + str(post))
        # post = urllib.parse.urlencode(post, doseq=True)

        url = self.base_url + self.search_url
        subs = requests.post(url, data=post).text
        rows = self.parseDOM_base(subs, 'a', attrs={'class': 'movieTitleCat'})

        clean_title = self.get_clean(title_to_find)
        for row in rows:
            title = self.parseDOM(row.content, 'h3')[0]
            if not title:
                title = row.attrs['tytul']
            words = clean_title.lower().split(" ")
            if self.contains_all_words(self.get_clean(title), words):
                self.log('Found: ' + title)
                result = urljoin(self.base_url, row.attrs['href'])
                if item['tvshow'] or ('showTraktId' in item["file_original_path"] and 'showTraktId=null' not in item["file_original_path"]):
                    if 'seasonNumber' in item["file_original_path"]:
                        season = re.findall("seasonNumber=(.*?)&", item["file_original_path"])[0]
                        episode = re.findall("episodeNumber=(.*)", item["file_original_path"])[0]
                    else:
                        season = item['season']
                        episode = item['episode']
                    result += '-s' + season.zfill(2) + 'e' + episode.zfill(2)
                result = result.replace('napisy-', 'napisy1,1,1-dla-', 1).encode('utf-8')
                return result
            elif counter == 0:
                if item['title'] == item['videoplayer_title']:
                    if item['tvshow']:
                        response = requests.get("https://www.filmweb.pl/serials/search?q=%s" % self.getsearch(title_to_find).replace(" ", "%20")).text
                        if(len(re.findall("filmPreview__title\">(.*?)<", response))>0):
                            alternative_title = re.findall("filmPreview__title\">(.*?)<", response)[0]
                            item.update({'videoplayer_title': alternative_title})
                        else:
                            item.update({'videoplayer_title': title})
                    else:
                        response = requests.get("https://www.filmweb.pl/films/search?q=%s" % self.getsearch(title_to_find).replace(" ", "%20")).text
                        if(len(re.findall("filmPreview__title\">(.*?)<", response))>0):
                            alternative_title = re.findall("filmPreview__title\">(.*?)<", response)[0]
                            item.update({'videoplayer_title': alternative_title})
                        else:
                            item.update({'videoplayer_title': title})
                    
                counter += 1
                print(item['videoplayer_title'])
                item.update({'title': item['videoplayer_title']})
                result = self.find_subtitle_page(item,counter)
                return result

    def _is_synced(self, item, video_file_size, video_time=0):
        import datetime
        import time
        sync = False
        try:
            totalTime = float(xbmc.Player().getTotalTime())

            x = time.strptime(str(video_time).split('.')[0], '%H:%M:%S')
            milliseconds = float(float(str(video_time).split('.')[1]) / 1000)
            video_time = int(
                datetime.timedelta(hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds()) + milliseconds
            if abs(totalTime - video_time) <= 0.5:
                sync = True

            if len(video_file_size) > 0:
                video_file_size = float(re.findall(r"([\d.]+)", video_file_size)[0])
                file_size = round(item["file_original_size"] / float(1048576), 2)
                if abs(file_size - video_file_size) <= 2:
                    sync = True
        except:
            return sync

        return sync

    def search(self, item):
        subtitle_list = []
        try:
            url = self.find_subtitle_page(item).decode('utf-8')
            if not url:
                self.notify('Movie not found')
                return subtitle_list
            self.log('trying to get subtitles list')
            page = requests.get(url.replace("napisy1,1,1", "napisy1,7,0")).text
            page = self.parseDOM(page, 'tbody')
            if len(page) > 0:
                rows = self.parseDOM(page, 'tr')
                for row in rows:
                    link_hash = self.parseDOM(row, 'a', ret='href')[0]
                    link_hash = link_hash.replace('napiprojekt:', '')
                    cols = self.parseDOM(row, 'p')
                    cols.pop(0)
                    label = ' | '.join(cols[:-1])
                    try:
                        int(cols[5])
                    except:
                        continue
                    subtitle_list.append({'language': 'pol',
                                          'label': label,
                                          'link_hash': link_hash,
                                          'sync': self._is_synced(item, cols[0], cols[2]),
                                          'data': cols[4],
                                          'downloads': int(cols[5])
                                          })
            else:
                self.notify('No subtitles available')
        except Exception as e:
            self.notify('Search error, check log')
            self.log(ex=e)

        return sorted(subtitle_list, key=lambda x: (x['sync'], x['downloads']), reverse=True)

    def get_clean(self, title):
        if title is None: return
        title = re.sub('&#(\d+);', '', title)
        title = re.sub('(&#[0-9]+)([^;^0-9]+)', '\\1;\\2', title)
        title = title.replace('&quot;', '\"').replace('&amp;', '&')
        title = title.replace('&', 'and')
        title = re.sub(r'\n|([[].+?[]])|([(]\d.*?[)])|\s(vs|v[.])\s|(:|;|-|–|"|,|\'|\_|\.|\?)', '', title).lower()
        if title.startswith('the'):
            title = title[3:]
        return self.normalize(title)

    def contains_word(self, str_to_check, word):
        if str(word).lower() in str(str_to_check).lower():
            return True
        return False

    def contains_all_words(self, str_to_check, words):
        for word in words:
            if not self.contains_word(str_to_check, word):
                return False
        return True

    def parseDOM_base(self, html, name, attrs):
        if attrs:
            attrs = dict((key, re.compile(value + ('$' if value else ''))) for (key, value) in attrs.items())
        results = dom_parser.parse_dom(html, name, attrs)
        return results

    def parseDOM(self, html, name='', attrs=None, ret=False):
        results = self.parseDOM_base(html, name, attrs)
        if ret:
            results = [result.attrs[ret.lower()] for result in results]
        else:
            results = [result.content for result in results]
        return results

    def getsearch(self, title):
        if title is None: return
        title = title.lower()
        title = re.sub('&#(\d+);', '', title)
        title = re.sub('(&#[0-9]+)([^;^0-9]+)', '\\1;\\2', title)
        title = title.replace('&quot;', '\"').replace('&amp;', '&')
        title = re.sub('\\\|/|-|–|:|;|\*|\?|"|\'|<|>|\|', '', title).lower()
        return title

    def normalize(self, title):
        title = str(title).lower() \
            .replace('ą', 'a') \
            .replace('ę', 'e') \
            .replace('ć', 'c') \
            .replace('ź', 'z') \
            .replace('ż', 'z') \
            .replace('ó', 'o') \
            .replace('ł', 'l') \
            .replace('ń', 'n') \
            .replace('ś', 's')
        return title

    def download(self, md5hash, filename, language="PL"):
        try:
            values = {
                "mode": "1",
                "client": "NapiProjektPython",
                "client_ver": "0.1",
                "downloaded_subtitles_id": md5hash,
                "downloaded_subtitles_txt": "1",
                "downloaded_subtitles_lang": language
            }

            self.log('Downloading subs: ' + str(values))

            # data = urllib.parse.urlencode(values)

            response = requests.post(self.download_url, data=values).text

            DOMTree = minidom.parseString(response)

            cNodes = DOMTree.childNodes
            if cNodes[0].getElementsByTagName("status"):
                text = base64.b64decode(
                    cNodes[0].getElementsByTagName("subtitles")[0].getElementsByTagName("content")[0].childNodes[
                        0].data)
                filename = filename[:filename.rfind(".")] + ".txt"
                open(filename, "wb").write(text)
                return filename

        except Exception as e:
            self.notify('Download error, check log')
            self.log(ex=e)
            pass

        return None