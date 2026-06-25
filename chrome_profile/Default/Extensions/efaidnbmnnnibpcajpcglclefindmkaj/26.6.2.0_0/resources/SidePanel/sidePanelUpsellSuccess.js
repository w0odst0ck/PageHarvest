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
import{dcLocalStorage as e}from"../../common/local-storage.js";import{signInUtil as r}from"../../browser/js/viewer/signInUtils.js";const n=new URLSearchParams(window.location.search),s=function(e){if(!e)return null;try{return new URLSearchParams(decodeURIComponent(e))}catch(e){return null}}(n.get("gsp")),o=parseInt(n.get("tabId"),10);if(function(e,r){const n=e.get("pdfspaceupsell")||r?.get("pdfspaceupsell");return"1"===n||"true"===n}(n,s)){const e=function(e,r){let n=e;return r&&Number.isNaN(n)&&(n=parseInt(r.get("tabId"),10)),n}(o,s);Number.isNaN(e)?window.close():function(e){chrome.runtime.sendMessage({main_op:"post_pdfspace_upsell",tabId:e},()=>{chrome.runtime.lastError&&console.error("Error sending post_pdfspace_upsell:",chrome.runtime.lastError.message),window.close()})}(e)}else Number.isNaN(o)?window.close():async function(n){if(await e.init(),e.getItem("upsellFromAnon")){const s=await chrome.tabs.query({active:!0,currentWindow:!0});if(s.length>0){const o=s[0].id;e.setItem("signInOriginHash","#/side-panel"),r.sidepanelPostAnonUpsellSignIn(!0,o,n),chrome.runtime.sendMessage({main_op:"post_upsell_anon",tabId:n})}return}chrome.runtime.sendMessage({main_op:"post_upsell",tabId:n},()=>{try{chrome.runtime.lastError&&console.error("Error sending message:",chrome.runtime.lastError.message)}finally{window.close()}})}(o);