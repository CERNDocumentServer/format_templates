# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2013 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
Utils functions for media files.
"""

import httplib
from urllib2 import urlopen, HTTPError
import re

from invenio.config import CFG_ETCDIR, CFG_SITE_URL
from invenio.bibdocfile import BibRecDocs
from invenio.search_engine import \
        perform_request_search, \
        search_pattern, \
        get_fieldvalues, \
        get_record, \
        get_creation_date
from invenio.bibrecord import record_get_field_instances, \
                              record_get_field_value, \
                              record_get_field_values
from invenio.jsonutils import json, CFG_JSON_AVAILABLE
from invenio.webbasket_dblayer import get_basket_content

MEDIAARCHIVE_PATH = '/MediaArchive/'
CFG_VIDEO_STREAMER_URL = "rtmp://wowzalb.cern.ch/vod"

CFG_MA_CAPTION_TAG = '950'
CFG_MA_CAPTION_SUBFIELD_ID = 'a'
CFG_MA_CAPTION_SUBFIELD_OWNER = 'b'
CFG_MA_CAPTION_SUBFIELD_CONTENT = 'z'

TOC_RELATIONSHIP_FIELD = ('774', '773', )

def get_media(bfo, tag="8567_", path_code='u', internal_note_code='y',
              label_code='x', resolve_movie_path='no'):
    """
    Returns a structure with the available media and their information

    Data is retrieved from field given by tag, path_code and internal_note.
    For example the path is retrieved from tag+path_code: 8567_u

    WARNING: This function is also used by bfe_CERN_audio.py

    In the case where the record has a video master path but no slaves
    mentionned in the metadata, this element can try to retrieve the
    slaves where they should be, using 'resolve_movie_path'
    parameter. This is useful in the case where metadata is not
    updated for the record, but the slaves video exists.  Be careful
    to use this only in case of formats where video should always be
    present, since retrieving the video slave path is quite heavy
    process

    The returned structure is a dictionary with keys 'slave', 'master', 'thumbnail'
    and 'posterframe' at first level, a dictionary at second
    level and third, and a list of dictionaries at fourth level.

    {'slave': [(name, {'file_type': [{'path': 'http://mediaarchive.cern.ch/Med...video1.avi',
                                    'filename': 'video1.avi',
                                    'file_type': 'avi',
                                    'label': 'Some label',
                                    'dimension':(180, 135),
                                    'video_bitrate': 120,
                                    'fps': 12.5,
                                    'audio_canal':2,
                                    'audio_bitrate':20,
                                    'audio_frequency':'22'},
                                   {...}
                       }
               )],
     'master':{same as movie}
     'thumbnail': {name: {percent: [{'path': 'http://mediaarchive.cern.ch/Med...thumb1,jpg',
                             'filename': 'thumb1.jpg',
                             'file_type': 'jpg',
                             'label': 'Some label',
                             'dimension':(180, 135),
                             'percent': 10},
                            {...}]
                         }
                  }
     'posterframe': [{same as thumbnail}, ...]
    """
    MEDIAARCHIVE_OLD_BASE_PATH = 'http://mediaarchive.cern.ch'
    MEDIAARCHIVE_BASE_PATH = 'https://mediastream.cern.ch'
    VIDEO_FORMATS = ['mov', 'wmv', 'rm', 'ram', 'mpg', 'mpeg', 'avi', 'mp4']
    MEDIA_TYPES = ['slave', 'master', 'posterframe', 'thumbnail', 'subtitle']

    out = {}
    for media in MEDIA_TYPES:
        out[media] = {}

    files = bfo.fields(tag)
    for media in files:
        path = media.get(path_code, None)
        if path is None:
            path = media.get('d', None)
            if path is None:
                # Do not process if path does not exist
                continue

        path = path.replace(MEDIAARCHIVE_OLD_BASE_PATH, MEDIAARCHIVE_BASE_PATH)
        internal_note = media.get(internal_note_code, '')
        label = media.get(label_code, '')
        media_type = get_media_type(label)
        _construct_info_dict(media, path, label, internal_note, media_type, out)

    if not out['slave'] and not out['thumbnail'] and not out['posterframe']:
        # Look for media using old method, in 8564_
        # But only do this if we are formatting a movie
        if bfo.field('960__a') == '85':
            files = bfo.fields('8564_')
            for media in files:
                media_type = ''
                if (media.get('y', '') == 'icon' or media.get('x', '') == 'icon') \
                       and media.has_key('q') and not 'http://preprints.cern.ch' in media['q']:
                    media_type = 'thumbnail'
                elif media.has_key('q') and get_format(media['q']).lower() in VIDEO_FORMATS:
                    media_type = 'slave'
                if media_type:
                    _construct_info_dict(media, media['q'], '', media['q'], media_type, out)
            if out['thumbnail']:# in this case posterframe and thumbnail are the same
                out['posterframe'].update(out['thumbnail'])

    if resolve_movie_path == 'yes' and \
          not out['slave'] and not out['thumbnail'] and not out['posterframe']:
        # If we still did not found anything, try to resolve path
        BASE_PATH = '%s/MediaArchive/Video/Public/%%(folder)s/%%(year)s/%%(key)s/%%(key)s-%%(filename)s' % MEDIAARCHIVE_BASE_PATH
        RESOLVE_CONFIG = {'INDICO': { 'folder': 'Conferences',
                                         'key': bfo.field('970__a').split('.', 1)[-1],
                                        'year': bfo.field('260__c'),
                                   'condition': bfo.field('970__a').startswith("INDICO."),
                                       'media': {      'slave': ['0600-kbps-maxH-360-25-fps-audio-128-kbps-48-kHz-stereo.mp4'],
                                                 'posterframe': ['posterframe-480x360-at-10-percent.jpg'],
                                                   'thumbnail': ['thumbnail-80x60-at-10-percent.jpg']
                                                }
                                    }
                         }

        for item in RESOLVE_CONFIG:
            if RESOLVE_CONFIG[item]['condition']:
                path_dict = {'folder': RESOLVE_CONFIG[item].get('folder', ''),
                               'year': RESOLVE_CONFIG[item].get('year', ''),
                                'key': RESOLVE_CONFIG[item].get('key', '')}
                for media_type in RESOLVE_CONFIG[item]['media']:
                    for filename in RESOLVE_CONFIG[item]['media'][media_type]:
                        path_dict.update({'filename': filename})
                        path = BASE_PATH % path_dict
                        if file_exists(path):
                            _construct_info_dict(None, path, '', path, media_type, out)

    return out


def _construct_info_dict(media, path, label, internal_note, media_type, out):
    """
    Constructs and adds to out a dictionary with full metadata about the media file
    Parameters:
        @param media: the MARC of the resource from the metadata
        @param path:  the URL of the resource
        @param label: the label extracted from MARC metadata
        @param internal_note: the internal note extracted from MARC metadata
        @param media_type: one of the types listed in MEDIA_TYPES
        @param out: the general media dictionary of this record, to be updated
    """
    info = {}
    info['path'] = path
    info['filename'] = get_filename(path)
    info['name'] = get_name(path)
    info['file_type'] = get_format(path)
    info['label'] = label
    info['dimension'] = get_dimension(internal_note, path)
    if media:
        info['order'] = get_order(media.get('8', ''), path)

    if media_type in ['slave', 'master']:
        info['video_bitrate'] = get_video_bitrate(internal_note)
        info['fps'] = get_framerate(internal_note)
        info['audio_canal'] = get_nb_audio_canal(internal_note)
        info['audio_bitrate'] = get_audio_bitrate(internal_note)
        info['audio_frequency'] = get_audio_frequency(internal_note)
        key = info['file_type']
    elif media_type in ['thumbnail', 'posterframe']:
        info['percent'] = get_percentage(internal_note)
        key = info['percent']
    elif media_type in ['subtitle']:
        info['language'] = get_language(internal_note)
        key = info['language']
    name = info['name']
    if name not in out[media_type]:
        out[media_type][name] = {}
    if key not in out[media_type][name]:
        out[media_type][name][key] = []
    out[media_type][name][key].append(info)


def get_ordered_media_names(media):
    """
    Returns the ordered names of the media in structure given as parameter.
    """
    sorted_names = ['slave', 'master', 'posterframe', 'thumbnail', 'subtitle']
    sorted_media = {}
    for name in sorted_names:
        sorted_media[name] = []

    for media_type in sorted_names:
        sort_values = {} # key: sort value / value: list of media names
        for (name, movie) in media[media_type].iteritems():
            all_movie_formats = movie.values()
            if all_movie_formats and all_movie_formats[0]:
                sort_value = all_movie_formats[0][0].get('order', 0)
                if not sort_values.has_key(sort_value):
                    sort_values[sort_value] = []
                sort_values[sort_value].append(name)
        sorted_values = sort_values.keys()
        sorted_values.sort(alphanum)
        for value in sorted_values:
            sorted_media[media_type].extend(sort_values[value])
    return sorted_media


def select_best_path(slave_list, width):
    """Return the video with highes bitrate for width, and the bitrate"""
    possible_paths = []
    for item in slave_list:
        if item['dimension'][0] == width:
            possible_paths.append((item['path'], item.get('video_bitrate', 0)))
    if possible_paths:
        possible_paths.sort(key=lambda tup:tup[1])
        return possible_paths[-1][0]
    if len(slave_list) == 2: #hack for rushes
        return slave_list[-1]['path']
    return slave_list[0]['path']

def select_best_bitrate(media):
    """Return the video path  with the best bitrate"""
    try:
        best = sorted(media, key=lambda x:x['video_bitrate'])
        return best[-1]['path']
    except:
        pass
    return False

def get_level_list(slaves, rtmp=False):
    """Prepares a list of bitrate levels for jwplayer"""
    res = []
    settings = {} #meant to keep width: max bitrate
    for slave in slaves:
        width = slave.get('dimension', (0, 0))[0]
        if width > 0:
            if width not in settings:
                settings[width] = []
            settings[width].append(slave.get('video_bitrate', 0))
    for item in settings:
        settings[item] = max(settings[item])
    if not settings:
        return []

    max_bitrate = max(settings.values())
    for slave in slaves:
        res_item = {}
        res_item['bitrate'] = slave.get('video_bitrate', 0)
        res_item['width'] = slave.get('dimension', (0, 0))[0]
        if not rtmp:
            res_item['file'] = slave['path']
        else:
            res_item['file'] = slave['path'].split(MEDIAARCHIVE_PATH)[1]
        if res_item['bitrate'] > 0 and res_item['width'] > 0 and res_item['file']:
            res.append(res_item)
            for item in settings:
                if int(item) >= 640 and res_item['width'] > item and res_item['bitrate'] > settings[item]:
                    res.append({'bitrate': res_item['bitrate'], 'width': item, 'file': res_item['file']})
                if int(item) < 640 and res_item['bitrate'] == max_bitrate: #add the high-res
                    res.append({'bitrate': res_item['bitrate'], 'width': item, 'file': res_item['file']})
    return res

def front_code_to_embed_video(bfo, width='', height=''):
    '''Returns a dictionary containing the code to embed all videos asociated with a record'''
    embed_front = {}
    multimedia = get_media(bfo)
    #retrive the masters
    masters_dict = multimedia.get('master', {})
    slave_dict = multimedia.get('slave', {})
    try:
        # try to get the ideal size of the iframe from the posterframe
        dim_width, dim_height = multimedia['posterframe'].values()[0].values()[0][0]['dimension']
    except:
        dim_width = 640
        dim_height = 360
    if not width:
        width = dim_width
    if not height:
        height = dim_height
    if masters_dict and slave_dict:
        # add the report number only of the master exists, and also the slaves exist
        report_numbers = [rep_number for rep_number in masters_dict if rep_number in slave_dict]
        collection_list = [
            'General Talks', 'Summer Student Lectures',
            'Academic Training Lectures'
        ]
        record_in_collection = perform_request_search(
            p="recid:{0}".format(bfo.recID), c=collection_list
        )
        for rep_number in report_numbers:
            if rep_number.startswith('CERN-VIDEO-C') or \
                    perform_request_search(p="recid:{0}".format(bfo.recID), c="Videos", cc="Videos"):
                embed_front[rep_number] = \
                    """<iframe width="%s" height="%s" frameborder="0" src="%s" allowfullscreen></iframe>""" \
                    % (width, height, generate_embedding_url(rep_number))
            elif record_in_collection:
                embed_front[rep_number] = \
                    """<iframe width="%s" height="%s" frameborder="0" src="%s" allowfullscreen></iframe>""" \
                    % (width, height, generate_embedding_url(str(bfo.recID)))
    return embed_front

def generate_embedding_url(report_number):
    '''Returns the URL that hosts the html code for embedding'''
    #http://cds.cern.ch/video/CERN-MOVIE-2011-124
    report_number = report_number.strip().replace(' ','').replace('/','-')
    params = {'showTitle': 'true'}

    return "%s/video/%s?%s" % (CFG_SITE_URL, report_number, '&'.join(['{0}={1}'.format(item, params[item]) for item in params]))


def get_preferred_posterframe_url(recid, icon_p=True):
    """
    Returns the posteframe that might have been manually uploaded for
    this record.

    @param recid: current record ID
    @param icon_p: if True, return icon version (if exists). Else return original image
    @return: URL of the preferred posterframe, of None if does not exist
    """
    bibarchive = BibRecDocs(recid)
    posterframe_bibdocs = bibarchive.list_bibdocs(doctype='posterframe')

    if posterframe_bibdocs:
        if icon_p:
            return posterframe_bibdocs[0].get_icon().get_url()
        for bibdoc_file in posterframe_bibdocs[0].list_latest_files():
            if not bibdoc_file.is_icon():
                return bibdoc_file.get_url()

    return None


def get_high_res_info(master_path, extensions=None):
    """
    Returns the information about the high-res files on DFS for the
    given master path (URL) + other extensions that might exist on
    DFS.

    Returned value is a dictionary with keys as available extensions,
    and values as tuple (size (int) in Bytes, master_path (string))
    """
    if not extensions:
        extensions = ['mov', 'mov.zip', 'avi', 'mpg', 'mp4']
    info = {}
    domain = master_path.split('/')[2]
    master_path_extension = master_path.split('.')[-1]
    master_path_without_extension = '.'.join(master_path.split('.')[:-1])

    master_path = master_path.replace(' ', "%20") #HTTPSConnection does not support spaces
    try:
        fd = open(CFG_ETCDIR +"/webaccess/cern_nice_soap_credentials.txt" ,"r")
        cern_nice_soap_auth = fd.read()
        fd.close()
    except ValueError:
        return {}

    _headers = {"Accept": "*/*",
                "Authorization": "Basic " + cern_nice_soap_auth.strip()}

    conn = httplib.HTTPSConnection(domain)
    # Original master path
    try:
        ## Request a connection
        conn.request("GET",
                     '/' + master_path.split('/', 3)[3],
                     headers = _headers)
        ## Get a response object:
        response = conn.getresponse()
        if response.status == 200:
            ## Get content-length:
            content_length = int(response.getheader('content-length'))
            info[master_path_extension] = (content_length,
                                           master_path)
    except:
        # Cannot connect
        pass
    ## Close the connection:
    conn.close()

    # Other formats
    for extension in extensions:
        if master_path_extension != extension:
            try:
                this_master_path = "%s.%s" % (master_path_without_extension, extension)
                conn = httplib.HTTPSConnection(domain)
                ## Request a connection
                conn.request("GET",
                             '/' + this_master_path.split('/', 3)[3],
                             headers = _headers)
                ## Get a response object:
                response = conn.getresponse()
                if response.status == 200:
                    ## Get content-length:
                    content_length = int(response.getheader('content-length'))
                    info[extension] = (content_length,
                                       this_master_path)
            except:
                # Cannot connect
                pass
            ## Close the connection:
            conn.close()
    return info


def file_exists(url):
    """
    Returns True if resource could be found at url. Else returns false
    """
    try:
        req = urlopen(url)
        if req.info().get('content-type', 'text/html') != 'text/html':
            return True
        else:
            return False
    except HTTPError, e:
        if e.code == 401:
            # Authentication is necessary to access this resouce
            domain = url.split('/')[2]
            try:
                fd = open(CFG_ETCDIR + "/webaccess/cern_nice_soap_credentials.txt" ,"r")
                cern_nice_soap_auth = fd.read()
                fd.close()
            except ValueError, e:
                return {}

            _headers = {"Accept": "*/*",
                        "Authorization": "Basic " + cern_nice_soap_auth}

            conn = httplib.HTTPSConnection(domain)
            try:
                ## Request a connection
                conn.request("GET",
                             '/' + url.split('/', 3)[3],
                             headers = _headers)
                ## Get a response object:
                response = conn.getresponse()
                if response.status == 200:
                    conn.close()
                    return True
            except:
                # Cannot connect
                pass

            ## Close the connection:
            if conn:
                conn.close()

            return False

    except IOError:
        return False


def format_size(size):
    """
    Get human-readable string for the given size in Bytes
    """
    if size < 1024:
        return "%d byte%s" % (size, size != 1 and 's' or '')
    elif size < 1024 * 1024:
        return "%.1f KB" % (size / 1024.0)
    elif size < 1024 * 1024 * 1024:
        return "%.1f MB" % (size / (1024.0 * 1024))
    else:
        return "%.1f GB" % (size / (1024.0 * 1024 * 1024))


def is_record_photo_mediaarchive(recid):
    """
    Checks if the record is PHOTOLAB
    """
    try:
        return get_fieldvalues(recid, '980__a')[0] == "PHOTOLAB"
    except:
        return False


def get_photolab_image_caption(record, imageID):
    """
    Get the caption for the given image
    """
    elements = record_get_field_instances(record, tag=CFG_MA_CAPTION_TAG)
    for element in elements:
        current_values = dict(element[0])
        if current_values.get(CFG_MA_CAPTION_SUBFIELD_ID, -1) == imageID:
            return current_values.get(CFG_MA_CAPTION_SUBFIELD_CONTENT, '')
    return ''

## Sorting Alphanumerically
def chunkify(alphanumstr):
    """return a list of numbers and non-numeric substrings of +alphanumstr+

    the numeric substrings are converted to integer, non-numeric are left as is
    """
    chunks = re.findall("(\d+|\D+)", str(alphanumstr))
    chunks = [re.match('\d', x) and int(x) or x for x in chunks] #convert numeric strings to numbers
    return chunks

def alphanum(a, b):
    """breaks +a+ and +b+ into pieces and returns left-to-right comparison of the pieces

    +a+ and +b+ are expected to be strings (for example file names) with numbers and non-numeric characters
    Split the values into list of numbers and non numeric sub-strings and so comparison of numbers gives
    Numeric sorting, comparison of non-numeric gives Lexicographic order
    """
    # split strings into chunks
    aChunks = chunkify(a)
    bChunks = chunkify(b)

    return cmp(aChunks, bChunks) #built in comparison works once data is prepared
##Sorting Alphanumerically


#Parse Metadata Functions#
def get_format(path):
    """
    Returns the file extension of the media
    Returns None if not identified
    """
    comp = path.split('.')
    if len(comp) > 1:
        return comp[-1].split('?')[0]
    else:
        return ''


def get_name(path):
    """
    Returns the name of the movie
    Returns empty string if not identified
    """
    comp = path.split('/')
    if len(comp) > 1:
        # Slave case
        if len(comp) > 5 and \
               comp[-6] == 'WebLectures':
            # WebLecture/Slides case
            return comp[-4]
        else:
            return comp[-2]
    else:
        comp = path.split('\\')
        # Master case
        if len(comp) > 0:
            return comp[-1].split('.')[0]
        else:
            return ''


def get_filename(path):
    """
    Returns the filename of the movie
    Returns None if not identified
    """
    comp = path.split('/')
    if len(comp) > 1:
        return comp[-1]
    else:
        comp = path.split('\\')
        if len(comp) > 1:
            return comp[-1]
        else:
            return None


def get_language(internal_note):
    """Returns the language of the subtitle"""
    return internal_note.replace('subtitle', '').strip()


def get_media_type(internal_note):
    """
    Returns:
        'slave' if the file is a slave movie (or not identified)
        'master' if the file is a master movie,
        'thumbnail' if the file is a thumbnail or
        'posterframe' if it is a posterframe.
    """
    internal_note_lower = internal_note.lower()
    for mtype in ['thumbnail', 'posterframe', 'master', 'subtitle']:
        if internal_note_lower.find(mtype) > -1:
            return mtype
    return 'slave'


def get_dimension(internal_note, path=""):
    """
    Returns the dimension (width, height) of the media as tuple.
    Returns (None, None) if not identified.

    Try to find dimension in internal note and path, if specified.
    """
    pattern = re.compile('(?P<width>\d+)\s*x\s*(?P<height>\d+)', re.IGNORECASE)
    match = pattern.search(internal_note+path)
    if match:
        width = match.group('width')
        height = match.group('height')
        if height.isdigit() and width.isdigit():
            width = int(width)
            height = int(height)
            return (width, height)
    return (None, None)


def resize_dimension(dimension, fixed_width, max_width, max_height=None):
    """
    Resizes the dimension to a given width, keeping the width/height ratio

    'dimension' is a tuple (width, height) as returned by 'get_dimension'
    'fixed_width' should be an int, but can also be a string or None
    'max_width' defined a maximum width for the image (useful if width
    is not specified)
    """
    if dimension == (None, None):
        return dimension

    width = dimension[0]
    height = dimension[1]
    # Convert fixed_width to int or None
    try:
        fixed_width = int(fixed_width)
    except ValueError:
        fixed_width = 0
    # Conver max_width to int or None
    try:
        max_width = int(max_width)
    except ValueError:
        max_width = 0
    if max_height:
        try:
            max_height = int(max_height)
        except ValueError:
            max_height = 0
    # Take max width into account
    if fixed_width > max_width or width > max_width:
        fixed_width = max_width
    # Compute height
    if fixed_width:
        height = (fixed_width * height)/width
        width = fixed_width
    if max_height and max_height < height:
        width = (width * max_height)/height
        height = max_height

    return (width, height)


def get_order(order_field_value, path):
    """
    Return a value that can be used to sort the media in the correct
    order. CAN RETURN AN INT OR A STRING!!!

    This function simply returns the order defined in the order field
    if it exists, or tries to resolve order based on media name.

    @param a field where order can usually be found
    @param path the full path to the video
    """
    order = 0
    if order_field_value.isdigit():
        # Order is provided in metadata
        order = int(order_field_value)
    else:
        order = get_name(path)
    return order


def get_video_bitrate(internal_note):
    """
    Return the video bitrate as int.
    Return None if not identified
    """
    pattern = re.compile('(?P<rate>\d+)(\s|-)*kbps', re.IGNORECASE)
    match = pattern.search(internal_note)
    if match:
        rate = match.group('rate')
        if rate.isdigit():
            return int(rate)
    else:
        return None


def get_audio_bitrate(internal_note):
    """
    Return the audio bitrate as int.
    Return None if not identified
    """
    pattern = re.compile('audio\s*(?P<rate>\d+)\s*kbps', re.IGNORECASE)
    match = pattern.search(internal_note)
    if match is not None:
        return match.group('rate')
    else:
        return None


def get_audio_frequency(internal_note):
    """
    Return the audio frequency as int, in kHz
    Return None if not identified
    """
    pattern = re.compile('(?P<freq>\d+)(\s|-)*khz', re.IGNORECASE)
    match = pattern.search(internal_note)
    if match is not None:
        freq = match.group('freq')
        if freq.isdigit():
            return int(freq)
    else:
        return None


def get_framerate(internal_note):
    """
    Return the number of fps as int.
    Return None if not identified
    """
    pattern = re.compile('(?P<frequency>\d+)(\s|-)*fps', re.IGNORECASE)
    match = pattern.search(internal_note)
    if match is not None:
        freq = match.group('frequency')
        if freq.isdigit():
            return int(freq)
    else:
        return None


def get_nb_audio_canal(internal_note):
    """
    Return the number audio canal as int.
    Return None if not identified
    """

    if 'stereo' in internal_note:
        return 2
    elif 'mono' in internal_note:
        return 1
    else:
        return None


def get_percentage(internal_note):
    """
    Returns the percentage of the video the image of taken
    Returns None if cannot be identified
    """
    pattern = re.compile('(?P<percent>\d+)(\s|-)*percent', re.IGNORECASE)
    match = pattern.search(internal_note)
    if match:
        percent = match.group('percent')
        if percent.isdigit():
            return int(percent)
    return 0
#End Parse Metadata Functions#


def generate_mediaexport_album(recid, resource_id, json_format=True):
    """Return the report number of associate images.

    :param str recid: The record id.
    :param str resource_id: The report number.
    :param str json_format: If true, returns JSON dump, otherwise a dictionary
    """
    # Fileds that are required
    MEDIA_CONFIG = {
        'title_en': ('245', ' ', ' ', 'a'),
        'title_fr': ('246', ' ', '1', 'a'),
    }
    bibarchive = BibRecDocs(recid)
    bibarchive_with_deleted = BibRecDocs(recid, deleted_too=True)
    bibdocs = bibarchive.list_bibdocs()
    doc_numbers = [(bibdoc.get_id(), bibdoc.get_docname(), bibdoc) for bibdoc in bibarchive_with_deleted.list_bibdocs()]
    doc_numbers.sort()
    # Calculate the size
    bibdoc_size = len(bibdocs)
    # Get the record
    record = get_record(recid)
    # Build the response
    entry = {}

    for key in MEDIA_CONFIG:
        entry[key] = record_get_field_value(record, *MEDIA_CONFIG[key])

    entry['id'] = resource_id
    entry['record_id'] = str(recid)
    entry['entry_date'] = get_creation_date(recid)
    entry['total'] = bibdoc_size
    entry['type'] = 'album'
    entry['images'] = []

    # Foreach doc create the corresponding report number
    for (docid, docname, bibdoc) in doc_numbers:
        if not bibdoc.deleted_p():
            bibdoc_number = doc_numbers.index((bibdoc.get_id(), bibdoc.get_docname(), bibdoc)) + 1
            image = generate_mediaexport(recid, True, resource_id, bibdoc_number, False)
            image['tirage_id'] = bibdoc_number
            image['id'] = '{0}-{1}'.format(image['id'], bibdoc_number)
            entry['images'].append(image)

    final = {}
    final['entries'] = [{'entry': entry}]

    if not CFG_JSON_AVAILABLE:
        return ''

    if json_format:
        return json.dumps(final)
    else:
        return final


def generate_mediaexport_basket(basket_id):
    """
    Exports the content of a basket. Takes each record from a basket and
    calls either generate_mediaexport_album or generate_mediaexport.

    :param str basket_id: The basket id.
    """
    records = get_basket_content(basket_id, format='')
    recids = [record[0] for record in records]

    output = {}
    output['entries'] = []
    for record_id in recids:
        # For each record_id return metadata
        record = get_record(record_id)
        if not record:
            # There is no record, for example when the record_id < 0 (external
            # resource). Skip it.
            continue
        report_number = record_get_field_value(record, *('037', ' ', ' ', 'a'))
        album_dict = generate_mediaexport_album(record_id, report_number, False)
        album_entries = album_dict.get('entries', None)
        if album_entries:
            output['entries'].append(album_entries)
        else:
            # If it's not an album, check if it's an image
            is_image = False
            collections = record_get_field_values(record, *('980', ' ', ' ', 'a'))
            collections.append(record_get_field_values(record, *('980', ' ', ' ', 'b')))
            for collection in collections:
                if "PHOTO" in collection:
                    is_image = True
                    break
            tirage = report_number.rsplit("-", 1)[-1]
            media_dict = generate_mediaexport(record_id, is_image, report_number, tirage, False, False)
            if media_dict:
                output['entries'].append(media_dict)

    return json.dumps(output)


def generate_mediaexport(recid, is_image, resource_id, tirage, wrapped, json_format=True):
    """Generates the JSON with the info needed to export a media resource to  CERN-Drupal"""
    """Mandatory fields to export: title_en, title_fr, caption_en, caption_fr,
                                   copyright_holder, copyright_date, attribution (image),
                                   keywords (image), directors (video), producer (video)
    """

    MEDIA_CONFIG = {'title_en':         ('245', ' ', ' ', 'a'),
                    'title_fr':         ('246', ' ', '1', 'a'),
                    'keywords':         ('653', '1', ' ', 'a'),
                    'copyright_holder': ('542', ' ', ' ', 'd'),
                    'copyright_date':   ('542', ' ', ' ', 'g'),
                    'license_url':      ('540', ' ', ' ', 'a'),
                    'license_desc':     ('540', ' ', ' ', 'b'),
                    'license_body':     ('540', ' ', ' ', 'u'),
                    'author':           ('100', ' ', ' ', 'a'),
                    'affiliation':      ('100', ' ', ' ', 'u'),
                    'directors':        ('700', ' ', ' ', 'a'),
                    'video_length':     ('300', ' ', ' ', 'a'),
                    'language':         ('041', ' ', ' ', 'a'),
                    'creation_date':    ('269', ' ', ' ', 'c'),
                    'abstract_en':      ('520', ' ', ' ', 'a'),
                    'abstract_fr':      ('590', ' ', ' ', 'a')}

    entry = {}
    record = get_record(recid)

    for key in MEDIA_CONFIG:
        entry[key] = record_get_field_value(record, *MEDIA_CONFIG[key])#.encode('utf-8')

    entry['id'] = resource_id
    entry['record_id'] = str(recid)
    entry['type'] = is_image and "image" or "video"
    entry['entry_date'] = get_creation_date(recid)

    toc_recid = 0
    toc_record = {}
    if not is_image and 'asset' in record_get_field_value(record, *('970', ' ', ' ', 'a')):
        toc_repnum = record_get_field_value(record, *('773', ' ', ' ', 'r'))
        if toc_repnum:
            try:
                toc_recid = search_pattern(p='reportnumber:"%s"' %toc_repnum)[0]
            except IndexError:
                pass

    #corner cases for copyright & licence
    if not entry['copyright_holder']:
        entry['copyright_holder'] = 'CERN'
    if not entry['license_body']:
        entry['license_body'] = 'CERN'
    if not entry['license_desc']:
        entry['license_desc'] = 'CERN'
    if not entry['license_url']:
        from invenio.bibknowledge import get_kb_mapping
        try:
            entry['license_url'] = get_kb_mapping(kb_name='LICENSE2URL', key=entry['license_desc'])['value']
        except KeyError:
            pass

    #keywords
    entry['keywords'] = ','.join(record_get_field_values(record, *MEDIA_CONFIG['keywords']))

    #attribution
    if not entry.get('author', '') and not entry.get('attribution', '') and toc_recid > 0:
        if not toc_record:
            toc_record = get_record(toc_recid)
        entry['author'] = record_get_field_value(toc_record, *MEDIA_CONFIG['author'])
        entry['affiliation'] = record_get_field_value(toc_record, *MEDIA_CONFIG['affiliation'])
        if not entry.get('directors', ''):
            entry['directors'] = ','.join(record_get_field_values(toc_record, *MEDIA_CONFIG['directors']))

    #photos
    if is_image:
        if entry['author']:
            entry['attribution'] = entry['author']
        if entry['affiliation']:
            entry['attribution'] += ': %s' % entry['affiliation']
        del entry['directors']
    else: #videos
        if entry['author']:
            entry['producer'] = entry['author']
        # Get all files from record
        files_field = ('856', '7', ' ', 'u')
        # Filter all that are images
        thumbnails = [
            image for image in record_get_field_values(record, *files_field)
            if 'jpg' in image
        ]
        # If exists get the first one
        if thumbnails:
            entry['thumbnail'] = thumbnails[0]


    del entry['author']
    del entry['affiliation']

    #
    #title
    if not entry['title_en'] and not entry['title_fr'] and toc_recid > 0:
        if not toc_record:
            toc_record = get_record(toc_recid)
        entry['title_en'] = record_get_field_value(toc_record, *MEDIA_CONFIG['title_en'])
        entry['title_fr'] = record_get_field_value(toc_record, *MEDIA_CONFIG['title_fr'])

    #crop, media storage, caption
    if is_image:
        entry['file_params'] = {'size': ['small', 'medium', 'large'], 'crop': False}

        if 'MediaArchive' in record_get_field_values(record, *('856', '7', ' ', '2')):
            entry['caption_en'] = get_photolab_image_caption(record, tirage)
            entry['caption_fr'] = ''
        else:
            brd = BibRecDocs(recid, deleted_too=True)
            doc_numbers = [(bibdoc.get_id(), bibdoc) for bibdoc in brd.list_bibdocs()]
            doc_numbers.sort()
            bibdoc = doc_numbers[tirage-1][1]
            entry['filename'] = brd.get_docname(bibdoc.get_id()) #bibdoc.get_docname()
            if 'crop' in [bibdocfile.get_subformat() for bibdocfile in bibdoc.list_latest_files()]:
                entry['file_params']['crop'] = True
            if not bibdoc.deleted_p():
                for bibdoc_file in bibdoc.list_latest_files():
                    entry['caption_en'] = bibdoc_file.get_comment()
                    entry['caption_fr'] = bibdoc_file.get_description()
                    if entry.get('caption_en', ''):
                        break

    if not entry.get('caption_en', ''):
        entry['caption_en'] = entry['abstract_en']
    if not entry.get('caption_fr', ''):
        entry['caption_fr'] = entry['abstract_fr']

    if is_image:
        del entry['language']
        del entry['video_length']

    # we don't need it
    del entry['abstract_en']
    del entry['abstract_fr']

    #make sure all mandatory fields are sent
    MANDATORY_FIELDS = ['title_en', 'title_fr', 'caption_en', 'caption_fr', 'copyright_holder', 'copyright_date']
    MANDATORY_FIELDS_IMAGE = MANDATORY_FIELDS + ['attribution', 'keywords']
    MANDATORY_FIELDS_VIDEO = MANDATORY_FIELDS + ['directors', 'producer', 'thumbnail']

    if is_image:
        mandatory_fields_all = MANDATORY_FIELDS_IMAGE
    else:
        mandatory_fields_all = MANDATORY_FIELDS_VIDEO

    for field in mandatory_fields_all:
        entry.setdefault(field, '')
    # In case we want to embed the object
    if wrapped:
        final = {}
        final['entries'] = [{'entry': entry}]

        if not CFG_JSON_AVAILABLE:
            return ''

        if json_format:
            return json.dumps(final)
        else:
            return final
    else:
        return entry


def get_keywords_from_drupal():
    """
    Retrieve keywords from Drupal feed
    """
    from invenio.websubmit_functions.file_cacher import Cache
    import json
    import urllib2

    # Drupal's feed
    DRUPAL_FEED = "http://home.web.cern.ch/api/tags-json-feed"

    def get_drupal_data():
        data = json.load(urllib2.urlopen(DRUPAL_FEED))
        data = map(lambda x: str(x['name'].encode('utf-8')), data['tags'])
        return json.dumps(data)

    try:
        cached = Cache('keywords.json', expiration=5)
        if(cached.expired()):
            cached.write(get_drupal_data())
        data = cached.read()
    except:
        data = get_drupal_data()

    return [str(x.encode('utf-8')) for x in json.loads(data)]


def get_html_for_keywords_selector(element_name, keywords):
    """
    @return: HTML markup of the keywords selector, to be used in submissions
    """

    return """
            <style type='text/css'>
                .selectize-input{
                    max-width: 450px;
                }
                /* Submission keywords reused */
                .used{
                    background: #6891fa !important;
                    border-color: #4073f3 !important;
                }
                /* Submission keywords used for
                 * first time.
                */
                .not_used{
                    background: #777!important;
                    border-color: #555!important;
                }
                .used .remove{
                    border-color: #4073f3 !important;
                }
                .not_used .remove{
                    border-color: #444!important;
                }
            </style>
            <script src='/js/selectize.min.js'></script>
            <link rel='stylesheet' href='/img/selectize.default.css' type='text/css' />
            <script type='text/javascript'>
                $(document).ready(function(){
                    var $input =  $('#selectize')
                      , $text  =  $('[name=%(element_name)s]');
                   // Make sure that javascript is enabled
                   $input.show();
                   $text.hide();
                   var list = %(keywords)s
                   $.when(
                    options = $.map(list, function(item){
                        return { 'text': item, 'value': item }
                    })
                   )
                   .done(function(){
                        make_selectize(options);
                    });
                    function make_selectize(data){
                        $input.selectize({
                            maxItems: null,
                            create: true,
                            hideSelected: true,
                            options: data,
                            plugins: ['remove_button'],
                            onInitialize: function(){
                                var preload = $text.val().split('\\n')
                                  , instance = $input[0].selectize;
                                instance.disable();
                                for(var i =0; i<preload.length; i++){
                                    instance.addOption({'text': preload[i], 'value': preload[i]});
                                    instance.refreshOptions();
                                    instance.addItem(preload[i]);
                                }
                                instance.enable();
                                instance.blur();
                            },
                            render: {
                                item: function(data, escape){

                                    if(check_if_already_exists(escape(data.text))){
                                        return '<div class="used">' + escape(data.text) + '</div>';
                                    }
                                    return '<div class="not_used">' + escape(data.text) + '</div>';
                                }
                            }
                        });
                        function check_if_already_exists(item){
                            try{
                                if($.inArray(item, list)!==-1){
                                    return true;
                                }
                                return false;
                            }catch(err){
                                // Return that is exists
                                return true;
                            }
                        }
                        var update = function(e) {
                            try{
                                $text.val($input.val().join('\\n'));
                            }catch(err){
                                // A nice error if val is empty
                            }
                        }
                        $(this).on('change', update);
                        update();
                    }
                });
            </script>
            <select id="selectize" style="display:none;" placeholder="Select keywords"></select>
        """ % {'keywords': keywords, 'element_name': element_name}

def get_toc_relationship(bfo):
    """TOC record relationship.

    :param bfo: the BibFormatObject
    :returns: the relationship field
    :rtype: List

    .. note::

        Example return

        [{'r': 'CERN-MOVIE-2015-XXX', 'o': 'AVW.project.XXX'}]
    """
    for field in TOC_RELATIONSHIP_FIELD:
        _field = bfo.fields(field)
        if _field:
            return _field
    return []
