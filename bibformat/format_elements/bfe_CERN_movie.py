# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2002-2013 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
BibFormat element - Display for videos (including posterframes, embed code)
"""

from invenio.config import \
     CFG_SITE_URL, \
     CFG_SITE_SECURE_URL, \
     CFG_SITE_RECORD

from invenio.bibformat_elements import \
     bfe_CERN_title_multimedia, \
     bfe_CERN_duration_multimedia, \
     bfe_CERN_languages
from invenio.bibformat_engine import BibFormatObject
from invenio.webstat import get_url_customevent
from invenio.search_engine import (
    perform_request_search, search_pattern, get_fieldvalues,
    get_restricted_collections_for_recid, record_public_p
)

from invenio.media_utils import (
    get_media,
    get_ordered_media_names as get_ordered_names,
    resize_dimension,
    get_preferred_posterframe_url,
    format_size,
    get_high_res_info,
    front_code_to_embed_video,
    get_level_list,
    select_best_path,
    select_best_bitrate,
    CFG_VIDEO_STREAMER_URL,
    file_exists,
    get_toc_relationship
)

from invenio.jsonutils import json
import cgi
import re

REPORT_NUMBER_ASSET_IN_TOC_MARC = '774__r'
REPORT_NUMBER_TOC_MARC = '773__r'
REPORT_NUMBER_MARC = '037__a'

# WARNING PLEASE FILL OUT HIDDEN_KEYWORD IF YOU WANT
# THE DOWNLOAD BOX TO BE HIDDEN
HIDDEN_DOWNLOADS = '595__a'
HIDDEN_KEYWORD   = 'NO_DOWNLOADS'

PLACEHOLDER_IMG_URL = '%s/img/video_not_available.gif' % CFG_SITE_URL
PLACEHOLDER_RESTRICTED_IMG_URL = '%s/img/restricted.gif' % CFG_SITE_URL

DISPLAY_PLACEHOLDER = {'slave':       ['hd'],
                       'posterframe': ['hb', '', 'hbf', 'hvp'],
                       'thumbnail':   ['hb', '', 'hbf', 'hvp'],
                      }

IMAGE_MEDIA_TYPE = ['posterframe', 'thumbnail']

MEDIAARCHIVE_PATH = '/MediaArchive/'

weblecture_flash_video_player_url = "https://mediastream.cern.ch/MediaArchive/Video/Public/WebLectures/master.swf"
newweblecture_player = "https://mediastream.cern.ch/MediaArchive/Video/Public2/weblecture-player/index.html?year=%s&lecture=%s"
flash_video_player_url = '%s/mediaplayer.swf' % CFG_SITE_URL
wmv_streaming_server_url = 'mms://mediastream.cern.ch/'

JWPLAYER_LOCATION = '//mediastream.cern.ch/MediaArchive/player/jwplayer/v7'

JWPLAYER_SCRIPTS = """<script type="text/javascript" src="%(jwplayer_location)s/jwplayer.js" type="text/javascript"></script>
       <script type="text/javascript">jwplayer.key="bsak02ZblA+UnaKB/oceaAIgGHzwL49kGPkmIpJDjPk=";</script>
       <script type="text/javascript" src="%(jwplayer_location)s/jwpsrv.js"></script>""" % {'jwplayer_location': JWPLAYER_LOCATION}

def format_element(bfo,
           display_as="embed",
           media_type="slave",
           percent="",
           max_nb="",
           min_nb="",
           width="",
           magnify='yes',
           max_width="",
           separator="<br/>",
           resolve_movie_path='no',
           autostart='no',
           thumb_link_to_detailed_record="no",
           hide_restricted_record_images="yes",
           button_list=None,
           max_heigth="",
           wrap_video=None):
    """
    Prints the movie of the record. <br/>
    Can also embed the movie in the template, or returns a link to the
    movie, or simply return the first posterframe.

    In the case where the record has a video master path but no slaves
    mentionned in the metadata, this element can try to retrieve the
    slaves where they should be, using 'resolve_movie_path'
    parameter. This is useful in the case where metadata is not
    updated for the record, but the slaves video exists.  Be careful
    to use this only in case of formats where video should always be
    present, since retrieving the video slave path is quite heavy
    process.

    @param display_as
           'embed', embed movie in html;
           'url', return HTML link to movie;
           'path', returns path to movie;
           'download_box' prints a box with links to different bitrates of the movies;
           'js_css_for_control_buttons(_closed)' display buttons that control the same div displaying various informatin: description/embed code/download box
           'code', display the code that webmasters can use to embed video.
    @param percent percentage of the movie duration at which the thumbnail is to be taken. Must be multiple of ten in [10, 90]
    @param max_nb the max number of images to print
    @param min_nb the min number of images to print. If not reached, returns empty string
    @param max_width the max width of the images
    @param magnify If 'yes', images will be magnified when mouse is over images
    @param media_type either 'slave', 'thumbnail' or 'posterframe'
    @param resolve_movie_path if 'yes', try to retrieve video automatically from where it should be even if metadata does not mention it.
    @param autostart starts to play automatically or not
    @param thumb_link_to_detailed_record if yes, the thumbnail link to the detailed record page
    @param hide_restricted_record_images if yes, images of restricted records are not displayed
    @param wrap_video wraps the video player, please note the wrapper should contain {video} word
           in order to include the video.
    """

    out = ''

    record_is_from_indico_p = bfo.field('970__a').startswith("INDICO.") or "AgendaMaker" in bfo.fields('035__9') or "INDICO" in bfo.fields('035__9')
    record_is_conf_p = len([coll_tag for coll_tag in bfo.fields('980__%') if coll_tag in ['TALK', 'SSLP', 'ACAD', 'E-LEARNING']]) > 0
    record_is_lecture_p = (record_is_from_indico_p and record_is_conf_p) or bfo.field('960__a') == '85'

    if bfo.field('960__a') not in ['85', '103'] and \
       not record_is_lecture_p and \
       not bfo.field('088__9').startswith('CERN-VIDEO-') and \
       not display_as.startswith('js_css') :
        return '' #not a video nor audio

    # If hidden keyword matched and the display request is download_box just return an empty string
    if HIDDEN_KEYWORD in bfo.fields(HIDDEN_DOWNLOADS) and display_as.lower() in ['download_box']:
        return ''

    if record_is_from_indico_p:
        resolve_movie_path = 'yes'

    record_is_toc_p = is_record_toc(bfo)
    if record_is_toc_p and display_as.lower() not in ['embed']: # if the record is TOC, only 'embed' makes sense
        return ''

    if record_is_toc_p and media_type != 'slave': # for everything else except 'slave' use the bfo of the first assset
        assets = get_assets_for_toc(bfo)
        if assets:
            bfo = BibFormatObject(assets[0])

    # We might have records with restricted access to slaves. In that
    # case, the following line should return True:
    is_restricted_record = bfo.field('5061_d') and True or False

    multimedia = get_media(bfo, resolve_movie_path=resolve_movie_path)
    ordered_names = get_ordered_names(multimedia)

    ## HTML DISPLAY ##
    if display_as.lower() in ['embed']:

        if media_type == 'slave':
            if record_is_toc_p:
                out = _generate_display_for_assets(get_assets_for_toc(bfo))
            else:
                out = _generate_display_for_slaves(bfo, multimedia, is_restricted_record, max_nb, width, max_width, ordered_names, percent, record_is_conf_p)
                if wrap_video:
                    out = wrap_video.format(video=out)
        elif media_type in ['thumbnail', 'posterframe']:
            for name in ordered_names[media_type]:
                if percent.isdigit():
                    # Percent was given. Ignore "max_nb" and print corresponding image
                    out += print_image(multimedia=multimedia,
                                       name=name,
                                       percent=int(percent),
                                       media_type=media_type,
                                       width=width,
                                       thumb_link_to_detailed_record=thumb_link_to_detailed_record,
                                       recid=bfo.recID,
                                       is_restricted_record=is_restricted_record,
                                       hide_restricted_record=hide_restricted_record_images=='yes')
                else:
                    # Print available images, up to 'max_nb'
                    try:
                        max_nb_int = int(max_nb)
                    except ValueError:
                        max_nb_int = None

                    try:
                        min_nb_int = int(min_nb)
                    except ValueError:
                        min_nb_int = None

                    (html_output, nb_images) = print_images(multimedia=multimedia,
                                                        name=name,
                                                        max_nb=max_nb_int,
                                                        min_nb=min_nb_int,
                                                        media_type=media_type,
                                                        width=width,
                                                        max_heigth=max_heigth,
                                                        magnify=magnify,
                                                        thumb_link_to_detailed_record=thumb_link_to_detailed_record,
                                                        recid=bfo.recID,
                                                        is_restricted_record=is_restricted_record,
                                                        hide_restricted_record=hide_restricted_record_images=='yes')
                    out += html_output
                    if max_nb_int is not None:
                        max_nb_int -= nb_images
                        if max_nb_int <= 0:
                            break


    ## DOWNLOAD MOVIE ##
    elif display_as.lower() in ['download_box'] and ordered_names.get('slave', ''):
        # display the download box containing the links to all available slaves
        out = _generate_download_movie_box(bfo, multimedia, ordered_names, record_is_conf_p)

    ## BACKWORDS COMPATIBILITY ##
    elif display_as.lower() in ['expandable_download_box'] and ordered_names.get('slave', ''):
        out = _generate_js_css_code_for_control_buttons('download', close=True)
        out +=  '''<div style="clear:both"></div><div style="text-align: left; padding-top: 5px; padding-bottom: 5px">
                       <a id="video_controlbutton_download" class="video_controlbutton" href="#">Download</a>
                   </div>'''
        out += '''<div id="video_detailbox_download" style="margin:10px">%s</div>''' % _generate_download_movie_box(bfo, multimedia, ordered_names, record_is_conf_p)

    ## EMBED CODE ##
    elif display_as.lower() in ['code'] and ordered_names.get('slave', ''):
        out = ''
        if not is_restricted_record:
            out = _generate_embed_movie_box(bfo)
        if not out: #something is not right, don't show the embed button
            # Check is the new lecture
            is_new_weblecture = _is_new_weblecture(bfo, is_restricted_record, multimedia, ordered_names)
            if is_new_weblecture:
                out = _generate_embed_movie_box(bfo, is_new_weblecture)
            else:
                out = _generate_css_code_for_hide_embed_button()

    ## HELPER: JS_CODE FOR BUTTON LIST ##
    elif display_as.lower() in ['js_css_for_control_buttons', 'js_css_for_control_buttons_closed']:

        # Make sure that the download button is completely removed from the DOM
        out = ""
        if HIDDEN_KEYWORD in bfo.fields(HIDDEN_DOWNLOADS):
            out += """
                <script type="text/javascript">
                    $(document).ready(function(){
                        $('[rel=download_button]').removeClass('hover').hide().remove();
                        $('[rel=embed_button]').addClass('hover');
                    })
                </script>
            """
            # Remove the download button from the list
            check_buttons_list = button_list.split(',')
            if 'download' in check_buttons_list:
                check_buttons_list.remove('download')
                button_list = ','.join(check_buttons_list)

        if not ordered_names['slave']:
            out += _generate_css_code_for_hide_control_buttons(button_list)
        else:
            out += _generate_js_css_code_for_control_buttons(button_list, close = display_as.lower().endswith('_closed'))

    ## LINKS ##
    elif display_as.lower() in ['url']:
        # Return clickable urls
        paths = _generate_textual_paths_with_labels(multimedia, ordered_names, media_type, max_nb)
        out = separator.join(['<a href="%s">%s</a>' % (path, label or label_replacement) for (path, label, label_replacement) in paths])

    ## TEXTUAL PATHS ##
    else:
        out = separator.join([path for (path, dummy, dummy) in _generate_textual_paths_with_labels(multimedia, ordered_names, media_type, max_nb)])

    # we reach this point, and there is nothing to display
    if not out:
        # No slaves found. In some cases, we want to say that the videos are being processed.
        if display_as.lower() in ['embed'] and \
                media_type in DISPLAY_PLACEHOLDER and \
                bfo.output_format.lower() in DISPLAY_PLACEHOLDER[media_type]:
            if record_is_lecture_p or bfo.field('960__a') == '85':
                return _generate_placeholder(bfo)

    return out


def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0


def _generate_placeholder(bfo):
    """Generated the placeholder image"""

    if bfo.field('960__a') == '85':
        # IE incompatibility. TODO: check if this test is still needed.
        if bfo.output_format.lower() == 'hvp':
            placeholder_width = 180
        else:
            placeholder_width = 190
    else:
        placeholder_width = 120

    # Last chance is to find it in the attached posterframe files
    image_last_chance = get_preferred_posterframe_url(bfo.recID, icon_p=True)
    if not image_last_chance:
        image = PLACEHOLDER_IMG_URL

    margin_right = 'margin-right:2px;'
    if bfo.output_format.lower() == 'hvp':
        margin_right = ''

    return '<img src="%s" alt="Not yet available" style="%swidth:100%%;max-width:%ipx"/>' % \
            (image, margin_right, placeholder_width)

def _is_new_weblecture(bfo, is_restricted_record, multimedia, ordered_names):
    """Returns if is a new weblecture.

    :return string:
    """
    out = ''
    for media_name in ordered_names['slave']:
        labels, year =  _get_labels_and_year(multimedia, media_name)
        if 'mp4camera' in labels and year:
            out += _generate_display_for_weblecture_new(media_name, year, is_restricted_record, bfo)
    return out

def _get_labels_and_year(multimedia, media_name):
    """Returns a tuple with labels and year from multimedia

    :return tuple: (labels, year)
    """
    #check for the new weblectures
    try:
        labels = [multimedia['slave'][media_name]['mp4'][index]['label'] for index in range(0, len(multimedia['slave'][media_name]['mp4']))]
        year = multimedia['slave'][media_name]['mp4'][0]['path'].split('/')[-3]
    except (KeyError, IndexError):
        labels = []
        year = ''

    return labels, year

def _generate_display_for_slaves(bfo, multimedia, is_restricted_record, max_nb, width, max_width, ordered_names, percent, record_is_conf_p):
    """Returns the html for displaying a video"""
    j = 0 #holds the number of videos displayed

    if not multimedia or not ordered_names:
        return ''

    if not ordered_names['slave']:
        return """<img src="%s" style="margin: 0px auto; display: block;" />""" % PLACEHOLDER_IMG_URL

    out = JWPLAYER_SCRIPTS

    if is_restricted_record:
        out += '''
            <br>
            <span style="font-size:small;color:#f00">
                This video is restricted. You might be asked to enter your CERN credentials (will be transmitted securely).
            </span><br/>'''

    weblectures_movies = []
    media_is_weblecture = []
    for media_name in ordered_names['slave']:
        #check for the new weblectures
        #try:
            #labels = [multimedia['slave'][media_name]['mp4'][index]['label'] for index in range(0, len(multimedia['slave'][media_name]['mp4']))]
            #year = multimedia['slave'][media_name]['mp4'][0]['path'].split('/')[-3]
        #except (KeyError, IndexError):
            #labels = []
            #year = ''
        # NOTE: Just replace it in order to use the check on other places too
        labels, year =  _get_labels_and_year(multimedia, media_name)
        if 'mp4camera' in labels and year:
            out += _generate_display_for_weblecture_new(media_name, year, is_restricted_record, bfo)
            media_is_weblecture.append(media_name)
        elif multimedia['slave'][media_name].has_key('html'):
            media_is_weblecture.append(media_name)
            media = multimedia['slave'][media_name]
            try:
                flash_url = media['html'][0]['path']
            except:
                flash_url = ''
            try:
                mp4_url = media['mp4'][0]['path']
                mp4_url = re.sub('http(s)?://media(archive|stream).cern.ch/MediaArchive/', '', mp4_url)
            except:
                mp4_url = ''
            if flash_url:
                weblectures_movies.append((media_name, flash_url, mp4_url, media, multimedia))


    if weblectures_movies:
        out += _generate_display_for_weblecture(weblectures_movies, is_restricted_record, bfo)

    video_movies = []
    for media_name in ordered_names['slave']:
        if media_name in media_is_weblecture:
            pass
        else:
            media = multimedia['slave'][media_name]
            posterframe = get_video_posterframe(multimedia['posterframe'].get(media_name, ''), 5, (640, 360))
            if 'mp4' in media or 'flv' in media:
                #embed only mp4 or flv
                video_html =  _generate_display_for_video_jwplayer(bfo, multimedia, media, posterframe, is_restricted_record, media_name)
                if video_html:
                    video_movies.append(media_name)
                    out += video_html

    # Print links to switch video

    printed_videos = [video_name for (video_name, dummy, dummy, dummy, dummy) in weblectures_movies] + video_movies
    printed_videos.sort() #sort by name

    if weblectures_movies or len(printed_videos) > 1:
        out += js_code_for_video_selection(printed_videos[0], video_movies)
    if len(printed_videos) > 1: #we have several videos
        out += '''<style type="text/css">
                .switchLink {
                    background-color:#fafafa !important;
                    color:#222 !important;
                    font-size:small !important;
                    border:#ddd solid 1px;
                    padding:2px;
                    margin:2px
                }
                .switchLink.on{
                    background-color: #333 !important;
                    color: #fff !important;
                    text-decoration:none;
                    cursor:default
                }
                </style>'''
        out += '''<span style="background-color:#eee;border:#ddd solid 1px;margin:2px"><small><strong>View:</strong></small>'''
        for i, name in enumerate(printed_videos):
            out += '''<small><a class="switchLink" id="switch_link_%s" data-video-switch="%s" href="#">%s</a></small>''' % (name, name, get_part_label(bfo, name, i, record_is_conf_p))
        out += '</span>'

    return out

def js_code_for_video_selection(first_video, movies):
    """Switch video script.

    .. note::

        Each video is wrapped with a div `.invenio-jwplayer-wrapper`
        which contains a `data-vicdo-id` attribute which holds the
        video id. On the part links are `data-video-switch` attribute which holds
        the video-id that choosen.

        The whole process is to hide the video
        wrapper div and show only the what with the value of the pressed
        `data-video-switch` id
    """
    html = '''
        <script type="text/javascript">
            var movies = new Array(%(movies)s);
            var _CDS_VIDEO_CLASS = 'invenio-jwplayer-wrapper';
            $(document).ready(function(){
                function movies_init(){
                    // Hide all movies
                    movies_hide();
                    $('a.switchLink').on('click', function(){
                        // Remove the `on` class from all tabs
                        $('a.switchLink').removeClass('on');
                        // Hide everything
                        movies_hide();
                        // Fetch the video ID as a string
                        var video_id = $(this).attr('data-video-switch');
                        // Activate the desired video
                        movies_activate_video(video_id);
                    });
                    // Activate the first one
                    movies_activate_video("%(first_video)s");
                }
                function movies_hide(){
                    $('.' + _CDS_VIDEO_CLASS).hide();
                    $.each(movies, function(index, item){
                        var player_id = 'invenio_player_container_' + item;
                        try{
                            if(jwplayer(player_id) != null){
                                jwplayer(player_id).pause(true);
                            }
                        }catch(error){
                            // There is an error;
                        }
                    });
                }
                function movies_activate_video(video_id){
                    // Check if the video is part of the list
                    if (movies){
                        if(movies.indexOf(video_id) > -1){
                            $('#switch_link_' + video_id).addClass('on');
                        }
                    }
                    try{
                        if(weblectures !== undefined){
                            if(weblectures.indexOf(video_id) > -1){
                                activate_lecture(video_id);
                                $('[data-video-id='+video_id+']').show();
                                return false;
                            }
                        }
                    }catch(error){
                        console.warn('Error loading the lecture');
                        // Enable the video
                        $('[data-video-id='+video_id+']').show();
                    }
                }
                movies_init();
            });
        </script>''' % {'first_video': first_video, 'movies': ','.join(["'%s'" % item for item in movies])}
    return html

def get_smil_file_path(mp4_path):
    """Returns the smil file path, if it exists"""

    mp4_path_tokens = mp4_path.split('/')
    smil_filepath = '%s/%s.smil' % ('/'.join(mp4_path_tokens[:-1]), mp4_path_tokens[-2])
    #does the smil_filepath exist?
    if not file_exists(smil_filepath):
        return ''
    smil_filepath = smil_filepath.split(MEDIAARCHIVE_PATH)[1]
    #return "%s/smil:Video/%s" %(CFG_VIDEO_STREAMER_URL, smil_file)
    return "http://wowza.cern.ch/vod/smil:Video/%s" % smil_filepath


def generate_thumbnails_file_content(recid, reportnumber, secure=True):
    """Returns the content"""

    if not recid and not reportnumber:
        return ''

    content = """WEBVTT\n\n"""

    content_item = \
"""
%(time1)s --> %(time2)s
%(thumbnail)s
"""

    if not recid:
        possible_recids = search_pattern(p='reportnumber:%s' % reportnumber)
        if len(possible_recids) == 1:
            recid = possible_recids[0]
    if not recid:
        return ''

    bfo = BibFormatObject(recid)
    media = get_media(bfo)

    try:
        total_duration = get_fieldvalues(recid, '300__a')[0]
        total_duration_in_sec = time_to_sec(total_duration)
    except (IndexError, ValueError):
        return ''

    time1 = '00:00:00.000'
    for count, index in enumerate(range(10, 110, 10)):
        time2 = create_vtt_time(index, total_duration_in_sec)
        content += content_item % {'time1': time1, 'time2': time2, 'thumbnail': get_thumbnail_at_percentage(media, count, reportnumber, secure)}
        time1 = time2

    return content

def get_thumbnail_at_percentage(media, index, reportnumber, secure=True):
    """Returns the thumbnail at percentage index"""
    try:
        thumbnail_dict = media['thumbnail']
        if reportnumber:
            frames_dict = thumbnail_dict[reportnumber]
        else:
            frames_dict = thumbnail_dict.values()[0]
        frames = frames_dict.keys()
        frames.sort()
        # Hotfix: let browser to decide the protocol https or http
        path = frames_dict[frames[index]][0]['path']
        if not secure:
            path = path.replace('https', 'http')
        return path
    except (KeyError, IndexError):
        return ''

def time_to_sec(total_duration):
    """Transform HH:MM:SS:MS in seconds"""
    total_duration = total_duration.replace('.', ":")
    items = total_duration.split(':')
    return int(items[0])*3600 + int(items[1])*60 + int(items[2])


def create_vtt_time(percentage, total_duration):
    vtt_time = percentage * total_duration / 100
    vtt_time_hh = vtt_time / 3600
    vtt_time_mm = (vtt_time - vtt_time_hh*3600) / 60
    vtt_time_ss = (vtt_time - vtt_time_hh*3600 - vtt_time_mm*60)

    return '%02d:%02d:%02d.000' %(vtt_time_hh, vtt_time_mm, vtt_time_ss)


def generate_jwplayer_config(bfo, multimedia, media, posterframe,
        is_restricted_record, media_name, embedded=False, video_width=640):
    """Generates the cofiguration of the player.

    :param int video_width: force fallback video width.
    """
    reportnumber = media_name
    try:
        copyright = bfo.field('542')['d']
    except (TypeError, KeyError):
        copyright = 'CERN'
    record_id = bfo.recID

    mp4_slaves = media.get('mp4', [])
    mp4_path = ''
    if mp4_slaves:
        mp4_path = select_best_path(mp4_slaves, video_width)

    flv_path = ''
    flv_slaves = media.get('flv', [])
    if flv_slaves:
        flv_path = select_best_path(flv_slaves, video_width)

    player_config = {}

    #video source
    player_config['sources'] = []
    if mp4_path:
        player_file = mp4_path
        smil_file = get_smil_file_path(mp4_path)
    elif flv_path:
        player_file = flv_path
        smil_file = ''
    else:
        player_file = ''
        smil_file = ''

    if smil_file:
        player_config['sources'].append({'file': "%s/playlist.m3u8" % smil_file})
        player_config['sources'].append({'file': "%s/jwplayer.smil" % smil_file})
    if player_file:
        player_config['sources'].append({'file': player_file})

    player_config['primary'] = 'flash'

    #video image
    player_config['image'] = posterframe
    #video size (the container should have the right size)
    player_config['width'] = '100%'
    #player_config['stretching'] = 'fill'
    if '4/3' in bfo.field('300__b'):
        player_config['aspectratio'] = '4:3'
    else:
        player_config['aspectratio'] = '16:9'
    # Chromecast support,
    player_config['cast'] = {
        "appid": "3495183F",
        "railcolor": "#e31e76",
        "loadscreen": "splash.jpg"
    }
    #appearence
    #player_config['skin'] = 'beelden'
    #disable analytics
    player_config['analytics'] = {'enabled': False, 'cookies': False}
    #streaming Android
    player_config['androidhls'] = True
    #captions, thumbnains
    player_config['tracks'] = []
    #captions
    if multimedia.get('subtitle', ''):
        if multimedia['subtitle'].get(media_name, ''):
            subtitles = multimedia['subtitle'][media_name]
            for lang in subtitles:
                try:
                    player_config['tracks'].append({
                               "file": subtitles[lang][0]['path'],
                               "label": lang,
                               "kind": "captions",
                               "default": True,
                           })
                except IndexError:
                    pass
    # player_config['captions'] = {'color': '#FFFFFF', 'fontSize': 24, 'backgroundOpacity': 0, 'edgeStyle': 'raised'}
    #thumbnails
    if not embedded:
        player_config['tracks'].extend([{
                     'file': '%s/video/%s/thumbnails' % (CFG_SITE_URL, record_id),
                     'kind': 'thumbnails'}])
    #modify the right click context
    if copyright == 'CERN':
        player_config['abouttext'] = 'About using CERN videos'
        player_config['aboutlink'] = 'http://copyright.cern.ch'
    #sharing & related videos
    if embedded:
        player_config['sharing'] = { \
              'code': '<iframe width="640" height="360" frameborder="0" src="%s/video/%s" allowfullscreen></iframe>' % (CFG_SITE_URL, reportnumber), \
              'link': '%s/record/%s' % (CFG_SITE_URL, record_id)}
        player_config['related'] = {
                     'file': '%s/video/%s/related' % (CFG_SITE_URL, reportnumber), \
                     'onclick': 'link', \
                     'dimensions': '180x100'}

    # WARNING EXTREME HACK PRACTICES ARE FOLLOWING
    # Some videos have non standard resolution and as a result the flash
    # version of the player has issues with the aspect ratio, that's why
    # for these records we are hardcoding the configuration to ``fill``
    if bfo.recID in [1309873, 1309874, 1309872, 1305408, 1334856] or player_config['aspectratio'] == '4:3':
        player_config['stretching'] = 'exactfit'
    return player_config


def _generate_display_for_video_jwplayer(bfo, multimedia, media, posterframe, is_restricted_record, media_name):
    """Generates the html code for the jwplayer"""

    initial_path = ''

    player_config = generate_jwplayer_config(bfo, multimedia, media, posterframe, is_restricted_record, media_name, False)

    playerconf = json.dumps(player_config, indent=4)

    try:
        stats_url = [filedict['file'] for filedict in player_config['sources'] if filedict['file'].find('wowza') < 0][0]
    except (IndexError, KeyError):
        stats_url = ''

    player_code = '''
        <div class="invenio-jwplayer-wrapper" data-video-id="%(media_name)s">
            <div id="invenio_player_container_%(media_name)s">Loading</div>
        </div>

       <script tpye="text/javascript">
           var player_config = %(player_config)s;
           // Get if is secure
           var protocol = (window.location.protocol == 'https:') ? 'https' : 'http';
           function jwFixImage() {
                var fileProtocol = player_config.image.split(':', 1)[0];
                if (fileProtocol != protocol) {
                    player_config.image = player_config.image.replace(fileProtocol, protocol);
                }
           }
           // Try to fix protocol conflicts
           try {
                $.when(
                    jwFixImage(),
                    $.each(player_config.tracks, function(index, item) {
                        var fileProtocol = item.file.split(':', 1)[0];
                        if (fileProtocol != protocol) {
                            player_config.tracks[index].file = item.file.replace(fileProtocol, protocol);
                        }
                    }),
                    $.each(player_config.sources, function(index, item) {
                        var fileProtocol = item.file.split(':', 1)[0];
                        if (fileProtocol != protocol) {
                            player_config.sources[index].file = item.file.replace(fileProtocol, protocol);
                        }
                    })
                ).done(function (){
                    jwPlayerInit();
                });
            } catch (error) {
                console.warn('ERROR', error);
                jwPlayerInit();
            }

           function jwPlayerInit() {
                jwplayer("invenio_player_container_%(media_name)s").setup(player_config);
                document.write('<img src="%(site_url)s/tools/videos_logs.py/?recid=%(recid)s&f=' + encodeURIComponent("%(media_url)s") + '" width="0px" height="0px"/>');
           }
        </script>''' % {
                 'player_config': playerconf,
                 'site_url': CFG_SITE_URL,
                 'media_url': stats_url.split(MEDIAARCHIVE_PATH)[1],
                 'media_name': media_name,
                 'recid': bfo.recID
                 }

    return player_code


def _generate_display_for_video_jwplayer_jw5(media, posterframe, is_restricted_record, media_name):
    """This function, previously called _generate_display_for_video_jwplayer has been deprecated
       with the upgrade to jw6"""

    mp4_slaves = media.get('mp4', [])
    mp4_path = ''
    mp4_best_path = ''
    if mp4_slaves:
        mp4_path = select_best_path(mp4_slaves, 640)
        mp4_best_path = select_best_bitrate(mp4_slaves)

    flv_path = ''
    flv_slaves = media.get('flv', [])
    flv_best_path = ''
    if flv_slaves:
        flv_path = select_best_path(flv_slaves, 640)
        flv_best_path = select_best_bitrate(flv_slaves)

    player_config = {}
    #General config
    player_config['width'] = '640px'
    player_config['height'] = '360px'
    player_config['image'] = posterframe

    if mp4_path:
        player_config['file'] = mp4_path
        levels = get_level_list(mp4_slaves)
        if levels:
            player_config['levels'] = levels
    elif flv_path:
        player_config['file'] = flv_path
        levels = get_level_list(flv_slaves)
        if levels:
            player_config['levels'] = levels
    else:
        player_config['file'] = ''

    player_config['wmode'] = 'opaque'
    player_config['controlbar.position'] = 'over'
    player_config['controlbar.idlehide'] = 'true'

    player_config['plugins'] = {}

    #player_config['plugins']['qualitymonitor-2'] = {}

    player_config['modes'] = []
    player_config['modes'].append({'type': 'flash', 'src': '%s/mediaplayer.swf' % CFG_SITE_URL})
    if mp4_path:
        player_config['modes'].append({'type': 'html5', 'config': {'file': mp4_path, 'provider': 'video'}})
    player_config['modes'].append({'type': 'download', 'config': {'file': player_config['file'], 'provider': 'video'}})

    initial_path = player_config['file']
    if not initial_path:
        return ""

    if mp4_best_path:
        best_path = mp4_best_path
    elif flv_best_path:
        best_path = 'flv:%s' % flv_best_path #wowza4.0
    else:
        best_path = initial_path

    if not is_restricted_record:
        player_config['streamer'] = CFG_VIDEO_STREAMER_URL
        player_config['provider'] = 'rtmp'
        player_config['file'] = player_config['file'].split(MEDIAARCHIVE_PATH)[1]
        if player_config['file'].find('.flv') > -1: #wowza4.0
            player_config['file'] = 'flv:%s' % player_config['file']
        if mp4_path and player_config.get('levels', ''):
            player_config['levels'] = get_level_list(mp4_slaves, True)
        elif flv_path and player_config.get('levels', ''):
            player_config['levels'] = get_level_list(flv_slaves, True)
            for indx in range(0, len(player_config.get('levels', []))): #wowza4.0
                player_config['levels'][indx]['file'] = 'flv:%s' % player_config['levels'][indx]['file']

    #this breaks on mobiles
    #if mp4_path:
    #    ios_file = "http://wowza.cern.ch:1935/vod/_definist_/" + mp4_path.split(MEDIAARCHIVE_PATH)[1] + '/playlist.m3u8'

    playerconf = json.dumps(player_config, indent=4)

    player_code = '''
       <div id="invenio_player_container_%(media_name)s">Loading</div>
          <script language="javascript">
        var iOS = ( navigator.userAgent.match(/(iPad|iPhone|iPod)/i) ? true : false );
        var player_config = %(player_config)s;

        if ((player_config['modes'][0]['type'] == 'html5') && (player_config['file'].indexOf('WebLectures') > -1) && (iOS)){
            player_config['modes'][0]['config']['file'] = 'smil:Video/' + player_config['file'].replace('-mobile.mp4', '.smil')
        }
        jwplayer("invenio_player_container_%(media_name)s").setup(player_config);
        document.write('<img src="%(site_url)s/tools/videos_logs.py/?f=' + encodeURIComponent("%(media_url)s") + '" width="0px" height="0px"/>');
        </script>''' % {
                 'player_config': playerconf,
                 'site_url': CFG_SITE_URL,
                 'media_url': initial_path.split(MEDIAARCHIVE_PATH)[1],
                 'media_name': media_name
                 }
    # ADD support HD toggle
    player_code += _generate_HD_button(best_path, initial_path)

    """player_code = '''
       <div id="invenio_player_container_%(media_name)s" %(display)s>Loading</div>
       <script language="javascript">
            var player_config = %(player_config)s;
            jwplayer("invenio_player_container_%(media_name)s").setup(player_config);
            document.write('<img src="%(site_url)s/tools/videos_logs.py/?f=' + encodeURIComponent("%(media_url)s") + '" width="0px" height="0px"/>');
        </script>''' % {
                 'player_config': playerconf,
                 'site_url': CFG_SITE_URL,
                 'media_url': initial_path.split(MEDIAARCHIVE_PATH)[1],
                 'media_name': media_name}
    """
    return player_code


def get_video_posterframe(media_posterframes, nth_percentage, nth_dimension):
    """Return the path to the posterframe that has the NiceToHave_percentage
       and NiceToHave_dimension
       If no posterframe is found for nth_dimension, we take the first
       available from nth_percentage;
       If nth_percentage is not available, we take the first posterframe with
       nth_dimension;
       If none of the above, we take the first posterframe available.
       """
    if not media_posterframes:
        return ''

    #try to return the posterframe, at the nth_percentage and nth_dimension
    if nth_percentage in media_posterframes:
        for item in media_posterframes[nth_percentage]:
            if item.get('dimension', '') == nth_dimension and item.get('path', ''):
                return item['path']
        #there is no posterframe with nth_dimension, return another one
        for item in media_posterframes[nth_percentage]:
            if item.get('path', ''):
                return item['path']


    #none of the above worked, return the first posterframe with nth_dimension
    for percentage in media_posterframes:
        for item in media_posterframes[percentage]:
            if item.get('dimension', '') == nth_dimension and item.get('path', ''):
                return item['path']

    # nothing worked so far, return the first posterframe
    for percentage in media_posterframes:
        for item in media_posterframes[percentage]:
            if item.get('path', ''):
                return item['path']

    return ''

def _generate_HD_button(url, normal_url):
    """ Return a button which toggles HD functionality """
    # check which key is availble and get the path
    out = ''
    if url and url != normal_url:
        out = '''
                <style type="text/css">
                    .toggle_wrapper{
                        display         : block;
                        position        : relative;
                        text-align      : right;
                        text-decoration : none!important;
                        margin-top      : 5px;
                        max-width       : 640px;
                    }
                    .toggle_hd{
                        border           : 1px solid #ccc;
                        padding          : 2px 2px 2px 15px;
                        border-radius    : 3px;
                        background-color : #f6f6f6 !important;
                        position         : relative;
                    }
                    .toggle_hd:hover{
                        text-decoration: none;
                    }
                    .toggle_hd::before{
                        content       : ' ';
                        position      : absolute;
                        width         : 8px;
                        height        : 8px;
                        background    : grey;
                        top           : 0;
                        left          : 3px;
                        bottom        : 0;
                        margin        : auto;
                        border-radius : 10px;
                    }
                    .toggle_hd.normalMode::before{
                        background: #ccc;
                    }
                    .toggle_hd.hdMode::before{
                        background: #0aa80a;
                    }
                    .toggle_hd.hdMode:hover,
                    .toggle_hd.hdMode:hover::before{
                        background : #0cd00c;
                        color      : #0cd00c!important;
                    }
                    .toggle_hd.normalMode:hover,
                    .toggle_hd.normalMode:hover::before{
                        background : #bbb8b8;
                        color      : #bbb8b8!important;
                    }
                    .toggle_hd.hdMode{
                        color: #0aa80a!important;
                    }
                    .toggle_hd.normalMode{
                        color: #ccc!important;
                    }
                </style>
                <script type="text/javascript">
                // Check if the browser is IE
                function isIE(){
                    var msie = window
                               .navigator
                               .userAgent
                               .indexOf("MSIE ");
                    if (msie > 0)
                        return true;
                    return false;
                }
                $(document).ready(function(){
                    $('body').on('click', '.toggle_hd', function(){
                        var $that = $(this),
                            pos   = jwplayer().getPosition();
                        if($that.data('state') == "normal"){
                            // change state to HD
                            $that.data('state', "hd");
                            url = $that.data('hd-url');
                            $that.removeClass('normalMode')
                                 .addClass('hdMode');
                        }else{
                            // change state to HD
                            $that.data('state', "normal");
                            url = $that.data('nm-url');
                            $that.removeClass('hdMode')
                                 .addClass('normalMode');
                        }
                        if(url !== undefined && url !=''){
                            jwplayer().load({
                                file : url
                            });
                            if(!isIE()){
                                setTimeout(function(){
                                    jwplayer().seek(pos);
                                }, 0);
                            }
                        }
                    })
                })
              </script>'''
        out += '''<div class="toggle_wrapper"><a class="toggle_hd normalMode"
                    data-state="normal"
                    data-hd-url="%s"
                    data-nm-url="%s"
                    href="javascript:void(0)">HD</a></div>''' % (url, normal_url)
    return out

def _generate_display_for_weblecture_new(lecture_id, year, is_restricted_record, bfo):
    """Generate html code for new weblectures (Feb. 2014)"""
    # The weblecture iframe
    html =  """<iframe class="lecture" src="%s" width="1020px" height="600px" allowfullscreen scrolling="no" frameborder="0"></iframe>""" % newweblecture_player %(year, lecture_id)

    # Only if the record is on e-learning collection add support of asciinema player
    collections = bfo.fields('980__a') + bfo.fields('980__b')
    if 'E-LEARNING' in collections:
        # Add the asciinema player support
        asciinema = (
            '<script src="/js/asciinema-player.js" type="text/javascript"></script> '
            '<link href="/css/asciinema-player.css" rel="stylesheet" type="text/css" /> '
        )
        html = asciinema + html
    return html

def _generate_display_for_weblecture(weblecture_movies, is_restricted_record, bfo):
    """Generate html code for weblectures"""
    if not weblecture_movies:
        return ''

    weblectures_html = '<br/>'

    weblectures_html += '''<script type="text/javascript" src="/js/swfobject.js"></script>'''
    weblectures_html += '''
        <script type="text/javascript">
            var flash_video_player="%(flash_video_player_url)s"
            var weblectures = new Array(%(movies)s);
            var flash_paths = new Array(%(flash_paths)s);
            function activate_lecture(lecture_id){
                var item_index = weblectures.indexOf(lecture_id);
                $('#switch_link_' + lecture_id).addClass('on');
                $('#weblecture_player_' + lecture_id).show();
                var params = {'flashvars': "baseURL=" + flash_paths[item_index],
                              'allowFullScreen': "true",
                              'allowScriptAccess': "always"};
                swfobject.embedSWF("%(weblecture_flash_video_player_url)s", "weblecture_player", "1020", "700", "10.1.0", '', {}, params, {});
            }
            </script>''' % {'movies': ','.join(["'%s'" % item[0] for item in weblecture_movies]),
                            'flash_paths': ','.join(["'%s'" % '/'.join(item[1].split('/')[:-1]) for item in weblecture_movies]),#remove last "flash.html"
                            'flash_video_player_url': flash_video_player_url,
                            'weblecture_flash_video_player_url': weblecture_flash_video_player_url
                           }
    weblectures_html += '''<div id="weblecture_player">'''
    for item in weblecture_movies:
        weblectures_html += '''<div style="display:none" class="wl_player" id="weblecture_player_%(player_id)s">''' % {'player_id': item[0]}
        if item[2]: # if an mp4 path exists
            weblectures_html += _generate_display_for_video_jwplayer(bfo, item[4], item[3], '', is_restricted_record, item[0])
        else:
            weblectures_html += '<img src="%s" alt="Not yet available" />' % PLACEHOLDER_IMG_URL
        weblectures_html += '''</div>'''

    weblectures_html += '''</div><br/>'''
    return weblectures_html

def _generate_display_for_assets(recids):
    """Returns the html code for displaying the assets"""

    css_code = '''
<style type="text/css">
.toc_asset_item_container {
    position: relative;
    width: 180px;
}

.toc_asset_item_thumb {
    float: left;
}
.toc_asset_item_desc {
    font-size: 90%;
    margin-top: 5px;
    color: #333333;
    line-height: 1.2em;
}

a.toc_asset_item_desc_link {
    float: left;
    color: #1B5C7F;
    font-weight: bold;
}

.toc_ul{
    margin: 0;
    padding: 0;
}

.toc_ul_title{
    font-weight: bold;
    color: #333333;
    margin-bottom: 10px;
}
</style> '''
    # Add css code for download buttons
    html_code = '''<div class="toc_ul_title">Number of videos: %s</div>''' %len(recids)
    html_code += '''<ul class="toc_ul">'''

    for recid in recids:
        bfo = BibFormatObject(recid)
        additional_info = [bfe_CERN_duration_multimedia.format_element(bfo), bfe_CERN_languages.format_element(bfo)]
        additional_info = [item for item in additional_info if item]

        html_code += """<li class="toc_asset_item">
             <div class="toc_asset_item_container"><a href="%(record_url)s">%(thumbnail)s</a></div>
             <div class="toc_asset_item_desc">
                <a class="toc_asset_item_desc_link" href="%(record_url)s">%(report_number)s</a><br/>
                <i>%(title)s</i><br/>
                %(additional_info)s
             </div>
        </li>""" % {'record_url': '%s/%s/%s' %(CFG_SITE_URL, CFG_SITE_RECORD, recid),
                    'thumbnail': format_element(bfo, display_as="embed", media_type="thumbnail", max_nb="1", resolve_movie_path='no', magnify="no", thumb_link_to_detailed_record="no"),
                    'report_number': bfo.field('037__a'),
                    'title': bfe_CERN_title_multimedia.format_element(bfo, main_only="yes", length="25"),
                    'additional_info': ' | '.join(additional_info)
                   }

    html_code += '</ul>'
    return css_code + html_code


def _generate_download_movie_box(bfo, multimedia, ordered_names, record_is_conf_p):
    """Generates the html code for the Download box"""

    #Note: the css for the hoover action is taken from video_platform_record.css
    css_code = '''<meta http-equiv="X-UA-Compatible" content="IE=edge" />
                  <style type="text/css">
                  #download_movie_box_internal_link, .more_avail_bitrates_link{
                      background-color: #FAFAFA;
                      border-radius: 5px;
                      box-shadow: 1px 1px 1px 1px #CCCCCC;
                      margin: 5px 2px;
                      padding: 3px;
                      color: #222222;
                      text-align: center;
                      display: inline-block;
                      line-height: 110%;
                      vertical-align: middle;
                  }
                  #download_movie_box_internal_link:hover, .more_avail_bitrates_link:hover, #more_avail_bitrates_links:hover{
                      color: #FFFFFF;
                      cursor: pointer;
                      text-decoration: none;
                      background: rgb(58,58,58); /* Old browsers */
                      background: -moz-linear-gradient(top, rgba(58,58,58,1) 0%, rgba(125,126,125,1) 100%); /* FF3.6+ */
                      background: -webkit-gradient(linear, left top, left bottom, color-stop(0%,rgba(58,58,58,1)), color-stop(100%,rgba(125,126,125,1))); /* Chrome,Safari4+ */
                      background: -webkit-linear-gradient(top, rgba(58,58,58,1) 0%,rgba(125,126,125,1) 100%); /* Chrome10+,Safari5.1+ */
                      background: -o-linear-gradient(top, rgba(58,58,58,1) 0%,rgba(125,126,125,1) 100%); /* Opera11.10+ */
                      background: -ms-linear-gradient(top, rgba(58,58,58,1) 0%,rgba(125,126,125,1) 100%); /* IE10+ */
                      filter: progid:DXImageTransform.Microsoft.gradient( startColorstr='#3a3a3a', endColorstr='#7d7e7d',GradientType=0 ); /* IE6-9 */
                      background: linear-gradient(top, rgba(58,58,58,1) 0%,rgba(125,126,125,1) 100%); /* W3C */
                      -webkit-box-shadow: 0px 0px 0px 0px #b3b3b3;
                      -moz-box-shadow: 0px 0px 0px 0px #b3b3b3;
                      box-shadow: 0px 0px 0px 0px #b3b3b3;
                  }
                  .more_avail_bitrates_link:active{
                      background-color: #FAFAFA;
                      color: #222222;
                  }
                  span#download_movie_box_internal_link_item{
                      font-size: x-small;
                  }
                  .more_avail_bitrates_box{
                      background-color: #FAFAFA;
                      color: #222222;
                      font-size: x-small;
                      box-shadow: 1px 1px 1px 1px #CCCCCC;
                      border-radius: 5px;
                      padding: 2px;
                      margin: 5px 2px;
                  }
                  #highres_box{
                      background-color: #FAFAFA;
                      color: #222222;
                      font-size: x-small;
                      box-shadow: 1px 1px 1px 1px #CCCCCC;
                      border-radius: 5px;
                      padding: 2px;
                      margin: 5px 2px;
                      display: inline-block;
                  }
                  a.more_avail_bitrates_link{
                      color: #222222;
                      background-color: #FAFAFA;
                  }
                  #more_avail_bitrates_links{
                      padding: 3px 7px;
                      border-radius: 3px;
                      color: #222222;
                      vertical-align: middle;
                  }
                  #high_res_ext{
                      font-size: small;
                  }
                  #high_res_help_img{
                      vertical-align: middle;
                  }
                  #download_movie_box_title{
                      text-align: center;
                  }
                  #download_movie_box_part_label{
                      font-weight: bold;
                      text-align: center;
                  }
                  #download_movie_box_format_label{
                      font-size: small;
                      font-weight: bold;
                      padding-right: 15px;
                      padding-left: 15px;
                      vertical-align: middle;
                  }
                  #download_movie_box_high_res_link{
                      color: #444;
                  }
                  #download_movie_box{
                      border: #CCCCCC solid 1px;
                      margin: 0 auto;
                      width: 90%;
                  }
                  </style>'''

    js_code = '''
                 <script>
                 $(document).ready(function(){
                     $('.more_avail_bitrates_box').hide();

                     $('a.more_avail_bitrates_link').click(function(){
                         var id_box = $(this).attr('id').replace('link', 'box');
                         $('#' + id_box).slideToggle();
                         $(this).text($(this).text() == 'More..'? 'Less..' : 'More..');
                         return false;
                      });
                 });
               </script>'''

    FORMAT_LABELS = {'flv': 'Flash',
                     'wmv': 'Windows Media',
                     'wma': 'Windows Media',
                     'rm' : 'Real Media',
                     'ram': 'Real Media',
                     'mov': 'Quicktime',
                     'ogg': 'Ogg Vorbis'
                    }

    HIGH_RES_HELP_LINK = '%s/help/high-res-multimedia?ln=%s' % (CFG_SITE_URL, bfo.lang)
    videos = []
    for name in ordered_names["slave"]:
        dict_of_formats =  multimedia["slave"][name]
        # For different movies/parts
        movie_info = {}
        movie_info['name'] = name
        try:
            master_path = multimedia['master'][name].values()[0][0]['path']
            master_path = master_path.replace('\\\\cern.ch\\dfs\\Services\\MediaArchive',
                                                  'https://mediastream.cern.ch/MediaArchive')
            master_path = master_path.replace('\\', '/')
            movie_info['master'] = master_path
        except:
            movie_info['master'] = ''

        movie_info['format'] = {}
        for fmt in dict_of_formats:
            available_video_bitrates = [(resource.get('path',''), resource.get('video_bitrate','')) for resource in dict_of_formats[fmt] if resource.get('label', '').find('Multirate') < 0] # do not add the multirates to the main formats, only to the 'More..' tab
            available_video_bitrates.sort(key=lambda tuple: tuple[1]) #sort on bitrates
            low_quality_link = high_quality_link = medium_quality_link = ''
            if len(available_video_bitrates) < 1:# there are no bitrates available
                continue
            medium_video_bitrates = available_video_bitrates[0:]
            if available_video_bitrates[0][1] > 0 and available_video_bitrates[0][1] <= 150: # check to see if the first one is the low quality one
                low_quality_link = available_video_bitrates[0]
                medium_video_bitrates = medium_video_bitrates[1:]
            if available_video_bitrates[-1][1] > 500: # check to see if the last one is the high quality, but also be backwords compatible
                high_quality_link = available_video_bitrates[-1]
                medium_video_bitrates = medium_video_bitrates[:-1]
            if medium_video_bitrates:
                medium_quality_link = medium_video_bitrates[len(medium_video_bitrates)/2] # take the middle one
                medium_video_bitrates.remove(medium_quality_link) # list with the rest of the bitrates
            medium_video_bitrates.extend([(resource.get('path',''), "Multi%s" % resource.get('video_bitrate','')) for resource in dict_of_formats[fmt] if resource.get('label', '').find('Multirate') > -1]) #add Multirates, if any
            movie_info['format'][fmt] = (low_quality_link, medium_quality_link, high_quality_link, medium_video_bitrates)
        videos.append(movie_info)

    if not videos: # make sure there is something to print
        return ''

    videos_content = {}
    for i, movie in enumerate(videos):
        videos_content[i] = {}
        videos_content[i]['format'] = {}

        # Part label
        if len(videos) > 1: #the record has several parts
            videos_content[i]['movie_part_label'] = get_part_label(bfo, movie['name'], i, record_is_conf_p)

        for fmt in movie['format']:
            if not movie['format'][fmt]:
                continue
            # Format label
            videos_content[i]['format'][fmt] = {}

            #Major format links
            (low_quality_link, medium_quality_link, high_quality_link, dummy) = movie['format'][fmt]
            videos_content[i]['format'][fmt]['available_rates'] = []
            for count, label in enumerate(['Low', 'Medium', 'High']):
                if movie['format'][fmt][count]:
                    url = movie['format'][fmt][count][0]
                    bitrate = movie['format'][fmt][count][1]
                    videos_content[i]['format'][fmt]['available_rates'].append( \
                     (label, \
                      bitrate and '(%s kbps)' % bitrate or '',
                      get_url_customevent(url, "media_download", [movie['name'], "movie", "%s %s" % (fmt, label), "WEBSTAT_IP"]))) #(label, bitrate, link)
                else:
                    videos_content[i]['format'][fmt]['available_rates'].append(('', '', ''))
            # check if we actually have any bitrates
            bitrates = [bitrate for (dummy, bitrate, dummy) in videos_content[i]['format'][fmt]['available_rates'] if bitrate]
            if bitrates:
                videos_content[i]['format'][fmt]['movie_format_label'] = FORMAT_LABELS.get(fmt, fmt.capitalize())

            #Minor format links
            more_available_formats = movie['format'][fmt][3]
            if more_available_formats:
                #display all the available formats
                videos_content[i]['format'][fmt]['more_available_rates'] = \
                   [('%s kbps' % bitrate, \
                    get_url_customevent(url, "media_download", [movie['name'], "movie", "%s %s" % (fmt, bitrate), "WEBSTAT_IP"])) \
                  for (url, bitrate) in more_available_formats] #(label, link)
        #High-res
        if movie.get('master', ''):
            high_res_versions = get_high_res_info(movie['master'])
            videos_content[i]['high_res_links'] = [('%s/tools/mediaarchive.py/copyright_notice?recid=%s&master_path=%s&ln=%s&reference=%s' % \
                                                     (CFG_SITE_SECURE_URL, bfo.recID, cgi.escape(this_master_path), bfo.lang, movie.get('name', '')), \
                                                   extension, \
                                                   format_size(size)) \
                                                      for (extension, (size, this_master_path)) in high_res_versions.iteritems()] #(link, label, size)
            videos_content[i]['high_res_label'] = ('WebLecture' in movie['master']) and ' (Speaker video)' or ''

    #Generate the HTML code
    html = ''

    html += '''<table id="download_movie_box">'''
    for index in videos_content:
        video_content = videos_content[index]
        if video_content.get('movie_part_label', ''):
            html += '''<tr><td colspan="5" id="download_movie_box_part_label">%s</td></tr>''' % video_content['movie_part_label']
        for format_idx, fmt in enumerate(video_content['format']):
            video_content_format = video_content['format'][fmt]
            if video_content_format.get('movie_format_label', ''):
                html += '<tr><td align="right" valign="top" id="download_movie_box_format_label">%s:</td>' % video_content_format['movie_format_label']
            for (label, bitrate, link) in video_content_format['available_rates']:
                if bitrate:
                    #html += '<td><div id="download_movie_box_internal_link"><a href="%s" id="download_movie_box_internal_link_item">%s</a><span id="download_movie_box_internal_link_item">%s</span></td>' % (link, label, bitrate)
                    html += '<td><a id="download_movie_box_internal_link" href="%s">%s<br/><span id="download_movie_box_internal_link_item">%s</span></a></td>' % (link, label, bitrate)
                else:
                    html += '<td></td>'
            if video_content_format.get('more_available_rates', ''):
                html += '<td><a class="more_avail_bitrates_link" id="more_link_%s_%s" href="#">More..</a></td></tr>' % (index, format_idx)
                html += '<tr><td/><td colspan="4"><div class="more_avail_bitrates_box" id="more_box_%s_%s">%s</td></tr>' % (index, format_idx, \
                          ' '.join(['<a id="more_avail_bitrates_links" href="%s">%s</a>' % (link, label) for (label, link) in video_content_format['more_available_rates']]))
        if video_content.get('high_res_links', ''):
            # Check if we have 4k video - check if "4k" exists in any of the keywords(if yes, indicate it in the video label)
            keywords = [keyword.get('a').lower().split() for keyword in bfo.fields("6531_")]
            if any('4k' in keyword for keyword in keywords):
                high_resolution_label = "4K"
            else:
                high_resolution_label = "High-resolution"
            html += '<tr><td align="right" valign="top" id="download_movie_box_format_label">%s:</td>' % high_resolution_label
            html += '<td colspan="4" align="left"><div id="highres_box">%(high_res_links)s %(high_res_help)s</div></td></tr>' % \
                      {'high_res_links': ' '.join(['<a id="more_avail_bitrates_links" href="%s"><span id="high_res_ext">%s</span> (%s)</a>' % (link, label.upper(), size) for (link, label, size) in video_content['high_res_links']]),
                       'high_res_help': '<a href="%(link)s"><img id="high_res_help_img" src="/img/help.png" alt="%(label)s" title="%(label)s"></a>' % \
                                   {'link': HIGH_RES_HELP_LINK,
                                    'label': 'Need help to download high-resolutions?'
                                   }
                      }
    # check if we have subititles
    subtitles = [subtitle for subtitle in bfo.fields('8567_') if \
        subtitle.get('x') == 'subtitle']
    if subtitles:
        subtitle_row = (
            "<tr>{header}{body}</tr/>"
        )
        subtitle_column = (
            "<td colspan='4' align='left'>"
            "<div class='cds-video-subtitles'>"
            "<a id='download_movie_box_internal_link' href='{0}'>{1}</a></td>"
        )
        subtitle_header = (
            '<td align="right" valign="top" '
            'id="download_movie_box_format_label">{0}:</td>'
        ).format("Subtitles")
        columns = []
        for subtitle in subtitles:
            columns.append(
                subtitle_column.format(
                    subtitle.get('u', '#'),
                    subtitle.get('y', '').replace('subtitle', '').title().strip()
                )
            )
        html += subtitle_row.format(header=subtitle_header, body="".join(columns))
    # close the table
    html += '</table>'
    return css_code + js_code + html

def _generate_css_code_for_hide_embed_button():
    """
    Hide the embed button
    """
    return """<style>#video_controlbutton_embed {display: none;}</style>"""

def _generate_css_code_for_hide_control_buttons(button_list):
    """
    Hide the control buttons in case no slaves are available
    """
    out = '<style>'
    out += """
        .video_control_container,
        #video_controlbutton {
            display: none;
        }"""
    if button_list:
        button_list_t = [button.strip().lower() for button in button_list.split(',')]
        for button in button_list_t:
            out += '#video_detailbox_%s {display: none;}' %button
    out += '</style>'
    return out


def _generate_js_css_code_for_control_buttons(button_list_s, close=False):
    """
    Generates the javascript code for connecting a list of buttons with their containes.
    @param button_list: string, a comma separated list of button names
    """
    css_code = '''
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <style type="text/css">
    /* .video_controlbutton, .video_controlbutton:link{
        margin-right  : 20px;
        padding-left  : 20px;
        padding-right : 20px;
        color         : #4D94CC;
        font-size     : 16px;
        font-weight   : bold;
        position      : relative;
    }
    .video_controlbutton:hover, .video_controlbutton.hover{
        cursor          : pointer;
        text-decoration : none;
        color           : #333;
    }
    .video_controlbutton:after{
        content      : " ";
        width        : 0;
        right        : 0;
        top          : 9px;
        position     : absolute;
        height       : 0;
        border-left  : 5px solid transparent;
        border-right : 5px solid transparent;
        border-top   : 5px solid #4D94CC;
    }
    .video_controlbutton.hover:after{
        content       : " ";
        width         : 0;
        right         : 0;
        top           : 9px;
        position      : absolute;
        height        : 0;
        border-left   : 5px solid transparent;
        border-right  : 5px solid transparent;
        border-bottom : 5px solid #333;
        border-top    : none!important;
    }*/
    </style>'''

    if not button_list_s:
        return ''

    if button_list_s:
        button_list = [button.strip().lower() for button in button_list_s.split(',')]

    js_code = '''
        <script>
        $(document).ready(function(){'''
    if not close:
        start_index = 1 #first one should be active
    else:
	start_index = 0
    for button in button_list[start_index:]:
        js_code += '''
            $('#video_detailbox_%s').hide();''' % button
    for index, button in enumerate(button_list):
        other_buttons = button_list[:index] + button_list[(index+1):]
        js_code += '''
            $('#video_controlbutton_%(button)s').click(function(){
                %(hide_others)s
                $('#video_detailbox_%(button)s').toggle();
                %(remove_hover_others)s
                if ($('#video_detailbox_%(button)s').is(':hidden')){
                    $(this).removeClass('hover');
                }else{
                    $(this).addClass('hover');
                }
                return false;
            });''' % {'button': button,
                      'hide_others': '\n'.join(['''$('#video_detailbox_%s').hide();''' % other_b for other_b in other_buttons]),
                      'remove_hover_others': '\n'.join(['''$('#video_controlbutton_%s').removeClass('hover');''' % other_b for other_b in other_buttons])
                     }
    js_code += '''});
         </script>'''
    return css_code + js_code

def _generate_embed_movie_box(bfo, iframe=''):
    """
    Generates the code for the embed box
    """
    code_dict = front_code_to_embed_video(bfo)
    if not code_dict and not iframe:
        return ''

    css_code = '''
        <style type="text/css">
            #embed_video_box{
                background-color: #EEE;
                border: #DDD solid 1px;
                margin:0 auto;
                width: 90%;
            }
            #embed_video_box_header{
                text-align: center;
                font-size:small;
            }
            </style>'''
    if iframe:
        # Display the embed code for lectures
        html_code = '''
            <table id="embed_video_box">
                <tr><th colspan="4" id="embed_video_box_header">Copy-paste this code into your page:</th></tr>
                <tr><td><textarea readonly="readonly" rows="3" cols="60">{iframe}</textarea></td></tr>
            </table>'''.format(iframe=iframe)
    else:
        html_code = '''
            <table id="embed_video_box">
                <tr><th colspan="4" id="embed_video_box_header">Copy-paste this code into your page:</th></tr>
                <tr><td><textarea readonly="readonly" rows="3" cols="60">%s</textarea></td></tr>
            </table>''' % '\n'.join(sorted(code_dict.values()))
    return css_code + html_code


def _generate_textual_paths_with_labels(multimedia, ordered_names, media_type, max_nb):
    """Generates a list with all the paths and their labels for media_type for max_nb of videos"""
    paths = []
    for i, name in enumerate(ordered_names[media_type]):
        movie =  multimedia[media_type][name]
        if max_nb.isdigit() and (i + 1) > int(max_nb):
            # stop as soon as max number of videos is reached
            break
        paths.extend([(media['path'], media.get('label', ''), media.get('filename', '')) for media in movie.values()[0] if media.get('path', '')])
    return paths


def print_image(multimedia, name, percent=50, media_type="thumbnail",
                width=None, max_width=None, film_effect="yes",
                thumb_link_to_detailed_record="no", recid=None,
                is_restricted_record=False, hide_restricted_record=False):
    """
    Returns one thumbnail/posterframe of the video, at given percentage in time
    and given width. 'media_type' decides if thumbnail or posterframe is to
    be printed.

    If 'percent' does not exist in multimedia, then look for percent in another
    media_type. If still not found, first existing image is taken.

    @param multimedia the structure returned by get_media
    @param name the name of the video from which images are taken
    @param percent a multiple of 10 in [10, 90]
    @param media_type 'thumbnail' or 'posterframe'
    @param width the width of the image, as int. If empty string, use original size
    @param film_effect if 'yes', print special border that mimics film
    @param thumb_link_to_detailed_record if yes, the thumbnail link to the detailed record page
    @param recid record. Used to link to record if thumb_link_to_detailed_record == 'yes'
    @param is_restricted_record: true if records (and linked media) are restricted
    @param hide_restricted_record: if is_restricted_record == True, print a placeholder image
    """
    if is_restricted_record and hide_restricted_record: # and not get_restricted_collections_for_recid(recid):
        return '<img src="%s" alt="Restricted" style="margin-right:5px;width:100%%;max-width:190px"/>' % PLACEHOLDER_RESTRICTED_IMG_URL


    alternative_media_type = [media_t for media_t in IMAGE_MEDIA_TYPE if media_t != media_type][0]
    image_path = None
    image_dimension = (None, None)

    avail_media_type = ''
    if multimedia[media_type][name].get(percent, []):
        avail_media_type = media_type
    elif multimedia[alternative_media_type][name].get(percent, []):
        avail_media_type = alternative_media_type
    if avail_media_type:
        max_width = max([image['dimension'][0] for image in multimedia[avail_media_type][name][percent] \
                             if image['dimension'][0] is not None])
        if max_width == 0:
            max_width = None
        image = [img for img in multimedia[avail_media_type][name][percent] \
                      if img['dimension'][0] == max_width][0]
        image_path = image.get('path', None)
        image_dimension = image.get('dimension', (None, None))

    if not image_path:
        # Take first image found
        avail_media_type = ''
        if multimedia[media_type][name]:
            avail_media_type = media_type
        elif multimedia[alternative_media_type][name]:
            avail_media_type = alternative_media_type
        if avail_media_type:
            for images in multimedia[avail_media_type][name].values():
                for image in images:
                    image_path = image.get('path', None)
                    image_dimension = image.get('dimension', (None, None))
                    if image_path:
                        break
    if not image_path:
        #We were not able to find an image
        return  ''

    (image_width, image_height) = resize_dimension(image_dimension, width, max_width)

    # width
    image_width_tag = ''
    css_film_effect_div_width_style = ''
    if image_width is not None:
        image_width_tag = 'width="%spx"' % image_width
        css_film_effect_div_width_style = 'width:%spx;' % (image_width + 30)

    # height
    image_height_tag = ''
    if image_height is not None:
        image_height_tag = 'height="%spx"' % image_height

    # Link image to detailed record page when specified
    link_prefix = ''
    link_suffix = ''
    if thumb_link_to_detailed_record.lower() == 'yes' and recid is not None:
        link_prefix = '<a href="%s/%s/%s">' % (CFG_SITE_URL, CFG_SITE_RECORD, recid)
        link_suffix = '</a>'
    if film_effect.lower() == "yes":
        return ''' <div style="background:#000;padding-left:5px;padding-right:5px;%(css_film_effect_div_width_style)smargin:4px auto;">
                       <div style="border-left:#fff dashed 10px;border-right:#fff dashed 10px;padding-top:5px;padding-bottom:5px;">
                           %(link_prefix)s
                           <img border="0" src="%(image_path)s" %(image_width_tag)s %(image_height_tag)s alt="Thumbnail" />
                           %(link_suffix)s
                       </div>
                   </div>''' % \
                   {'image_path':image_path,
                    'image_width_tag': image_width_tag,
                    'css_film_effect_div_width_style': css_film_effect_div_width_style,
                    'image_height_tag': image_height_tag,
                    'link_prefix': link_prefix,
                    'link_suffix': link_suffix
                    }

    return ''' <div style="%(css_film_effect_div_width_style)smargin:4px auto;">
                   %(link_prefix)s
                   <img border="0" src="%(image_path)s" %(image_width_tag)s %(image_height_tag)s alt="Thumbnail" />
                   %(link_suffix)s
               </div>''' % \
                   {'image_path':image_path,
                    'image_width_tag': image_width_tag,
                    'css_film_effect_div_width_style': css_film_effect_div_width_style,
                    'image_height_tag': image_height_tag,
                    'link_prefix': link_prefix,
                    'link_suffix': link_suffix
                    }


def print_images(multimedia, name, max_nb=None, min_nb=None, media_type="thumbnail", width=None,
                 max_width=None, max_heigth=None, magnify='yes', thumb_link_to_detailed_record="no",
                 recid=None, is_restricted_record=False, hide_restricted_record=False):
    """
    Returns thumbnails/posterframes of the video at given width. Also returns the number of images that have been included in the output.
    'media_type' decides if thumbnail or posterframe are to be printed.

    @param multimedia the structure returned by get_media
    @param name the name of the video from which thumbnails are to be taken
    @param max_nb the max number of images to print
    @param min_nb the min number of images to print. If not reached, returns empty string
    @param media_type 'thumbnail' or 'posterframe'
    @param width the width of the image, as int. If not given, original size
    @param max_width the max width of the images
    @param magnify If 'yes', images will be magnified when mouse is over images
    @param thumb_link_to_detailed_record if yes, the thumbnail link to the detailed record page
    @param recid record. Used to link to record if thumb_link_to_detailed_record == 'yes'
    @param is_restricted_record: true if records (and linked media) are restricted
    @param hide_restricted_record: if is_restricted_record == True, print a placeholder image
    """
    if is_restricted_record and hide_restricted_record: #and not get_restricted_collections_for_recid(recid):
        return ('<img src="%s" alt="Restricted" style="max-height: %spx;" />' % (PLACEHOLDER_RESTRICTED_IMG_URL, str(max_heigth)), 1)

    out = []
    i = 0
    percentages = multimedia[media_type][name].keys()
    percentages.sort()
    try: #try to remove the 0% image, in many cases it's black
        if len(percentages) > 1:
            percentages.remove(0)
    except:
        pass
    for percentage in percentages:
        media = multimedia[media_type][name][percentage]
        try:
            max_width = max([image['dimension'][0] for image in media \
                             if image['dimension'][0] is not None])
        except:
            max_width = None
        for image in media:
            if max_nb is not None and i >= int(max_nb):
                # stop as soon as max number of video is reached
                break
            image_path = image.get('path', None)
            image_dimension = image.get('dimension', (None, None))
            if (image_dimension[0] is not None and \
                    image_dimension[0] != max_width) or \
                    (image_dimension[0] is None and max_width > 0):
                # Continue if we know that there is a bigger image available
                continue
            if image_path is not None:
                (image_width, image_height) = resize_dimension(image_dimension, width, max_width, max_heigth)

                # width
                image_width_tag = ''
                if image_width is not None:
                    image_width_tag = 'width="%spx"' % image_width
                else:
                    image_width_tag = 'style="max-width:%spx"' % width
                # height
                image_height_tag = ''
                if image_height is not None:
                    image_height_tag = 'height="%spx"' % image_height

                # Enable or not magnification of thumbnail
                magnified_image = ''
                if magnify.lower() == 'yes':
                    magnified_image = '<span><img style="z-index:5;" src="%(image_path)s" alt="Original size thumbnail"/></span>' % \
                               {'image_path':image_path}
                # Link image to detailed record page when specified
                link_prefix = ''
                link_suffix = ''
                if thumb_link_to_detailed_record.lower() == 'yes' and recid is not None:
                    link_prefix = '<a href="%s/record/%s">' % (CFG_SITE_URL, recid)
                    link_suffix = '</a>'
                out.append('''<div class="thumbMosaic">
                                  %(link_prefix)s
                                  <img border="0" src="%(image_path)s" %(image_width_tag)s %(image_height_tag)s alt="Thumbnail" class="thumb"/>
                                  %(link_suffix)s
                                  %(magnified_image)s
                              </div>''' % \
                           {'image_path':image_path,
                            'image_width_tag': image_width_tag,
                            'image_height_tag': image_height_tag,
                            'magnified_image': magnified_image,
                            'link_prefix': link_prefix,
                            'link_suffix': link_suffix})
                i += 1


    if i and (min_nb is None or i >= int(min_nb)):
        return ('''<style type="text/css">
                       div.thumbMosaic {display:inline;}
                       div.thumbMosaic span{display:none;}
                       div.thumbMosaic:hover span{display:block;position:absolute;z-index:2;}
                     </style>''' + \
        ' '.join(out), i)

    return ('', 0)


def guess_talk_name(bfo, talk_id):
    """Tries to retrive the talk name base of the talk_id"""
    notes = bfo.fields('518')
    connected_notes = [(note.get('d', ''), note.get('h', '')) for note in notes if note.get('g', '') == talk_id]
    if not connected_notes:
        return ''
    note_txt = [item for item in connected_notes[0] if item]
    return ', '.join(note_txt)


def get_part_label(bfo, conf_id, index, record_is_conf_p):
    """Generate the lable for each part: "Part i"
       Exceptions:
        * Conferences : Display conference date instead of "Part i".
          - Look for 8564_u and try to match conference id. Then print 8564_y:
          - 8564_ $$uhttp://indico.cern.ch/conferenceDisplay.py?confId=24743$$yTalk 28 Jan 2008
    """
    if record_is_conf_p:
        try:
            label = [field['y'] for field in bfo.fields('8564_') if field.get('u', '').endswith('=%s' % conf_id) and field.get('y', '')][0]
            if label == 'Talk': # in some cases for WebLecture, add more info
                label += ' %s' % guess_talk_name(bfo, conf_id)
            return label
        except:
            pass
    return 'Part %s' % (index + 1)


##BibAlbum##
def get_recid_for_toc(bfo):
    """Retrieves the recid of the TOC (if any) associated with the record"""
    _toc_recid = -1

    try:
        _toc_relationship = get_toc_relationship(bfo)[0]
    except IndexError:
        return _toc_recid

    report_number_toc = _toc_relationship.get('r')
    if report_number_toc:
        toc_recid = perform_request_search(p='"%s"' %report_number_toc, f=REPORT_NUMBER_MARC, ap=0)
        if len(toc_recid) == 1: # if one and only one
            _toc_recid = toc_recid[0]
        else:
            toc_id = _toc_relationship.get('o')
            toc_recid = search_pattern(p='970__a:"%s"' %toc_id)
            if len(toc_recid) == 1:
                _toc_recid = toc_recid[0]

    return _toc_recid

def is_record_toc(bfo):
    """Returns True if the record is a TOC record"""
    if 'project' in bfo.field('970__a').lower(): #and bfo.field('774__r'):
        return True
    return False

def get_assets_for_toc(bfo):
    """Returns the list of assets recids"""
    result = []
    repnum_assets = bfo.fields(REPORT_NUMBER_ASSET_IN_TOC_MARC)
    repnum_assets.sort()
    if record_public_p(bfo.recID):
        #TOC is public, show only public assets
        search_fnc = perform_request_search
    else:
        #TOC is restricted, show all assets
        search_fnc = search_pattern
    for repnum_asset in repnum_assets:
        result.extend(search_fnc(p='"%s"' %repnum_asset, f=REPORT_NUMBER_MARC, ap=0))
    return result

def get_reportnumber_for_toc(bfo):
    """Retrieves the report number of the TOC"""
    try:
        _get_toc = get_toc_relationship(bfo)[0]
    except IndexError:
        _get_toc = dict()
    return _get_toc.get('r')
##BibAlbum##

##Utils##
def encode_flashvar(value):
    "Encode these 3 chars (?, &, =), as requested by the player"
    if not value:
        return ''
    return value.replace('?', '%3F').replace('=', '%3D').replace('&', '%26')
##Utils##
