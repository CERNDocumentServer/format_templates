# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015 CERN.
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
"""BibFormat element - Prints links to download all pictures
"""

from invenio.config import CFG_SITE_URL
from invenio.bibdocfile import BibRecDocs
from invenio.bibdocfile_config import CFG_BIBDOCFILE_SUBFORMATS_TRANSLATIONS
from invenio.textutils import nice_size


def format_element(bfo):
    """
    Prints buttons to download all photos for each size
    """
    current_bibrecdoc = BibRecDocs(bfo.recID)
    if len(current_bibrecdoc.bibdocs) < 2:
        # If we have less than 2 photos, there is no point in displaying the
        # "Download all" buttons
        return
    wrapper = '''<style>
                #downloadallphotos {
                    clear: both;
                    font-size: small;
                    color: #555444;
                    margin-left: 10px;
                }
                #downloadallphotos a {
                    border-radius: 5px;
                    box-shadow: 1px 1px 1px 1px #CCCCCC;
                    color: #222222;
                    display: inline-block;
                    margin: 2px 5px;
                    padding: 3px;
                    text-decoration: none;
                    background-color: #E6E6FA;
                }
                #downloadallphotos a:hover {
                    background: -moz-linear-gradient(center top , #3A3A3A 0%, #7D7E7D 100%) repeat scroll 0 0 rgba(0, 0, 0, 0);
                    color: #fff;
                }
                </style>'''
    wrapper += '''<div id="downloadallphotos">Download all pictures:'''
    buttons = ''
    for (size, internal_size) in CFG_BIBDOCFILE_SUBFORMATS_TRANSLATIONS:
        total = current_bibrecdoc.get_total_size_latest_version(bfo.user_info, internal_size)
        # don't display the button if the size will be 0
        if total:
            buttons += '<a %(original)s href="%(site)s/record/%(recID)s/files/allfiles-%(size)s">%(size)s (%(total)s)</a>' \
                % {'original': size == 'original' and 'data-size="Original"' or '',
                   'site': CFG_SITE_URL,
                   'recID': bfo.recID,
                   'size': size,
                   'total': nice_size(total)}
    # If there are no buttons to display, don't display the rest of the HTML
    if buttons:
        return wrapper + buttons


def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0
