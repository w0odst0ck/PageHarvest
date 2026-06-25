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
export const openWebpageToPdfViewerForTab=e=>{if(!e||!e.id)return;const o=(e.title||"webpage").replace(/[<>:"/\\|?*\x00-\x1F]/g,"").replace(/\s+/g," ").trim().substring(0,200)||"webpage",t=o.endsWith(".html")?o:`${o}.html`,r=e.url||"",n=`https://convert-pdf-webpage/?tabId=${e.id}&tabOriginalUrl=${encodeURIComponent(r)}`,a=`${chrome.runtime.getURL("viewer.html")}?pdfurl=${encodeURIComponent(`${n}&acrobatPromotionSource=webpage_chrome-convert_to_pdf`)}&pdffilename=${encodeURIComponent(t)}&acrobatPromotionWorkflow=${encodeURIComponent("html-to-pdf")}`;chrome.tabs.create({url:a,active:!0})};