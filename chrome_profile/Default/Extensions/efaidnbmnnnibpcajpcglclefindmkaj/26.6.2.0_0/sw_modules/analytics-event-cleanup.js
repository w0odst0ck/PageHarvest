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
import{dcLocalStorage as e}from"../common/local-storage.js";import{removeExperimentCodeForAnalytics as t}from"../common/experimentUtils.js";import{floodgate as r}from"./floodgate.js";import{cleanupOldPdfRenderingTrackingStorage as o}from"../common/pdf-rendering-tracking.js";const i=["DCBrowserExt:OneNote:Visited","DCBrowserExt:DocsGoogle:Visited:Document","DCBrowserExt:DocsGoogle:Visited:Spreadsheet","DCBrowserExt:DocsGoogle:Visited:Presentation","DCBrowserExt:Gdrive:Image:Opened","DCBrowserExt:Gmail:Image","DCBrowserExt:Gmail:ImageAttachment:Opened","gmail-pdf-default-viewership-session-count","gdrive-pdf-default-viewership-session-count","DCBrowserExt:ChatGPT:DownloadAsPdf:Clicked","DCBrowserExt:GDrive:TripleDotMenuClicked","DCBrowserExt:GDrive:TopFileBarMenuClicked:SingleSelect","DCBrowserExt:GDrive:TopFileBarMenuClicked:MultiSelect","DCBrowserExt:GDrive:RightClickMenuClicked:SingleSelect","DCBrowserExt:GDrive:RightClickMenuClicked:MultiSelect"],s=["GDCT","GDCC","GDIF","GDTT","GDTF","GDCF","OT","OTC","EMP","LI","LIC","LC","LCC","LFP","LFF","LFC","GIT","GIC","GIDN","GDIN","GDIT","GDIC","GSH","GSHC","GST","GSC","GCO","GCOC","CRT","CRI","CRC","CCT","CCTC","CDR","CDRC","GMPC","GMP1","GMP2"],C=async()=>{((e=[])=>{Array.isArray(e)&&0!==e.length&&e.forEach(e=>{t(e)})})(s),(async()=>{try{const t=e.getAllItems(),o=[];Object.keys(t).forEach(t=>{const i=t.match(/^DCBrowserExt:([^:]+):Visited$/);if(i&&i.length>1){const s=`dc-cv-${i[1].toLowerCase()}-analytics-visited`;o.push((async()=>{await r.hasFlag(s)||await e.removeItem(t)})())}}),await Promise.all(o)}catch(e){}})(),o(),((t=[])=>{Array.isArray(t)&&0!==t.length&&t.forEach(t=>{e.getItem(t)&&e.removeItem(t)})})(i)};export{C as clearEventsFromLocalStorage};