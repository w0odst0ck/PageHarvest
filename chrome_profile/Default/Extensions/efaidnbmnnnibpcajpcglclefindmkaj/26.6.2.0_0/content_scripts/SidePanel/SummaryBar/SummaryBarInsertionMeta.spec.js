/*************************************************************************
* ADOBE CONFIDENTIAL
* ___________________
*
*  Copyright 2015 Adobe Systems Incorporated
*  All Rights Reserved.
*
* NOTICE:  All information contained herein is, and remains
* the property of Adobe Systems Incorporated and its suppliers,
* if any.  The intellectual and technical concepts contained
* herein are proprietary to Adobe Systems Incorporated and its
* suppliers and are protected by all applicable intellectual property laws,
* including trade secret and or copyright laws.
* Dissemination of this information or reproduction of this material
* is strictly forbidden unless prior written permission is obtained
* from Adobe Systems Incorporated.
**************************************************************************/
const loadModules=()=>(jest.resetModules(),delete window.SummaryBarConfig,delete window.SummaryBarInsertionMeta,require("./SummaryBarConfig.js"),require("./SummaryBarInsertionMeta.js"),{SummaryBarInsertionMeta:window.SummaryBarInsertionMeta});describe("SummaryBarInsertionMeta",()=>{beforeEach(()=>{document.body.innerHTML="",window.dcLocalStorage={getItem:jest.fn().mockReturnValue(null)}}),it("parses ::prepend selector directives",()=>{const{SummaryBarInsertionMeta:e}=loadModules();expect(e.parseSelectorDirective("#mw-content-text .mw-parser-output::prepend")).toEqual({query:"#mw-content-text .mw-parser-output",insertBefore:!0})}),it("resolves siteInsertion for matching subdomains",()=>{const{SummaryBarInsertionMeta:e}=loadModules(),t=e.resolveSiteInsertionEntry({siteInsertion:{"wikipedia.org":{selector:"#mw-content-text .mw-parser-output::prepend"}}},"en.wikipedia.org");expect(t?.selector).toContain("mw-parser-output")}),it("inserts before the matched node when ::prepend is set",()=>{const{SummaryBarInsertionMeta:e}=loadModules();document.body.innerHTML='\n            <div id="mw-content-text">\n                <div class="mw-parser-output">\n                    <p>Article body</p>\n                </div>\n            </div>\n        ';const t=e.parseSelectorDirective("#mw-content-text .mw-parser-output::prepend"),r=e.resolveInsertionFromDirective(t),o=document.querySelector(".mw-parser-output");expect(r.parent).toBe(document.getElementById("mw-content-text")),expect(r.before).toBe(o),expect(r.preferArticleColumnWidth).toBe(!0)}),it("reads selector hints from cached Floodgate meta storage",()=>{window.dcLocalStorage.getItem.mockReturnValue(JSON.stringify({siteInsertion:{"wikipedia.org":{selector:".mw-parser-output::prepend"}}})),document.body.innerHTML='\n            <main>\n                <div class="mw-parser-output"><p>Body</p></div>\n            </main>\n        ',Object.defineProperty(window,"location",{configurable:!0,value:{hostname:"en.wikipedia.org"}});const{SummaryBarInsertionMeta:e}=loadModules(),t=e.resolveForCurrentHost();expect(t?.before).toBe(document.querySelector(".mw-parser-output")),expect(t?.preferArticleColumnWidth).toBe(!0)})});