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
const MESSAGE_VIEW_FTE_STORAGE_KEY="acrobat-gmail-message-view-compress-pdf-fte-config",MESSAGE_VIEW_FTE_CONTAINER_CLASS="acrobat-fte-tooltip-container-compressPDFMessageView",COMPRESS_PDF_CTA_CONTAINER_ID="compress-pdf-cta-container";class GmailCompressPDFMessageViewFte{id="GmailCompressPDFMessageViewFte";timeout=3e3;static GMAIL_DOMAINS=["mail.google.com"];constructor(){const e=window.location.hostname;if(!GmailCompressPDFMessageViewFte.GMAIL_DOMAINS.some(t=>e.includes(t)))return this.isEligible=async()=>!1,void(this.render=async()=>{});this.initPromise=this.loadServices()}async loadServices(){[this.fteUtils,this.gmailCompressPDFMessageViewFteService,this.state]=await Promise.all([import(chrome.runtime.getURL("content_scripts/utils/fte-utils.js")),import(chrome.runtime.getURL("content_scripts/gmail/gmail-compress-pdf-message-view-fte-service.js")),import(chrome.runtime.getURL("content_scripts/gmail/state.js"))])}async render(){await(this.gmailCompressPDFMessageViewFteService?.addFte?.()),GmailCompressPDFMessageViewFte.keepFteAlive()}static keepFteAlive(){const e=document.querySelector(`.${MESSAGE_VIEW_FTE_CONTAINER_CLASS}`);if(!e)return;let t=e.parentElement;if(!t)return;const s=new MutationObserver(()=>{if(e.isConnected)return;if(t?.isConnected)return void s.disconnect();const i=document.getElementById("compress-pdf-cta-container");i&&(i.appendChild(e),t=i)});s.observe(document.body,{childList:!0,subtree:!0})}async isEligible(){const e=await chrome.runtime.sendMessage({main_op:"gmail-message-view-compress-pdf-init"});if(!e?.enableGmailMessageViewCompressPDFTouchPoint||!e?.enableFte)return!1;await this.initPromise;const t=this.state?.default,s=t?.compressPdfMessageViewFteState?.ctaContainerForFTE;if(!s)return!1;const i=await(this.fteUtils?.initFteStateAndConfig?.(MESSAGE_VIEW_FTE_STORAGE_KEY)),o=e?.fteConfig;return await(this.fteUtils?.shouldShowFteTooltip?.(o,i,e.enableFte))}}