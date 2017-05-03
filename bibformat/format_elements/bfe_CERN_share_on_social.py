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
"""BibFormat element - bookmark for sharing on social.cern.ch

"""

from invenio.bibformat_elements import bfe_title
from invenio.config import CFG_SITE_URL, CFG_SITE_RECORD
from invenio.search_engine import record_public_p


def format_element(bfo, only_public_records=1):
    """
    Return a small bookmark element to share record on social.cern.ch

    @param only_public_records: if set to 1 (the default), prints the box only
        if the record is public (i.e. if it belongs to the root colletion and is
        accessible to the world).
    """

    if int(only_public_records) and not record_public_p(bfo.recID):
        return ""

    # Reuse bfe_title element to get the record's title
    title = bfe_title.format_element(bfo)

    url = '%(siteurl)s/%(record)s/%(recid)s' % \
          {'recid': bfo.recID,
           'record': CFG_SITE_RECORD,
           'siteurl': CFG_SITE_URL}

    bookmark_template = """
<style type="text/css">
    /* Some styling for the button */
    a.social-button{
        background: #fff;
        border: 1px solid #ddd;
        float: left;
        font-size: 12px;
        line-height: 14px;
        padding: 2px;
        text-decoration: none;
    }
    .social-button img{
        float: left;
        margin-right: 5px;
    }
    .social-button:hover{
        background: #ddd;
        border: 1px solid #bbb;
        text-decoration: none;
    }
    .social-header {
        margin: 0 auto;
    }
    .social-text {
        margin: 10px auto;
    }
    .social-remarks {
        margin: 5px auto;
    }
    .social-send {
        width: 50%%;
        left: 25%%;
    }
</style>
<link rel="stylesheet" href="/img/overlay.css" type="text/css" />
<script src="/js/overlay.min.js" type="text/javascript"></script>
<script type="text/javascript" src="%(siteurl)s/js/SP.RequestExecutor.js"></script>
<script type="text/javascript">// <![CDATA[

    ///////////////////////////// SOCIAL INTEGRATION FUNCTIONS ///////////////

    //Taken from https://espace2013.cern.ch/webservices-help/webauthoring/AdvancedAuthoring/Pages/IntegrateSocial_API.aspx

    function successHandler(data){
        console.log("Success");
        console.log(arguments);
        console.log(JSON.parse(data));
    }

    function errorHandler(){
        console.log("Error");
        console.log(arguments);
    }

    function postOnSocial(message){
        //Write into social, first get the formDigest value that will be used on the callback 'postMessage' function
        executeRestCall(formDigestUrl, "POST", null, postMessage, errorHandler, message);
      }

    function postMessage(data, message){
        //Get the Digest token from the RestCall
        var result = JSON.parse(data);
        var formDigest = result.d.GetContextWebInformation.FormDigestValue;
        var xhr = createCORSRequest("POST", myFeedManagerEndpoint + "my/Feed/Post");
        xhr.onload = function () {
          if(this.status == 200){
            // If the operation succeeds... than the feed has been updated.
            // Display success message in the magnific popup
            $('.social-header').width('110').text('Message posted !');
            $('.social-text').remove();
            $('.social-send').disabled = false
            $('.social-send').text('Close');
            $('.social-remarks').remove();
            // Unbind 'send' event and bind 'close' event to the button
            $(document).off('click', '.social-send');
            $('.social-send').click( function() {
                $('.mfp-close').click();
            });
          } else {    // We sent the request correctly but there has been a problem
            // Display error message in the magnific popup
            $('.social-header').width('100').text('Error !');
            $('.social-text').remove();
            $('.social-send').disabled = false
            $('.social-send').text('Close');
            $('.social-remarks').text('Please reload the page and try again (make sure you are logged in on social.cern.ch)')
            // Unbind 'send' event and bind 'close' event to the button
            $(document).off('click', '.social-send');
            $('.social-send').click( function() {
                $('.mfp-close').click();
            });
          }
        };
        //Set variables on the request object
        xhr.withCredentials = true;
        xhr.setRequestHeader("X-RequestDigest", formDigest);
        xhr.setRequestHeader("content-type", "application/json; charset=utf-8; odata=verbose");
        // Creating the data for the post
        // Those 6 backslashes below are to generate 2 backslashes in the REST request
        var data =  " { 'restCreationData':{ " +
            "   '__metadata':{ 'type':'SP.Social.SocialRestPostCreationData'}, " +
            "   'ID': null, " +
            "   'creationData':{ " +
            "       '__metadata':{'type':'SP.Social.SocialPostCreationData' }, " +
            "       'ContentItems':{ " +
            "           'results': [ " +
            "           { " +
            "               '__metadata' : {'type':'SP.Social.SocialDataItem' }, " +
            "           'Text':'%(record_url)s'," +
            "           'Uri':'%(record_url)s'," +
            "           'ItemType':'1'" +
            "           }, " +
            "           { " +
            "               '__metadata' : {'type':'SP.Social.SocialDataItem' }, " +
            "           'AccountName':'CERN\\\\\\\\cdssocial'," +
            "           'ItemType':'0'" +
            "           } " +
            "               ] " +
            "       }, " +
            "       'ContentText': '" + message + "', " +
            "       'UpdateStatusText':false " +
            "   } " +
            " }}";

        xhr.send(data);     // Uploads the message
    }

    // This function authenticate the User on Social (transparently to the User)
    function authenticateOnSocial(inputFunction){
        var executor = new SP.RequestExecutor(requestExecutorSite);
        executor.executeAsync({
          url: formDigestUrl,
          method: "GET",
          headers: {
            "Accept": "application/json; odata=verbose",
            "Access-Control-Allow-Origin": "*",
          },
          dataType: "json",
          error: function (xhr, ajaxOptions, thrownError) {
            // This function will be executed always. It is not an actual 'error' situation.
            try{
              // After the authentication completes we use the function passed in input, that will contain the calls for any other function on Social
              if(inputFunction !== null && inputFunction !== undefined){
                inputFunction();
              }
            }catch(e){ console.log("Error: input function parameter in the authentication function is not valid."); return; }
          },
        }); //End of executor.executeAsync
    }

    function createCORSRequest(method, url) {
        var xhr = new XMLHttpRequest();
        if ("withCredentials" in xhr) {
          // Check if the XMLHttpRequest object has a "withCredentials" property.
          // "withCredentials" only exists on XMLHTTPRequest2 objects.
          xhr.open(method, url, true);
        } else if (typeof XDomainRequest != "undefined") {
        // Otherwise, check if XDomainRequest.
        // XDomainRequest only exists in IE, and is IE's way of making CORS requests.
        xhr = new XDomainRequest();
        xhr.open(method, url);
        } else {
          // Otherwise, CORS is not supported by the browser.
          xhr = null;
        }
        if(xhr !== null){   // if the CORS is supported...
          xhr.withCredentials = true;
          xhr.setRequestHeader("accept", "application/json; odata=verbose");
        }
        return xhr;
    }

    function executeRestCall(url, method, data, onSucc, onError, extra) {
        var xhr = createCORSRequest(method, url);
        if (!xhr) {
            console.log('CORS not supported');
            throw new Error('CORS not supported');
        }
        else{
            xhr.onload = function () {
                onSucc(xhr.responseText, extra);    // passing the parameters and the results of the RESTcall to the 'onSucc' pointed function
            };

            xhr.onerror = onError;
            if (data !== null && data !== undefined && data !== ''){
                xhr.send(data);
            }else{
                xhr.send();
            }
        }
    }

    ///////////////////////////// END OF SOCIAL INTEGRATION FUNCTIONS ////////

    // Initial config variables for social.cern.ch
    // var socialUrl = "https://social-dev.cern.ch";
    var socialUrl = "https://social.cern.ch";
    var requestExecutorSite = socialUrl + "/_layouts/15/AppWebProxy.aspx";
    var myFeedManagerEndpoint = socialUrl + "/_api/social.feed/";
    var formDigestUrl = socialUrl + "/_api/contextinfo";
    jQuery.support.cors = true;         // Used for createCORSRequest()

    function createMagnificPopup() {
        $('.social-button').magnificPopup({
            items:{
                src:'<div class="social-popup overlay-white oc-content overlay-white-500">\
                        <h3 class="social-header">The following message will be posted:</h3>\
                        <textarea class="social-text">%(title)s %(record_url)s via @CDS Social</textarea>\
                        <div class="social-remarks"><span>Please make sure that you have an account on social.cern.ch !</span></div>\
                        <button type="buton" class="social-send">Post !</button>\
                    </div>',
                type: 'inline'
            }
        });
        // $.click won't work, because .social-send button is created dynamically
        // de-attach other callbacks first
        $(document).off('click', '.social-send');
        $(document).on('click', '.social-send', function(){
            // Replace the record's url and @CDS Social with placeholders
            var message = $('.social-text').val()
            var newMessage = message.replace('%(record_url)s', '{0}')
            var newMessage = newMessage.replace('@CDS Social', '@{1}')
            // Disable the button and put a loader image inside
            $('.social-send').disabled = true
            $('.social-send').html('<img src="../img/loading.gif" style="background: none repeat scroll 0%% 0%% transparent;"/>')
            authenticateOnSocial(function(){
                postOnSocial(newMessage);
            });
        });
    }

    jQuery( document ).ready(function() {
        // Determine if user is logged in or not based on the existence of
        // either 'cern-account' class or 'cern-signout'
        if($('.cern-account').length) {
            // User NOT logged in
            $('.social-button').click(function(){
                alert('You have to be signed in to do this!');
            });
        } else if($('.cern-signout').length) {
            // User logged in
            $('.social-button').click(function(){
                createMagnificPopup();
            });
            // attach the magnific popup now
            createMagnificPopup();
        } else {
            $('.social-button').click(function(){
                alert('There was an error, please reload the page and try again.\
                    If the error still occurs, please contact cds.support@cern.ch');
            });
        }
    });

// ]]>
</script>

    <a href="javascript:void(0)" class="social-button">
        <img src="/img/social-logo.png">
        Share on social.cern.ch
    </a>
    """ % {'siteurl': CFG_SITE_URL,
           'record_url': url,
           'title': title.replace("'", "\\'")}

    return bookmark_template


def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0
