# -*- coding: utf-8 -*-
#
# $Id$
#
# This file is part of Invenio.
# Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007 CERN.
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
"""BibFormat element - Prints HTML picture and links to resources
"""
__revision__ = "$Id$"

import os
import cgi
import re
from urllib import urlopen, quote
from invenio.config import CFG_SITE_URL, CFG_SITE_SECURE_URL, CFG_ICON_CREATION_FORMAT_MAPPINGS
from invenio.bibdocfile import BibRecDocs
from invenio.urlutils import create_html_link, url_safe_escape
from invenio.bibdocfile_config import CFG_BIBDOCFILE_DEFAULT_ICON_SUBFORMAT
from invenio.bibformat_elements import bfe_copyright
from invenio.webstat import get_url_customevent
from operator import itemgetter
from invenio.search_engine import get_all_restricted_recids, get_record
from invenio.media_utils import alphanum, get_photolab_image_caption
from invenio.bibknowledge import get_kb_mapping

# Mapping from eg A4 -> "Large"
version_mapping = {'a4': 'Large',
                   'a5': 'Medium',
                   'icon': 'Small'}

MAX_LEN_CAPTION = 50

def format_element(bfo, magnify='yes', check_existence='yes', source="auto", display_name="no", display_reference="yes", display_description="yes", display_comment="yes", display_tirage="yes", submission_doctype=""):
    """
    Prints html image and link to photo resources, if 8567 exists print only 8567
    otherwise if exists 8564.
    @param magnify If 'yes', images will be magnified when mouse is over images
    @param check_existence if 'yes' check that file is reachable
    @param source where to look for photos. Possible values are 'mediaarchive', 'doc', 'bibdoc' or 'auto' (check everywhere)
    """
    out = ""

    rec_is_restricted = bfo.recID in get_all_restricted_recids()
    # Hack to know about copyright while we do not have this stored in
    # the metatada.
    copyright_prefix = ''
    report_number = bfo.field('037__a')
    author = bfo.field('100__a').lower()
    if report_number.startswith('ATL') or \
           'claudia marcelloni' in author or \
           'atlas' in author or \
           'joao pequenao' in author or \
           'tiina wickstroem' in author or \
           'nikolai topilin' in author:
        copyright_prefix = '<br/>The ATLAS Experiment '

    cond_of_use = '''<a href="http://copyright.cern.ch/">Conditions of Use</a> '''
    if bfo.field('540__u') or bfo.field('542__u') or bfo.field('542__d') != 'CERN' or bfo.field('540__a'):
        cond_of_use = ''

    # Check if image is under creative commons license
    creative_commons = False
    if bfo.field('540__a').startswith('CC-BY'):
        creative_commons = True
        out += '<div about="%s" rev="license">' % get_kb_mapping(kb_name='LICENSE2URL', key=bfo.field('540__a'))['value']
    multimedia = {}
    if source in ['auto', 'mediaarchive']:
        multimedia = get_media(bfo, check_existence=(check_existence.lower() == 'yes'))
        # Also append master information to the multimedia structure
        masters = get_media(bfo, path_code='d', internal_note_code='x', check_existence=(check_existence.lower() == 'yes'))
        for (tirage, info) in masters.iteritems():
            if multimedia.has_key(tirage):
                multimedia[tirage]['master'] = info['master']

    if multimedia != {} and source in ['auto', 'mediaarchive']:
        out += '''<center><small><strong>%s%s</strong></small></center><br />''' % (cond_of_use, bfe_copyright.format_element(bfo) or '&copy; CERN')
        out += '''<center><small><a href="%(CFG_SITE_URL)s/help/high-res-multimedia?ln=%(ln)s">%(label)s</a></small></center>''' % \
               {'CFG_SITE_URL': CFG_SITE_URL,
                'ln': bfo.lang,
                'label': bfo.lang == "fr" and 'Besoin d\'aide pour acc&eacute;der aux photos en haute r&eacute;solution?' or \
                'Need help to download high-resolutions?'}
        mediaarchive_pictures = print_images(multimedia=multimedia, magnify=magnify,
                                reference=bfo.field('037__a'), bfo=bfo)
        if len(multimedia) > 1 and not rec_is_restricted: # we have at least 2 photos
            out += generate_view_button(bfo, report_number, mediaarchive_pictures)
        else:
            out += mediaarchive_pictures
        out += '''<script type="text/javascript">
        window.onload = function() {
            if (location.hash != ''){
                    var pic = document.getElementById('thumb'+location.hash.substring(1));
                    if (pic != null){
                        hs.expand(pic)
                    }
                }
        }
                </script>'''
    elif not source in ['mediaarchive']:
        out += '''<center><small><strong>%s%s</strong></small></center><br />''' % (cond_of_use, bfe_copyright.format_element(bfo) or '&copy; CERN')

        bibdoc_pictures = get_bibdoc_pictures(bfo, display_name, display_reference,
                                              display_description, display_comment,
                                              display_tirage, submission_doctype)
        if bibdoc_pictures and source in ['auto', 'bibdoc']:
            if bibdoc_pictures.count('<img ') > 1 and not rec_is_restricted:# we have at least 1 photo
                out += generate_view_button(bfo, report_number, bibdoc_pictures)
            else:
                out += bibdoc_pictures
        elif source in ['auto', 'doc']:
            # Use picture from doc
            out += get_doc_pictures(bfo)

    if creative_commons:
        out += '</div>'
    return out

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0

def generate_view_button(bfo, report_number, content_as_list):

    #slideshow content
    content_as_slideshow = """<iframe width="550" height="420" scrolling="no" frameborder="0" src="%s" allowfullscreen></iframe>""" % \
                                    generate_embedding_url_for_slideshow(bfo, report_number)

    out = '''<script>
           $(document).ready(function() {
             $("#photodisplaycontrol").click(function(){
                 if ($(this).text() == "View as Slideshow"){
                     $(this).text("View as list");
                     $("#photodisplaycontent1").hide();
                     $("#photodisplaycontent2").show();
                     $("#slideshowcontent").html('%s');
                 }
                 else {
                     $(this).text("View as Slideshow");
                     $("#photodisplaycontent2").hide();
                     $("#photodisplaycontent1").show();
                     $("#slideshowcontent").html('');
                }
             });
            });
             </script>''' % content_as_slideshow
    out += '''<style>
             .photocontroler {
                  background-color: #E6E6FA;
                  margin-left: 10px;
                  padding: 3px;
                  width: 115px;
                  text-align: center;
                  border-radius: 2px;
                  border: 1px solid #C6C6C6;
                  white-space: nowrap;
              }
              #photodisplaycontrol {
                  text-decoration: none;
                  font-size: small;
                  color: #555444;
                  text-align: center;
              }
             </style>'''
    out += '''<div class="photocontroler"><a href="#" id="photodisplaycontrol">View as Slideshow</a></div>'''
    out += '''<div id="photodisplaycontent1">%s</div>''' %content_as_list
    out += '''<div id="photodisplaycontent2" style="display:none; text-align:center; padding:15px;">
              <span id="slideshowcontent"></span>
              <div style="clear:both;"></div>
              %s
              </div>''' % get_slideshow_box(bfo)
    return out

def generate_embedding_url_for_slideshow(bfo, report_number):
    keywords = bfo.fields('6531_a')
    #check that the keyword bulletin exists, we want a different format for the slideshow
    if 'bulletin' in [kw.lower() for kw in keywords]:
        format = 'espp'
    else:
        format = 'sspp'
    return "%(site_url)s/images/%(report_number)s/export?format=%(format)s&ln=%(ln)s&captions=%(captions)s" % {
        'site_url': CFG_SITE_URL,
        'report_number': report_number,
        'format': format,
        'ln': 'en',
        'captions': 'true'}


def get_slideshow_box(bfo):

    report_numbers = bfo.fields('037__a')
    try:
        report_number = report_numbers[0]
    except IndexError:
        return ''
    code = '<iframe width="480" height="360" scrolling="no" frameborder="0" src="%s" allowfullscreen></iframe>' \
            % generate_embedding_url_for_slideshow(bfo, report_number)
    code_box_id = 'embedSlideshow'
    out = '''<style>
                a.embedLinkSS {
                    background-color: #fafafa;
                    color: #222;
                    border: #ddd solid 1px;
                    padding: 4px;
                    font-size: x-small;
                    font-weight: 700;
                }
                table.embedLinkSS {
                    background-color:#eee;
                    border:#ddd solid 1px;
                    margin:0 auto;
                }
             </style>'''
    out += '<div style="margin-top:10px;">'
    out += '''<a href="#" class="embedLinkSS" onclick="$(this).hide();$('#%s').show();return false;">Embed record as a slideshow</a>''' % code_box_id
    out += '''<table class="embedLinkSS" style="display:none" id="%(code_box_id)s">
                 <tr><th colspan="4" style="text-align:center;font-size:small">Copy-paste this code into your page:</th></tr>
                 <tr><td><textarea readonly="readonly" rows="3" cols="50">%(code)s</textarea></td></tr></table>''' % \
                 {'code': code,
                  'code_box_id': code_box_id
                 }
    out += '</div>'
    return out


set_link_content_pattern = re.compile(r'<!--START_SETLINK-->.*?<!--END_SETLINK-->', \
                                      re.IGNORECASE | re.DOTALL)
def get_doc_pictures(bfo, tag="8564_"):
    """Return html for links in 8564"""
    resources = bfo.fields(tag)
    out = ""
    for resource in resources:
        if resource.has_key('q') and \
               ('cmsdoc.cern.ch' in resource['q'] or
                'cms.cern.ch' in resource['q'] or
                '/setlink?' in resource['q'] or
                'documents.cern.ch' in resource['q'] or
                'doc.cern.ch' in resource['q'] or
                'preprints.cern.ch' in resource['q']):
            f = urlopen(resource['q'])
            set_link_page = f.read()
            match_obj = set_link_content_pattern.search(set_link_page)
            if match_obj is not None:
                out += match_obj.group()

    return out


def get_bibdoc_pictures_struct(bfo, submission_doctype):
    """
    Returns an associative array of the record data and images
    """
    bibarchive = BibRecDocs(bfo.recID)
    bibarchive_with_deleted = BibRecDocs(bfo.recID, deleted_too=True)
    report_number = bfo.field('037__a')

    if 'EVENTDISPLAY' in report_number and len(bibarchive.list_bibdocs()) > 1:
        #display only main file
        display_only_main = True
    else:
        display_only_main = False

    # First create an ordered list of doc numbers. This will be used
    # to assign a "tirage" to all photos, even if deleted.  (if
    # someone refers to a specific photo, we should keep its number
    # even if photos are reordered or deleted)
    doc_numbers = [(bibdoc.get_id(), bibarchive_with_deleted.get_docname(bibdoc.get_id()), bibdoc) for bibdoc in bibarchive_with_deleted.list_bibdocs() if (not display_only_main) or (bibdoc.get_type().lower() == 'main' and display_only_main)]
    #doc_numbers = [(bibdoc.get_id(), bibdoc.get_docname(), bibdoc) for bibdoc in bibarchive_with_deleted.list_bibdocs()]
    doc_numbers.sort()

    number_of_photos_to_display = len([x for x in doc_numbers if not x[2].deleted_p()])

    bibdocs = bibarchive.list_bibdocs()
    if len(bibdocs) == 0:
        return ""

    # Compile a regular expression that can match the "default" icon,
    # and not larger version.
    CFG_BIBDOCFILE_ICON_SUBFORMAT_RE_DEFAULT = re.compile(CFG_BIBDOCFILE_DEFAULT_ICON_SUBFORMAT + '\Z')

    bibdoc_pictures = []

    for (docid, docname, bibdoc) in doc_numbers:
        if bibdoc.deleted_p():
            continue

        if True in [docfile.hidden_p() for docfile in bibdoc.list_latest_files()]:
            continue

        if bibdoc.get_type().lower() != 'main' and display_only_main:
            continue

        if bibdoc.format_already_exists_p('.swf') and bibdoc.get_type() == 'panorama':
            # We do not want to consider Flash panoramas here
            continue

        found_icons = []
        found_url = ''
        for docfile in bibdoc.list_latest_files():
            if docfile.is_icon() and not docfile.hidden_p():
                found_icons.append((docfile.get_size(), docfile.get_url()))
        found_icons.sort()

        icon = None
        icon_url = None
        if found_icons:
            icon_url = found_icons[0][1]
        if not icon_url:
            icon_url = CFG_SITE_URL + '/img/file-icon-image-96x128.png'

        # Let's try to find a better preview. Let's say more or less middle size?
        try:
            preview_url = found_icons[len(found_icons)/2][1]
        except:
            # Never mind
            preview_url = icon_url

        if number_of_photos_to_display == 1:
            icon_url = preview_url

        photo_files = []
        name = bibarchive_with_deleted.get_docname(docid)
        description = "" # Limit to one description per bibdoc
        comment = "" # Limit to one comment per bibdoc
        bibdoc_number = doc_numbers.index((docid, docname, bibdoc)) + 1
        download_links = []
        orig_formats = []
        for bibdoc_file in bibdoc.list_latest_files():
            if bibdoc_file.hidden_p(): # ignore hidden formats
                continue
            format = bibdoc_file.get_format().lstrip('.').upper()
            url = bibdoc_file.get_url()
            photo_files.append((format, url))
            if not description and bibdoc_file.get_description():
                description = bibdoc_file.get_description()
            if not comment and bibdoc_file.get_comment():
                comment = bibdoc_file.get_comment()
            if not bibdoc_file.get_subformat():
                orig_formats.append(format)
            download_links.append({'url': url, 'format': format})

        #some photos from the past have better quality jpg format than other formats
        if 'JPG' in orig_formats:
            orig_formats.remove('JPG')
            orig_formats = ['JPG'] + orig_formats
        format_label = {'Large': ';ICON-1440', 'Medium': ';ICON-640', 'Small': ';ICON-180', 'Original': ''}
        format_order = ['Small', 'Medium', 'Large', 'Original']
        # sort download links based on format_order
        for orig_format in orig_formats:
            format_for_icon =  CFG_ICON_CREATION_FORMAT_MAPPINGS.get(orig_format.lower(), [orig_format])[0]
            temp_download_links = [{'url': li['url'], 'format': format} for format in format_order for li in download_links if li['format'].upper() == "%s%s" %(format_for_icon.upper(), format_label[format])]
            if len(temp_download_links) > 2: #we have at least the original, and 2 subformats
                other_originals = [li for li in download_links if li['format'].upper() in orig_formats and li['format'].upper() != format_for_icon]
                download_links = temp_download_links
                #add the other originals to the list
                download_links.extend(other_originals)

                if is_user_at_cern:
                    preview_url = [li['url'] for li in download_links if li['format'] == 'Large'][0]
                else:
                    preview_url = [li['url'] for li in download_links if li['format'] == 'Medium'][0]
                if number_of_photos_to_display == 1:
                    icon_url = [li['url'] for li in download_links if li['format'] == 'Medium'][0]
                else:
                    icon_url = [li['url'] for li in download_links if li['format'] == 'Small'][0]
                break
        bibdoc_pictures.append({'bibdoc_number': bibdoc_number,
                                'icon_url': icon_url,
                                'preview_url': preview_url,
                                'report_number': report_number,
                                'name': name,
                                'bibdoc_number': bibdoc_number,
                                'download_links': download_links,
                                'description': description,
                                'comment': comment,
                                'submit_link': submission_doctype and (create_html_link(CFG_SITE_URL + '/submit/direct', urlargd={'DEMOPIC_RN': report_number, 'sub': 'MBI' + submission_doctype}, link_label='<img src="%s/img/iconpen.gif">' % CFG_SITE_URL)) or ''})
                                #'submit_link': ''})

    #sort this structure based on the name of each picture (closest to chronological order)
    bibdoc_pictures = sorted(bibdoc_pictures, key=itemgetter('name'), cmp=alphanum)

    return bibdoc_pictures


def get_bibdoc_pictures(bfo, display_name, display_reference,
                        display_description, display_comment,
                        display_tirage, submission_doctype):
    rec_data = get_bibdoc_pictures_struct(bfo, submission_doctype)
    out = []
    separator = ''

    if len(rec_data) == 1:#if we have only 1 image, use different style
        image_style_1 = "text-align:center;margin:10px"
        image_style_2 = "text-align:center;vertical-align:bottom;"
        image_style_3 = "max-height:490px; max-width:640px;"
    else:
        image_style_1 = "text-align:center;float:left;margin:10px"
        image_style_2 = "height:210px;width:180px;float:left;text-align:center;vertical-align:bottom;"
        image_style_3 = "max-height:140px; max-width:180px;"

    for bibdoc_picture_struct in rec_data:
        photo_files = []
        for picture_details in bibdoc_picture_struct['download_links']:
            photo_files.append((picture_details['format'], picture_details['url']))

        download_links = ', '.join([create_html_link(url, urlargd={}, linkattrd={'data-size':format}, link_label=format) for (format, url) in photo_files])

        download_links_short = ', '.join([create_html_link(url, urlargd={}, linkattrd={'style':'color:#888;font-size:x-small', 'data-size':format}, link_label=format) for (format, url) in photo_files])
        if display_description.lower() == 'yes' and bibdoc_picture_struct['description'] and display_comment.lower() == 'yes' and bibdoc_picture_struct['comment']:
            separator = ' // '
        else:
            separator = ''
        description_and_comment_short = ((display_description.lower() == 'yes' and bibdoc_picture_struct['description']) + separator + \
                                         (display_comment.lower() == 'yes' and bibdoc_picture_struct['comment'] or ''))
        if len(description_and_comment_short) > MAX_LEN_CAPTION:
            description_and_comment_short = description_and_comment_short[:MAX_LEN_CAPTION] + '''<a style="color:#888;" href="#" onclick="document.getElementById('thumb%s').onclick();return false">[...]</a>''' % bibdoc_picture_struct['bibdoc_number']
        out.append('''
<div style="%(style1)s">
<div style="%(style2)s">
<a id="thumb%(index)s" href="%(image_url)s" class="highslide" onclick="return hs.expand(this)">
	<img src="%(thumb_url)s" style="%(style3)s" alt="" title="%(name)s%(reference)s%(tirage)s" />
</a>
<div class="highslide-caption">
    <b>%(name)s%(reference)s%(tirage)s</b> &nbsp;-&nbsp;  %(download_links_string)s <br/>%(description)s%(separator)s%(comment)s
</div>
<br/>

<div class="image-download-links" style="color:#888;font-size:x-small;display:block;clear:both">%(name)s%(reference)s%(tirage)s <br/>%(download_links_string_short)s<br/><span style="color: #444;font-size:small">%(description_and_comment_short)s</span></div>%(edit_link)s</div>
</div>''' % {'style1': image_style_1,
             'style2': image_style_2,
             'style3': image_style_3,
             'index': bibdoc_picture_struct['bibdoc_number'],
             'thumb_url': url_safe_escape(bibdoc_picture_struct['icon_url']),
             'image_url': url_safe_escape(bibdoc_picture_struct['preview_url']),
             'reference': display_reference.lower() == 'yes' and bibdoc_picture_struct['report_number'] or '',
             'name': display_name.lower() == 'yes' and bibdoc_picture_struct['name'] or '',
             'tirage': display_tirage == 'yes' and '-' + str(bibdoc_picture_struct['bibdoc_number']) or '',
             'download_links_string': download_links,
             'download_links_string_short': download_links_short,
             'description': display_description.lower() == 'yes' and bibdoc_picture_struct['description'] or '',
             'comment': display_comment.lower() == 'yes' and bibdoc_picture_struct['comment'] or '',
             'description_and_comment_short': description_and_comment_short,
             'separator': separator,
             'edit_link': bibdoc_picture_struct['submit_link']})

    show_hide_images_js = '''
        <script type="text/javascript">
        function toggle_images_visibility(){
            var more = document.getElementById('more');
            var link = document.getElementById('link');
            more.innerHTML = more.innerHTML.substring(4, more.innerHTML.length - 3);
            link.style.display='none';
            hs.updateAnchors();
        }

        </script>
        '''#%{'show_less': "Hide",
           #  'show_more': "Show all %i images" % len(rec_data)}

    DISPLAY_MAX_RECORDS = 20
    return ''.join(out[:DISPLAY_MAX_RECORDS])+ \
           (len(out) > DISPLAY_MAX_RECORDS and \
            ('<div id="more"><!--' + ''.join(out[DISPLAY_MAX_RECORDS:]) + '--></div>' + \
        '<a id="link" href="" onclick="toggle_images_visibility();return false;" style="float:left;color:rgb(204,0,0);">%s</a>' % "Show all %i images" % len(rec_data))
            or '') + \
           '''<script type="text/javascript">
        window.onload = function() {
            if (location.hash != ''){
                    var pic = document.getElementById('thumb'+location.hash.substring(1));
                    if (pic != null){
                        hs.expand(pic)
                    }
                }
        }
                </script>''' + \
           show_hide_images_js

def get_media(bfo, tag="8567_", tirage_code='8', path_code='u', internal_note_code='y', label_code='x',
              check_existence=True):
    """
    Returns a structure with the available media and their information

    Data is retrieved from field given by tag, path_code and internal_note.
    For example the path is retrieved from tag+path_code: 8567_u

    The returned structure is a dictionary whose keys are tirages and values are dictionnaries
    whose keys are mediatype such as 'icon', 'a4', 'a5' and values are dictionnaries containing
    all further information
    e.g:
    {'01':
          {'a4':
                {'path':'http://mediaarchive.cern.ch/MediaArchive/Photo/Public/....',
                'label':'jpgA4'},
          {'a5':{...,
                }
          {'icon':{...,
                  }

     '02':{'a4':
                {'path':'http://mediaarchive.cern.ch/MediaArchive/Photo/Public/....',
                'label':'jpgA4'},
          {'a5':{...,
                }
     }

    """
    out = {}
    files = bfo.fields(tag)
    for media in files:
        path = media.get(path_code, None)
        if path is None:
            # Do not process if path does not exist
            continue
        else:
            path = path.replace('http://mediaarchive.cern.ch', 'https://mediastream.cern.ch')
        tirage = media.get(tirage_code, '')
        if not out.has_key(tirage):
            out[tirage] = {}
        internal_note = media.get(internal_note_code, '')
        label = media.get(label_code, '')
        media_type = get_media_type(internal_note)
        info = {}
        if not check_existence or file_exists(path):
            info['path'] = path
        info['filename'] = get_filename(path)
        info['file_type'] = get_format(path)
        info['label'] = label
        out[tirage][media_type] = info
    return out

def get_format(path):
    """
    Returns the file extension of the media
    Returns None if not identified
    """
    comp = path.split('.')
    if len(comp) > 1:
        return comp[-1]
    else:
        return None

def get_filename(path):
    """
    Returns the filename of the movie
    Returns None if not identified
    """
    comp = path.split('/')
    if len(comp) > 0:
        return comp[-1]
    else:
        return None

def get_media_type(internal_note):
    """
    Returns 'icon' if the file is a icon,
    'a4' if the file is an a4,
    'a5' if the file is an a5
    Returns None if not identified
    """
    if 'icon' in internal_note.lower():
        return 'icon'
    elif 'a4' in internal_note.lower():
        return 'a4'
    elif 'a5' in internal_note.lower():
        return 'a5'
    elif 'master' in internal_note.lower():
        return 'master'
    else:
        return None

def print_master_path_link():
    return '''

    '''

def print_images(multimedia, bfo, media_type="icon", on_magnify_type="a5", on_click_type="a4", \
                 max_nb=None, magnify='yes', reference=''):
    """
    Returns icon/a5/a4 of the photo
    'media_type' decides if icon/a4/a5 are to be printed.

    if media type is not found, then another media type is used

    @param multimedia the structure returned by get_media
    @param max_nb the max number of tiages to print
    @param media_type 'icon', 'a4', 'a5'
    @param on_magnify_type: type of image to display when mouse over
    @param on_click_type: type of image to display when mouse click
    @param magnify If 'yes', images will be magnified when mouse is over images
    @param reference the reference number of the picture
    """
    out = []

    i = 0
    tirages = multimedia.keys()
    try:
        tirages_to_sort = dict([(int(tirage), tirage) for tirage in tirages])
        tirages_to_sort_keys = tirages_to_sort.keys()
        tirages_to_sort_keys.sort()
        tirages = [tirages_to_sort[tirages_to_sort_key] for tirages_to_sort_key in tirages_to_sort_keys]
    except:
        tirages.sort()

    recstruct = get_record(bfo.recID)
    for tirage in tirages:
        if max_nb is not None and i >= int(max_nb):
            # stop as soon as max number of video is reached
            break
        if not multimedia[tirage].has_key(media_type):
            continue

        image = multimedia[tirage][media_type]
        image_path = image.get('path', None)
        master_path = multimedia[tirage].get('master', {}).get('path', '')
        master_path = master_path.replace('\\\\cern.ch\\dfs\\Services\\MediaArchive',
                                          'https://mediastream.cern.ch/MediaArchive')
        master_path = master_path.replace('\\', '/')
        download_links = []
        for version, url in [(version, image.get("path", "")) \
                             for version, image in multimedia[tirage].iteritems() \
                             if image.get("path", "") != '' and version != 'master']:
            version_label = version_mapping.get(version, version)
            custom_url = get_url_customevent(url, "media_download",
                            ["%s %s" % (reference,tirage),"photo",version_label,"WEBSTAT_IP"])
            download_links.append((custom_url,version_label))

        download_links.sort()
        download_links.reverse()
        download_links.append(('''%(CFG_SITE_SECURE_URL)s/tools/mediaarchive.py/copyright_notice?recid=%(recid)s&master_path=%(encoded_master_path)s&ln=%(ln)s&reference=%(reference)s&tirage=%(tirage)s''' % \
                                      {'master_path': master_path,
                                       'CFG_SITE_SECURE_URL': CFG_SITE_SECURE_URL,
                                       'recid':bfo.recID,
                                       'encoded_master_path':cgi.escape(master_path),
                                       'ln':bfo.lang,
                                       'tirage':tirage,
                                       'reference':reference},
                               '''<img src="/img/download-icon-gray-12x12.jpg" alt="Download" border="0"/>High-res'''))
        download_links_string = ''
        if len(download_links) > 0:
            download_links_string = '<b>Download</b> ' + \
                                    ', '.join(['<a style="%s" href="%s">%s</a>' % ("",url,label) for url,label in download_links])

        # Grab image to display in 'detailed'
        # Possibly take A4. then A5, and finally icon when at CERN
        if is_user_at_cern(bfo):
            image_url = multimedia[tirage].get('a4', multimedia[tirage].get('a5', multimedia[tirage].get('icon', None)))
        else:
            # Outside CERN: be reasonable and use A5 first
            image_url = multimedia[tirage].get('a5', multimedia[tirage].get('icon', multimedia[tirage].get('a4', None)))
        if image_url != None:
            image_url = image_url.get("path", "")
        else:
            image_url = ''

        #get description
        full_photo_description = get_photolab_image_caption(recstruct, tirage)
        photo_description = full_photo_description[:]
        if len(photo_description) > MAX_LEN_CAPTION:
            photo_description = photo_description[:MAX_LEN_CAPTION] + \
             '''<a style="color:#888;" href="#" onclick="document.getElementById('thumb%s').onclick();return false">[...]</a>''' % tirage

        #different style if only 1 photo
        if len(tirages) == 1:
            photo_style_1 = "text-align:center;margin:10px"
            photo_style_2 = "text-align:center;vertical-align:bottom;"
            try:
                image_path = multimedia[tirage].get('a5', multimedia[tirage].get('icon', None)).get("path", "")
            except:
                pass
        else:
            photo_style_1 = "text-align:center;float:left;margin:10px"
            photo_style_2 = "height:210px;width:180px;float:left;text-align:center;vertical-align:bottom;"
        out.append('''
<!--
    4) This is how you mark up the thumbnail image with an anchor tag around it.
    The anchor's href attribute defines the URL of the full-size image.
-->
<div style="%(style1)s">
<div style="%(style2)s">
<a id="thumb%(index)s" href="%(image_url)s" class="highslide" onclick="return hs.expand(this)">
	<img src="%(thumb_url)s" alt="Thumbnail %(reference)s tirage %(tirage)s"
		title="%(reference)s-%(tirage)s" />
</a>
<div class="highslide-caption">
    <b>%(reference)s-%(tirage)s</b> &nbsp;-&nbsp; %(download_links_string)s <br/> %(full_description)s
</div>
<br/>
<div style="color:#888;font-size:x-small;display:block;clear:both">%(reference)s-%(tirage)s <br/>%(download_links_string_short)s <br/> <span style="color: #444;font-size:small;word-wrap:break-word;">%(description)s</span></div></div>
</div>
''' % {'style1': photo_style_1,
       'style2': photo_style_2,
       'index': tirage,
       'thumb_url': image_path,
       'image_url': image_url,
       'reference': reference,
       'tirage': tirage,
       'description': photo_description,
       'full_description': full_photo_description,
       'download_links_string': download_links_string,
       'download_links_string_short': (' '.join(['<a style="%s" href="%s">%s</a>' % ("color:#888;font-size:x-small",url,label) \
                                               for url,label in download_links])) })

        i += 1


    return ' '.join(out)

def is_user_at_cern(bfo):
    client_ip = bfo.user_info['remote_ip']
    if client_ip.startswith("137.138") or \
          client_ip.startswith("128.141") or \
          client_ip.startswith("128.142") or \
          client_ip.startswith("192.91") or \
          client_ip.startswith("194.12") or \
          client_ip.startswith("192.16"):
        return True
    return False

def file_exists(url):
    """
    Returns True if resource could be found at url. Else returns false
    """
    pipe_input, pipe_output, pipe_error = os.popen3('/usr/bin/wget --spider -S -t 1 -T 3 ' +\
                                                    url)
    pipe_input.close()
    res = pipe_error.read()
    pipe_output.close()
    if not 'ERROR 404' in res:
        return True
    else:
        return False
