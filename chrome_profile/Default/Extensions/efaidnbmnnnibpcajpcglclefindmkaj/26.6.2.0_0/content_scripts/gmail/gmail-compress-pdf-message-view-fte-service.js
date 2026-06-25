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
import{sendAnalytics,sendErrorLog}from"../utils/util.js";import{createFteTooltip,addFteCloseButtonListener,updateFteToolTipCoolDown}from"../utils/fte-utils.js";import state from"./state.js";const SOURCE="gmail_chrome",GMAIL_COMPRESS_PDF_MESSAGE_VIEW_WORKFLOW="compress_pdf_message_view",MESSAGE_VIEW_FTE_STORAGE_KEY="acrobat-gmail-message-view-compress-pdf-fte-config";export const addFte=async()=>{try{const e=state?.compressPdfMessageViewFteState?.ctaContainerForFTE;if(!e)return;const s=state?.gmailMessageViewCompressPDFConfig,t=s?.fteToolTipStrings||{},o=createFteTooltip({title:t.title,description:t.description,button:t.button},"compressPDFMessageView");o.classList.add("acrobat-fte-tooltip-container-message-view-js-positioned");const r=()=>{o.remove(),o.clickOutsideHandler&&document.removeEventListener("click",o.clickOutsideHandler),o.keydownHandler&&document.removeEventListener("keydown",o.keydownHandler,!0)};o.clickOutsideHandler=e=>{o.contains(e.target)||(r(),sendAnalytics([["DCBrowserExt:CompressPDF:MessageView:Fte:Dismissed",{source:SOURCE,workflow:"compress_pdf_message_view"}]]))},o.keydownHandler=e=>{"Escape"===e.key&&(r(),sendAnalytics([["DCBrowserExt:CompressPDF:MessageView:Fte:Dismissed",{source:SOURCE,workflow:"compress_pdf_message_view"}]]))},addFteCloseButtonListener(o,{fteType:"compressPDFMessageView",onClose:()=>{r(),sendAnalytics([["DCBrowserExt:CompressPDF:MessageView:Fte:Closed",{source:SOURCE,workflow:"compress_pdf_message_view"}]])},sendErrorLog:sendErrorLog}),document.addEventListener("click",o.clickOutsideHandler,{once:!0}),document.addEventListener("keydown",o.keydownHandler,!0),e.appendChild(o),sendAnalytics([["DCBrowserExt:CompressPDF:MessageView:Fte:Shown",{source:SOURCE,workflow:"compress_pdf_message_view"}]]),await updateFteToolTipCoolDown(s?.fteConfig,MESSAGE_VIEW_FTE_STORAGE_KEY)}catch(e){sendErrorLog("GmailCompressPDFMessageViewFte","Failure in adding FTE to compress PDF message view")}finally{state?.compressPdfMessageViewFteState&&(state.compressPdfMessageViewFteState.ctaContainerForFTE=null)}};