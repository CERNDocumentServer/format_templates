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
"""BibFormat element - Display Flash (swf) panorama attached to this record
"""
__revision__ = "$Id$"

import os
from invenio.bibdocfile import BibRecDocs

def format_element(bfo, separator='<br/>', width="800px", height="480px"):
    """
    Display Flash (swf) panorama attached to this record. Consider
    files attached as .swf file with doctype 'panoaram'.

    @param separator: printed between each panorama
    @param width: width of each panorama
    @param height: height of each panorama
    """
    out = ""
    panoramas = []
    bibarchive = BibRecDocs(bfo.recID)
    # Prepare the Javascripts
    for bibdocfile in bibarchive.list_latest_files(doctype='panorama'):
        if bibdocfile.get_format() == '.swf':
            pano_index = len(panoramas)
            panoramas.append('embedpano({swf:"%(swf_file)s", target:"panoramabox%(pano_index)s", width:"%(width)s", height:"%(height)s"});' \
                            % {'swf_file': bibdocfile.get_url(),
                               'pano_index': pano_index,
                               'width': width,
                               'height': height})
    if panoramas:
        out = separator.join(['<div id="panoramabox%i" style="margin:auto"></div>' %i for i in xrange(len(panoramas))])
        out += '<script type="text/javascript" src="/js/swfkrpano.js"></script>'
        out += '<script type="text/javascript">' + \
               ''.join(panoramas) + \
               '</script>'

    return out

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0
