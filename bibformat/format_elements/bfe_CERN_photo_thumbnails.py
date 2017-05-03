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

"""
BibFormat element - Prints brief HTML picture and links to resources.
"""

__revision__ = "$Id$"

import os
from operator import itemgetter
from invenio.config import weburl
from invenio.bibdocfile import BibRecDocs
from invenio.mediaarchive_utils import _perform_request_add_slave_url
from invenio.media_utils import alphanum
from invenio.bibformat_engine import BibFormatObject
from invenio.urlutils import url_safe_escape

def format_element(
    bfo,
    limit,
    min_photos="",
    print_links="yes",
    style="",
    separator="",
    focus_on_click='no',
    open_pdf="no",
    use_cover_photos_only="no"
):
    """
    Prints html photo thumbnails.
    @param limit the max number of thumbnails to display
    @param print_links if 'yes', each image is linked to its detailed record
    @param min_photos the minimum number of photos which must be available to print the thumbnails
    @param style the css style applied to the image (Eg: 'max-width:40px')
    @param separator printed between each image
    @param focus_on_click if 'yes', add #tirage to printed link so that detailed format can focus on clicked image
    @param user_cover_photos_only if 'yes', only look for album photos that are indicated as "Cover" photos
    """

    out = ""

    album = bfo.field('999__a') == "ALBUM"

    if album:
        if use_cover_photos_only == "yes":
            # Get all the photos in this album
            photos_in_album = bfo.fields('774')
            # Only keep the photos that are indicated as "Cover" photos
            cover_photos_in_album = filter(
                lambda photo: "Cover" in photo.get("n", ""),
                photos_in_album
            )
            # If photo has been indicated as "Cover" photo, keep all of them
            if not cover_photos_in_album:
                cover_photos_in_album = photos_in_album
            # Get the record_id of the first "Cover" photo found
            try:
                record_id = cover_photos_in_album[0].get("r", "")
            except IndexError:
                return ''
        else:
            record_id = bfo.field('774__r')
        record = BibFormatObject(record_id)
        resources_1 = record.fields("8567_")
        resources_2 = record.fields("8564_")
        bibarchive = BibRecDocs(record_id)

    else:
        resources_1 = bfo.fields("8567_")
        resources_2 = bfo.fields("8564_")
        bibarchive = BibRecDocs(bfo.recID)

    has_bibdoc_files = bool(len(bibarchive.list_bibdocs()))

    # We order these resources by tirage, subfield 8
    def cmp_tirage(x, y):
        "Compare tirage"
        x_tirage = x.get('8', '1000')
        y_tirage = y.get('8', '1000')
        try:
            x_tirage = int(x_tirage)
            y_tirage = int(y_tirage)
        except:
            pass
        return cmp(x_tirage, y_tirage)
    resources_1.sort(cmp_tirage)

    if limit.isdigit() and int(limit) >= 0:
        max_photos = int(limit)
    else:
        max_photos = len(resources_1) + len(resources_2)

    if min_photos.isdigit() and int(min_photos) >= 0:
        min_photos = int(min_photos)
    else:
        min_photos = 0

    if style:
        style = 'style="' + style +'"'

    num_displayed_photo = 0

    # 8567 resources
    for resource in resources_1:
        if num_displayed_photo < max_photos and \
               resource.get("y", "").lower() == "icon":
            num_displayed_photo += 1
            if print_links.lower() == 'yes':
                out += '<a href="'+weburl+'/record/'+bfo.control_field("001")
                if focus_on_click.lower() == 'yes' and resource.get("8", "") != '':
                    out += '#' + resource.get("8", "")
                out += '">'
            photo_url = resource.get("u", "")
            photo_url = photo_url.replace('http://mediaarchive.cern.ch', 'https://mediastream.cern.ch')
            out += '<img '+style+' src="' + url_safe_escape(photo_url) + \
                   '" alt="" border="0"/>'
            if print_links.lower() == 'yes':
                out += '</a>'
            out += separator

    if out == '':

        if album:

            if use_cover_photos_only == "yes":
                # Get the record_ids of the "Cover" photos in the album using
                # the previously calculated `cover_photos_in_album` list.
                photo_ids = filter(
                    None,
                    map(
                        lambda photo: photo.get("r"),
                        cover_photos_in_album
                    )
                )
            else:
                photo_ids = bfo.fields('774__r')

            for photo_id in photo_ids:
                bibarchive = BibRecDocs(photo_id)
                # get the first bibdoc
                bibdoc_pictures = [bibdoc for bibdoc in bibarchive.list_bibdocs()]
                for doc in bibdoc_pictures:
                    # in this case focus on does not work - different sorting
                    if num_displayed_photo >= max_photos:
                        break
                    icon = doc.get_icon()
                    if not icon:
                        continue
                    num_displayed_photo += 1
                    link_tag = False
                    if print_links.lower() == 'yes':
                        out += '<a href="' + weburl + '/record/' + bfo.control_field("001")
                        #if focus_on_click.lower() == 'yes':
                        #    out += '#%s' %(i+1)
                        out += '">'
                        link_tag = True
                    elif open_pdf.lower() == 'yes':
                        try:
                            resource_pdf_path = resource.get_file('pdf').get_url()
                        except:
                            resource_pdf_path = ''
                        if resource_pdf_path:
                            out += '<a href="%s">' % resource_pdf_path
                            link_tag = True

                    out += '<img '+ style + ' src="%s" alt="" border="0"/>' % url_safe_escape(icon.get_url())
                    if link_tag:
                        out += '</a>'
                    out += separator

        else:
            bibdoc_pictures = [(bibdoc, bibarchive.get_docname(bibdoc.get_id())) for bibdoc in bibarchive.list_bibdocs()]
            bibdoc_pictures = sorted(bibdoc_pictures, key=itemgetter(1), cmp=alphanum)
            for i, (resource, dummy) in enumerate(bibdoc_pictures):
                # in this case focus on does not work - different sorting
                if num_displayed_photo >= max_photos:
                    break
                icon = resource.get_icon()
                if not icon:
                    continue
                if icon.hidden_p():
                    continue
                num_displayed_photo += 1
                link_tag = False
                if print_links.lower() == 'yes':
                    out += '<a href="' + weburl + '/record/' + bfo.control_field("001")
                    #if focus_on_click.lower() == 'yes':
                    #    out += '#%s' %(i+1)
                    out += '">'
                    link_tag = True
                elif open_pdf.lower() == 'yes':
                    try:
                        resource_pdf_path = resource.get_file('pdf').get_url()
                    except:
                        resource_pdf_path = ''
                    if resource_pdf_path:
                        out += '<a href="%s">' % resource_pdf_path
                        link_tag = True

                out += '<img '+ style + ' src="%s" alt="" border="0"/>' % url_safe_escape(icon.get_url())
                if link_tag:
                    out += '</a>'
                out += separator

    # 8564 resources
    if out == '':
        for resource in resources_2:
            if num_displayed_photo < max_photos and \
                   resource.get("x", "").lower() == "icon" and resource.get("u", "") != "" and \
                   (not resource.get("u", '').split("/")[2] in ['documents.cern.ch', 'doc.cern.ch', 'preprints.cern.ch'] or \
                    (len(resources_1) == 0 and not has_bibdoc_files)) and open_pdf.lower() == 'no':
                num_displayed_photo += 1
                if print_links.lower() == 'yes':
                    out += '<a href="'+weburl+'/record/'+bfo.control_field("001")
                    if focus_on_click.lower() == 'yes' and resource.get("8", "") != '':
                        out += '#' + resource.get("8", "")
                    out += '">'
                out += '<img '+style+' src="' + url_safe_escape(resource.get("u", "")) + \
                       '" alt="" border="0"/>'
                if print_links.lower() == 'yes':
                    out += '</a>'
                out += separator


    # No icon in metadata. Try to read on dfs disk
    # If icon does already exist but is not not in metdata,
    # place it in 'icon_exists_links'. Else put it in
    # 'icon_missing_links', which will be used if really no
    # icon exist for that record (there are chances that this
    # icon will be created later)
    #
    # If icon exists but not in metadata, try to update record metadata
    icon_exists_links = []
    icon_missing_links = []
    if out == '':
        masters_paths = [link['d'] for link in bfo.fields('8567_') \
                         if link.get('x', '') == 'Absolute master path' and \
                            link.get('d', '') != '']
        for master_path in masters_paths:
            try:
                path_components = master_path.split('\\')[-3:] # take 3 last components
                path_components[-1] = path_components[-1][:-4] # remove .jpg
                filename = path_components[-1] + '-Icon.jpg'
                path_components.append(filename)
                link = 'http://mediaarchive.cern.ch/MediaArchive/Photo/Public/' + \
                       '/'.join(path_components)
                # check if file exists
                if file_exists(link):
                    icon_exists_links.append('<a href="' + weburl + '/record/' + \
                                             bfo.control_field("001") + '">' + \
                                             '<img '+style+' src="' + link + '" alt="" border="0"/></a>')

                    # Also try to update the record metadata using the info.xml file
                    info_xml_url = 'http://mediaarchive.cern.ch/MediaArchive/Photo/Public/' + \
                                   '/'.join(path_components[:-1]) + \
                                   '/' + 'info.xml'
                    _perform_request_add_slave_url(info_xml_url)
                else:
                    icon_missing_links.append('<a href="' + weburl + '/record/' + \
                                              bfo.control_field("001") + '">' + \
                                              '<img '+style+' src="' + link + '" alt="" border="0"/></a>')
            except Exception, e:
                continue

        # First add icons that we know exist for sure
        for icon in icon_exists_links:
            if num_displayed_photo < max_photos:
                num_displayed_photo += 1
                out += icon
                out += separator

        # Last attempt: add icon even if not exists
        for icon in icon_missing_links:
            if num_displayed_photo < max_photos:
                num_displayed_photo += 1
                out += icon
                out += separator

    if min_photos > num_displayed_photo:
        return ""

    if max_photos == num_displayed_photo and separator:
        out += '<a href="%s/record/%s" style="text-decoration: none;"><span style="font-size: small; margin-left: 5px;">More &gt;&gt;</span></a>' %(weburl, bfo.control_field("001"))

    return out

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0

def file_exists(url, download_result=False):
    """
    Returns True if resource could be found at url. Else returns false

    @param download_result If False, use 'wget' with --spider option.
                           You should use download_result=True if accessed url has get/post parameters.
    """
    pipe_input, pipe_output, pipe_error = os.popen3('/usr/bin/wget %s -S -t 1 -T 3 -O - %s > /dev/null' % \
                                                    ((not download_result and '--spider') or '',
                                                    url))
    pipe_input.close()
    res = pipe_error.read()
    pipe_output.close()
    if not 'ERROR 404' in res:
        return True
    else:
        return False
