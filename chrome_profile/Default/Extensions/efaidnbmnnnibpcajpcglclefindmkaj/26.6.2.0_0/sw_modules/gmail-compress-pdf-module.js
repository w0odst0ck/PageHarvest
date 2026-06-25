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
import{floodgate as o}from"./floodgate.js";import{checkUserLocaleEnabled as t,safeParseFeatureFlag as e}from"./gsuite/util.js";import{util as s}from"./util.js";async function i(i){const[n,l]=await Promise.all([o.hasFlag("dc-cv-gmail-compress-pdf-touch-point"),o.hasFlag("dc-cv-gmail-compress-pdf-touch-point-control")]);let a;n?a=e("dc-cv-gmail-compress-pdf-touch-point"):l&&(a=e("dc-cv-gmail-compress-pdf-touch-point-control"));const r=t(a?.enLocaleEnabled,a?.nonEnLocaleEnabled),c=a?.selectors||{},p=a?.tooltip||{},m=a?.fteEnabled||!1,g=!s.isAcrobatTouchPointEnabled("acrobat-touch-point-in-gmail");i({enableGmailCompressPDFTouchPoint:n&&!g&&r,selectors:c,compressPDFSizeThreshold:a?.compressPDFSizeThreshold,compressPDFString:s.getTranslation("gmailCompressPDFTouchPoint"),compressPDFTooltipText:s.getTranslation("gmailCompressPDFTouchPointOnHoverTooltip"),fteToolTipStrings:{title:s.getTranslation("gmailCompressPDFTouchPointFTEHeader"),description:s.getTranslation("gmailCompressPDFTouchPointFteDescription"),button:s.getTranslation("closeButton")},enableGmailCompressPDFFteTooltip:m,gmailCompressPDFFteConfig:p,gmailCompressPDFOnHoverTooltip:s.getTranslation("gmailCompressPDFTouchPointOnHoverTooltip")})}export{i as gmailCompressPDFInit};