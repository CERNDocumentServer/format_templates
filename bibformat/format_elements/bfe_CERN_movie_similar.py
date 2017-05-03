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
BibFormat element - Prints the movie link or player for the movie.
"""

__revision__ = "$Id$"

from invenio.config import weburl
from invenio.bibformat import format_records
from invenio.search_engine import perform_request_search

def format_element(bfo, display_recent_too='no', nb_max='10'):
    """
    Returns a list of similar movies.
    If there are none, and display_recent_too == 'yes', returns most recent movies
    @param display_recent_too if 'yes' and not similar movie, display most recent movies
    @param more_link if 'yes', print link to video collection
    """

    out = """
<script>
    $(document).ready(function(){
        $(".bfe_cern_movie_thumbnail").each(function(){
            if ( $.trim($(this).html()).length == 0 ) {
                $(this).html('<div style="font-weight: bold; text-align: center; margin-top: 33px;\">No preview available</div>');
            }
        });
    });
</script>
    """

    if nb_max.isdigit():
        nb_max = int(nb_max)
    else:
        nb_max = 10

    video_type = bfo.field('690C_a')

    search_in_coll = 'Video Movies'
    if 'rush' in video_type:
        search_in_coll = 'Video Rushes'

    results = perform_request_search(
        of="id",
        p="recid:{0!s}".format(bfo.recID),
        rm="wrd",
        c=search_in_coll,
        cc=search_in_coll
    )

    if bfo.recID in results:
        results.remove(bfo.recID)

    if len(results) < nb_max and display_recent_too == 'yes':
        other_results = perform_request_search(
            of="id",
            c=search_in_coll,
            cc=search_in_coll
        )
        if bfo.recID in other_results:
            other_results.remove(bfo.recID)
        results.extend(other_results)

    out += format_records(results[:nb_max], of='hs')

    return out

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0
