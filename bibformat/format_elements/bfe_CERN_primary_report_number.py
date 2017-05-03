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
"""BibFormat element - Prints list of primary report numbers
"""
__revision__ = "$Id$"

from invenio.bibformat_elements.bfe_report_numbers import \
          build_report_number_link

def format_element(bfo, separator=", "):
    """
    Prints list of primary report numbers (037__a)
    @param separator a separator between numbers
    """
    primary_report_numbers = bfo.fields('037__a')

    return separator.join([build_report_number_link(report_number) \
                           for report_number in primary_report_numbers])
