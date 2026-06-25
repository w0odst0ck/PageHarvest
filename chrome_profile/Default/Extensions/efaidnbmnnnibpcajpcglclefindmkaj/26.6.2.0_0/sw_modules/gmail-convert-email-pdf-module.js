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
import{floodgate as t}from"./floodgate.js";import{util as o}from"./util.js";import{setExperimentCodeForAnalytics as e,removeExperimentCodeForAnalytics as i}from"../common/experimentUtils.js";import{checkUserLocaleEnabled as l,safeParseFeatureFlag as n}from"./gsuite/util.js";async function a(a){const[r,c]=await Promise.all([t.hasFlag("dc-cv-gmail-convert-email-to-pdf"),t.hasFlag("dc-cv-gmail-convert-email-to-pdf-control")]);let m;r?m=n("dc-cv-gmail-convert-email-to-pdf"):c&&(m=n("dc-cv-gmail-convert-email-to-pdf-control"));const s=l(m?.enLocaleEnabled,m?.nonEnLocaleEnabled);r&&s?(i("GCEC"),e("GCE")):c&&s?(i("GCE"),e("GCEC")):(i("GCE"),i("GCEC"));const g=m?.selectors,f=m?.fteConfig,p=m?.fteEnabled||!1,T=!o.isAcrobatTouchPointEnabled("acrobat-touch-point-in-gmail");a({enableGmailConvertEmailToPdfTouchpoint:r&&!T&&s,selectors:g,fteEnabled:p,fteConfig:f,fteToolTipStrings:{title:o.getTranslation("gmailConvertEmailToPDFFteTitle"),description:o.getTranslation("gmailConvertEmailToPDFFteDescription"),button:o.getTranslation("closeButton")},touchpointText:o.getTranslation("gmailConvertEmailToPDF"),tooltipText:o.getTranslation("gmailConvertEmailToPDFTooltip")})}export{a as gmailConvertEmailPdfInit};