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
import{floodgate as t}from"./floodgate.js";import{util as o}from"./util.js";import{setExperimentCodeForAnalytics as e,removeExperimentCodeForAnalytics as a}from"../common/experimentUtils.js";import{dcLocalStorage as n}from"../common/local-storage.js";import{resolveInactiveTabChallenger as r}from"./direct-verb-inactive-tab-utils.js";async function i(i){const[c,s,l]=await Promise.all([t.hasFlag("dc-cv-gmail-convert-to-pdf"),t.hasFlag("dc-cv-gmail-convert-to-pdf-fte"),t.hasFlag("dc-cv-gmail-convert-to-pdf-control")]),T=t.getFeatureMeta("dc-cv-gmail-convert-to-pdf-fte"),g=t.getFeatureMeta("dc-cv-gmail-convert-to-pdf"),d=t.getFeatureMeta("dc-cv-gmail-convert-to-pdf-control");let f,m,p,v;try{f=JSON.parse(T),m=c?JSON.parse(g):JSON.parse(d),p=m?.enLocaleEnabled||!1,v=m?.nonEnLocaleEnabled||!1}catch(t){}const P=function(t,o){const e=n.getItem("locale"),a="en-US"===e||"en-GB"===e;return a&&t||!a&&o}(m?.enLocaleEnabled,m?.nonEnLocaleEnabled);c&&P?(a("GCPC"),e("GCP")):l&&P?(a("GCP"),e("GCPC")):(a("GCP"),a("GCPC"));let u=!1;c&&P&&(u=await r("gmail"));const C=await async function(o){const e=[];let a={};const n=o.map(async o=>{const n=`dc-cv-gmail-${o}-metadata`;if(!await t.hasFlag(n))return;const r=t.getFeatureMeta(n);if(!r)return;let i;try{i=JSON.parse(r)}catch(t){}i?.selectors?.forEach(t=>e.push(t)),a={...a,...i?.types}});return await Promise.all(n),{selectors:e,fileExtToMimeTypeMap:a}}(m?.fileTypes||[]);i({enableConvertToPdfTouchpointInGmail:c&&P,enableGmailConvertToPdfFteToolTip:s&&P,acrobatTouchPointText:o.getTranslation("gmailConvertToPdf"),passwordProtectedConvertError:o.getTranslation("convertToPdfPasswordProtectedError"),enableConvertToPdfTouchpointInGmailControl:l&&P,fteTooltipStrings:{title:o.getTranslation("gmailConvertToPdfFteToolTipTitle"),description:o.getTranslation("gmailConvertToPdfFteToolTipDescription"),button:o.getTranslation("closeButton")},fteConfig:f,metadata:C,inactiveTabDirectVerbProcessingEnabled:u,convertToPdfToastMessage:o.getTranslation("convertToPdfToastMessage"),convertingTooltip:o.getTranslation("convertingTooltip"),convertingTouchPointText:o.getTranslation("convertingTouchPointText"),convertToPdfErrorToastMessage:o.getTranslation("convertToPdfErrorToastMessage"),convertToPdfTabCloseErrorToastMessage:o.getTranslation("convertToPdfTabCloseErrorToastMessage"),tryAgain:o.getTranslation("tryAgain"),surfaceName:o.getTranslation("surfaceNameGmail")})}export{i as gmailConvertToPdfInit};