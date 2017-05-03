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
"""BibFormat element - Prints link to conference
"""
__revision__ = "$Id$"
from invenio.config import CFG_SITE_URL
from invenio.search_engine import search_pattern
from invenio.bibformat_engine import BibFormatObject

def format_element(bfo,
           separator=", "):
    """
    Prints full conference link
    @param separator a separator between links
    """
    return_links = []
    links = [link for link in bfo.fields('962__') \
             if link.has_key('b')]
    collection = bfo.field('980__a')

    for link in links:
        # Sysno is 9 digits + 3 letters, and starts with '00'.
        # Recid is digits only and never starts with 0.
        # For sysno it can happen that the 3 ending letters are
        # dropped in the case they are CER

        recid_of_related_record = None
        if link['b'].isdigit() and not link['b'].startswith("0"):
            # This is a recid
            url = "%s/record/%s" % (CFG_SITE_URL, link['b'])
            recid_of_related_record = int(link['b'])
        else:
            # This is an Aleph sysno.
            aleph_sysno = link['b']
            if len(aleph_sysno) <= 9 and \
                   not aleph_sysno.lower().endswith('cer'):
                aleph_sysno += 'cer'

            if len(aleph_sysno) <= 9:
                aleph_sysno = aleph_sysno.zfill(12)

            url = "%s/search?sysno=%s" % (CFG_SITE_URL, aleph_sysno)
            if not link.get("t", ""):
                # There is no link label. We'll need to extract
                # information from related record. So fetch recid now
                try:
                    recid_of_related_record = search_pattern(p=aleph_sysno, f='sysno').tolist()[0]
                except:
                    # Too bad, no link will be displayed
                    continue

        # Build link address
        out = '<a href="%s">' % url

        # Build link label
        if link.get("t", "") != "":
            out += "%s</a>" % link.get("t", "")
        else:
            try:
                related_bfo = BibFormatObject(recid_of_related_record)
            except:
                # In case not related record was found
                continue
            if collection not in ["STANDARD", "ARC0201"]:
                meeting_title    = related_bfo.field('111__a')
                meeting_location = related_bfo.field('111__c')
                meeting_date     = related_bfo.field('111__d')
                publication_name = related_bfo.field('260__b')
                publisher_place  = related_bfo.field('260__a')
                publication_date = related_bfo.field('260__c')
                serie_statement  = related_bfo.field('490__a')
                volume           = related_bfo.field('490__v')
                report_number    = related_bfo.field('088__a')

                out += meeting_title    + ' ' + \
                       meeting_location + ' ' + \
                       meeting_date     + ' ' + \
                       publication_name + ' ' + \
                       publisher_place  + ' ' + \
                       publication_date + ' ' + \
                       serie_statement  + ' ' + \
                       volume           + ' ' + \
                       report_number    + '</a>'
            else:
                publication_title = related_bfo.field('245__a')
                publication_place = related_bfo.field('260__a')

                out += publication_title + ' ' + \
                       publication_place + '</a>'

        return_links.append(out)

        if link.has_key('k'):
            return_links.append(" - pp " + link['k'].replace('PR %%c', ' '))
        if link.has_key('n') and link['n'] != 'book':
            return_links.append('    <small>(list <a href="%s/search?p=%s&f=962__n\">conference papers</a>)</small>' % \
                                (CFG_SITE_URL, link['n']))

    return separator.join(return_links)


def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0
