# -*- coding: utf-8 -*-
# $Id$

# This file is part of Invenio.
# Copyright (C) 2013 CERN.
#
# The Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# The Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

from invenio.bibformat_elements.bfe_copyright import CFG_CERN_LICENSE_URL
from invenio.bibknowledge import get_kb_mapping

def format_element(bfo, resource_type="photo"):
    """
    Used to put a copyright overlay on top of a resource (photo, video, ..)
    @param resource_type: the type of the resource the overlay will be placed on top of
    """

    if resource_type != 'photo':
        #not implement
        return ''
    output = """
        <script type="text/javascript">
            hs.creditsText = '© %(credit_text)s';
            hs.creditsHref = '%(credit_url)s';
            hs.creditsTitle = 'The use of photos requires prior authorization from %(credit_text)s';
        </script>"""

    # There might be more that one copyright and licence, select the one that
    # applies to the record, not a single file (one without '8' subfield)
    copyrights = bfo.fields('542__')
    copyright_holder = ""
    copyright_url = ""
    for copyright in copyrights:
        if not copyright.get('8', None):
            copyright_holder = copyright.get('d')
            copyright_url = copyright.get('u')
            break

    licences = bfo.fields('540__')
    licence = ""
    for lic in licences:
        if not lic.get('8', None):
            licence = lic.get('a')
            break

    if licence.startswith('CC-BY'):
        return """
        <script type="text/javascript">
            hs.creditsText = '%(credit_text)s';
            hs.creditsHref = '%(credit_url)s';
            hs.creditsTitle = '%(credit_text)s';
        </script>""" % {'credit_text': licence,
                        'credit_url' : get_kb_mapping(kb_name='LICENSE2URL', key=licence)['value']}

    if not copyright_holder:
        copyright_holder = 'CERN'

    if copyright_holder == 'CERN' and not copyright_url:
        copyright_url = CFG_CERN_LICENSE_URL


    if copyright_holder == 'CERN':
        output += """
        <script type="text/javascript" src="/js/overlay.min.js"></script>
        <script type="text/javascript" src="/js/copyright_notice.min.js"></script>
        <link href="/img/overlay.css" type="text/css" rel="stylesheet" />
        """
    return output % {'credit_text': copyright_holder,
                      'credit_url': copyright_url}

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0

