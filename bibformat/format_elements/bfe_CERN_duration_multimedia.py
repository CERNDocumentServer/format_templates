# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2013 CERN.
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
"""BibFormat element - Prints the duration of the movie
"""


def format_element(bfo):
    """
    Prints the duration of the movie (300__a) in a more firendly format:
    hh:mm:ss:ms -> hh:mm:ss.ms
    hh:mm:ss.ms -> to hh:mm:ss.ms h (if h > 0); to mm:ss.ms min (if h = 0 and min > 0); to ss.ms sec (if h = 0 and min = 0)
    """
    out = ''
    duration = bfo.field('300__a')
    if len(duration.split(':')) != 4: # not the hh:mm:ss:ms format
        return duration  
    try:
        last_colon = duration.rfind(':')
        duration = duration[:last_colon] + '.' + duration[(last_colon+1):]
        duration_parts = duration.split(':')
        for i, part in enumerate(duration_parts[:-1]):
            if out:
                break
            #do we have a positive value?
            if int(part) > 0:
                out += ':'.join(duration_parts[i:]) # only consider the parts from the current counter
                if i == 0:
                    out += ' h'
                elif i == 1:
                    out += ' min'
            else:
                continue
        if not out:
            out = "%s sec" %duration_parts[-1]
    except:
        #if there are any problems, return the original string
        out = duration
    return out
    

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0





