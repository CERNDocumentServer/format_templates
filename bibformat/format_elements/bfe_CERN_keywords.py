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
"""BibFormat element - Prints keywords
"""
__revision__ = "$Id$"

import cgi
from urllib import quote
from invenio.config import weburl

def format_element(bfo, separator=' ; ', link='yes', cern_keywords_only='yes', link_to_keywords_in_colls="", display_source="", other_langs="no"):
    """
    Display keywords of the record.


    @param separator: a separator between keywords
    @param link: links the keywords if 'yes' (HTML links)
    @param cern_keywords_only: if yes, print keywords only if 6531_9 == 'CERN'.
    @param link_to_keywords_in_colls: Comma-separated list of collections. Keywords links will be created with these collection as constraints. if 'auto', link restrict to current collection of the record
    @param display_source: display only keywords with subfield $9 that matches the specified value(s). Use commas to separate several sources. For eg display_source="CERN,author". Leave empty for all sources. (if cern_keywords_only='yes', 'display_source' parameter is ignored)
    """

    keywords_dictionary_list = bfo.fields('6531_')
    keywords_dictionary_list.extend(bfo.fields('653_1'))

    if other_langs == 'yes':
        #print the French keywords as well (only if they are different from the English ones)
        other_langs_kws = bfo.fields('6532_')
        for kw in other_langs_kws:
            if kw not in keywords_dictionary_list:
                keywords_dictionary_list.append(kw)

    out = []


    # Prepare list of values that we want to find in $9 for the
    # keyword to be displayed
    display_source_list = [source.strip() for source in display_source.split(',')]
    if cern_keywords_only.lower() == 'yes':
        display_source_list = ['CERN']

    # When specified, create a link for the keywords that restrict
    # search in the specified collection
    # Eg. link_to_keywords_in_colls = # 'brochure' will create links
    # like 'http://cds.cern.ch/search.py?c=Brochures&f=keyword&p=LHC'
    restrict_to_colls = ''
    if link_to_keywords_in_colls != '':
        if link_to_keywords_in_colls == 'auto':
            collection = bfo.kb('collid2type', bfo.field('980__a'))
            collection = collection.replace(' ', '+')
            restrict_to_colls = '&amp;c=' + collection
        else:
            restrict_to_colls = ''.join(['&amp;c=' + coll for coll \
                                         in link_to_keywords_in_colls.split(',')])

    for keywords_dictionary in keywords_dictionary_list:
        if display_source_list and not display_source_list == ['']:
            # We only want to display keywords coming from specified sources
            if not keywords_dictionary.get('9', '') in display_source_list:
                continue

        if keywords_dictionary.get('a', ''):
            if link == 'yes':
                keyword = '<a href="' + weburl + '/search?f=keyword&p='+ \
                            quote(keywords_dictionary['a']) + \
                            restrict_to_colls + \
                            '&amp;ln='+ bfo.lang+ \
                            '">' + cgi.escape(keywords_dictionary['a']) + '</a>'
            else:
                keyword = cgi.escape(keywords_dictionary['a'])


            out.append(keyword)

    return separator.join(out)

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0
