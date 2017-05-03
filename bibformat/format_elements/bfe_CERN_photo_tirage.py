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
"""BibFormat element - Prints Photolab 'tirage'(s)
"""
__revision__ = "$Id$"

def format_element(bfo, separator=", ", mode="list"):
    """
    Prints Photolab 'tirage'(s)
    @param separator a separator between tirage
    @param mode Either 'list' (to list all tirage) or 'count' (to return number of tirages)
    """
    out = ''
    tirages = bfo.fields('924__a')
    if tirages == []:
        tirages = bfo.fields('8567_8')
        tirages.sort()
        tirages = [tirages[item] for item in range(0, len(tirages)) if tirages[item-1]!=tirages[item]]

    if mode.lower() == 'count' and len(tirages) > 0:
        return len(tirages)
    else:
        return separator.join(tirages)
