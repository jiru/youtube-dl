# coding: utf-8
from __future__ import unicode_literals

import json

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    int_or_none,
    smuggle_url,
    unsmuggle_url,
)


class LiTVIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?litv\.tv/(?:vod|promo)/[^/]+/(?:content\.do)?\?.*?\b(?:content_)?id=(?P<id>[^&]+)'

    _URL_TEMPLATE = 'https://www.litv.tv/vod/%s/content.do?content_id=%s'

    _TESTS = [{
        'url': 'https://www.litv.tv/vod/drama/content.do?content_id=VOD00037490',
        'info_dict': {
            'id': 'VOD00037490',
            'title': '他們在畢業的前一天爆炸',
        },
        'playlist_count': 5,
    }, {
        'url': 'https://www.litv.tv/vod/drama/content.do?content_id=VOD00037490',
        'md5': '28955f865ed7ee4f572f54a16eedbf56',
        'info_dict': {
            'id': 'VOD00037490',
            'ext': 'mp4',
            'title': '他們在畢業的前一天爆炸第1集',
            'thumbnail': r're:https?://.*\.jpg$',
            'description': '本劇為公視2010擁抱青春靈魂最深處的第三部曲，由電影《陽陽》導演鄭有傑執導，將透過劇情探討青少年在即將跨越成人世界的重要時刻，內心所遭遇的矛盾與掙扎。本片召集一批極具潛力的明日之星共同演出，包括巫建和、黃遠、紀培慧等，堪稱2010最具話題的超級偶像劇。',
            'episode_number': 1,
        },
        'params': {
            'noplaylist': True,
        },
        'skip': 'Georestricted to Taiwan',
    }, {
        'url': 'https://www.litv.tv/promo/miyuezhuan/?content_id=VOD00044841&',
        'md5': 'cc8d39510469700d8b7a7bdf675ea33e',
        'info_dict': {
            'id': 'VOD00044841',
            'ext': 'mp4',
            'title': '芈月傳第1集　霸星芈月降世楚國',
            'description': '楚威王二年，太史令唐昧夜觀星象，發現霸星即將現世。王后得知霸星的預言後，想盡辦法不讓孩子順利出生，幸得莒姬相護化解危機。沒想到眾人期待下出生的霸星卻是位公主，楚威王對此失望至極。楚王后命人將女嬰丟棄河中，居然奇蹟似的被少司命像攔下，楚威王認為此女非同凡響，為她取名芈月。',
        },
        'skip': 'Georestricted to Taiwan',
    }]

    def _extract_playlist(self, episodes_list, video_id, program_info, prompt=True):
        episode_title = program_info['title']
        content_id = program_info['contentId']

        if prompt:
            self.to_screen('Downloading playlist %s - add --no-playlist to just download video %s' % (content_id, video_id))

        all_episodes = [
            self.url_result(smuggle_url(
                episode['url'],
                {'force_noplaylist': True}))  # To prevent infinite recursion
            for episode in episodes_list]

        return self.playlist_result(all_episodes, content_id, episode_title)

    def _real_extract(self, url):
        url, data = unsmuggle_url(url, {})

        video_id = self._match_id(url)

        noplaylist = self._downloader.params.get('noplaylist')
        noplaylist_prompt = True
        if 'force_noplaylist' in data:
            noplaylist = data['force_noplaylist']
            noplaylist_prompt = False

        webpage = self._download_webpage(url, video_id)

        program_info = self._parse_json(self._search_regex(
            r'var\s+programInfo\s*=\s*([^;]+)', webpage, 'VOD data', default='{}'),
            video_id)

        episodes_list = self._search_regex(
            r'"@type":\s+"ItemList",\s+"itemListElement":\s+(\[[^\]]+\])',
            webpage, 'Season list', default='[]')
        episodes_list = self._parse_json(episodes_list, video_id)
        if episodes_list:
            if not noplaylist:
                return self._extract_playlist(
                    episodes_list, video_id, program_info,
                    prompt=noplaylist_prompt)

            if noplaylist_prompt:
                self.to_screen('Downloading just video %s because of --no-playlist' % video_id)

        # In browsers `getMainUrl` request is always issued. Usually this
        # endpoint gives the same result as the data embedded in the webpage.
        # If georestricted, there are no embedded data, so an extra request is
        # necessary to get the error code
        if 'assetId' not in program_info:
            program_info = self._download_json(
                'https://www.litv.tv/vod/ajax/getProgramInfo', video_id,
                query={'contentId': video_id},
                headers={'Accept': 'application/json'})
        video_data = self._parse_json(self._search_regex(
            r'uiHlsUrl\s*=\s*testBackendData\(([^;]+)\);',
            webpage, 'video data', default='{}'), video_id)
        if not video_data:
            payload = {
                'assetId': program_info['assetId'],
                'watchDevices': program_info['watchDevices'],
                'contentType': program_info['contentType'],
            }
            video_data = self._download_json(
                'https://www.litv.tv/vod/ajax/getMainUrlNoAuth', video_id,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'})

        if not video_data.get('fullpath'):
            error_msg = video_data.get('errorMessage')
            if error_msg == 'vod.error.outsideregionerror':
                self.raise_geo_restricted('This video is available in Taiwan only')
            if error_msg:
                raise ExtractorError('%s said: %s' % (self.IE_NAME, error_msg), expected=True)
            raise ExtractorError('Unexpected result from %s' % self.IE_NAME)

        formats = self._extract_m3u8_formats(
            video_data['fullpath'], video_id, ext='mp4',
            entry_protocol='m3u8_native', m3u8_id='hls')
        for a_format in formats:
            # LiTV HLS segments doesn't like compressions
            a_format.setdefault('http_headers', {})['Youtubedl-no-compression'] = True

        title = program_info['title'] + program_info.get('secondaryMark', '')
        description = program_info.get('description')
        thumbnail = program_info.get('imageFile')
        categories = [item['name'] for item in program_info.get('category', [])]
        episode = int_or_none(program_info.get('episode'))

        return {
            'id': video_id,
            'formats': formats,
            'title': title,
            'description': description,
            'thumbnail': thumbnail,
            'categories': categories,
            'episode_number': episode,
        }
