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
import{dcLocalStorage as e}from"../../common/local-storage.js";import{loggingApi as a}from"../../common/loggingApi.js";import{getGenAIServiceVariant as r}from"../../common/util.js";import{util as t}from"../../browser/js/content-util.js";import{getSidePanelTabId as s,connectSidePanelPort as n}from"./sidePanelUtil.js";export class Cdn{urlParams=new URLSearchParams(window.location.search);tabId=s();iframeElement=document.getElementById("sidepanel");constructor({initTimeStamp:s,hostedHashRoute:o,touchpoint:i,anonGenAISSRHtml:m,onIframeLoad:d,onIframeError:l}){const p=new URL(e.getItem("sidepanelUrl"));p.hash=o;const c="true"===e.getItem("adobeInternal"),h="false"!==e.getItem("logAnalytics"),g="false"!==e.getItem("ANALYTICS_OPT_IN_ADMIN"),f=e.getItem("appLocale")||chrome.i18n.getMessage("@@ui_locale");p.searchParams.append("la",h&&g),p.searchParams.append("ca",chrome.runtime.id),p.searchParams.append("cluster",r()),p.searchParams.append("locale",f),p.searchParams.append("uuid",e.getItem("sidePanelUUID")),p.searchParams.append("adi",c),p.searchParams.append("its",s),p.searchParams.append("ev",this.urlParams.get("version")),p.searchParams.append("ecid",e.getItem("ECID")),p.searchParams.append("fabVariant",e.getItem("fabVariant")||""),p.searchParams.append("gaiuo",e.getItem("enableGenAIUnlimitedOffer")),p.searchParams.append("utl",!0),p.searchParams.append("uua",!!e.getItem("enableUUA")),p.searchParams.append("home",!!e.getItem("isSidePanelHomeEnabled")),p.searchParams.append("fgContextVars",JSON.stringify(e.getItem("fgContextVars")||{})),p.searchParams.append("hsnap",!!m),p.searchParams.append("slt",t.getTranslation("tooltipTextEnabled")),this.iframeElement.onload=()=>{a.info({message:"Hosted iframe loaded",url:this.iframeElement.src,touchpoint:i}),d?.()},this.iframeElement.onerror=e=>{a.error({message:"Error in loading hosted iframe",error:e.toString(),url:this.iframeElement.src,touchpoint:i}),l?.()},this.iframeElement.src=p.href,this.origin=p.origin,this.port=n(this.tabId,s)}isCdnReady=new Promise((e,a)=>{const r=setTimeout(()=>{a(new Error("Hosted shell ready event timeout"))},2e4);this.isCdnReadyResolver=()=>{clearTimeout(r),e()}});supportedOrigin=e=>{try{return!![/^https:\/\/([a-zA-Z\d-]+\.){0,}(adobe|acrobat)\.com(:[0-9]*)?$/].find(a=>a.test(e))}catch(e){return!1}};sendMessage=e=>{this.iframeElement&&this.supportedOrigin(this.origin)&&this.isCdnReady.then(()=>this.iframeElement.contentWindow.postMessage(e,this.origin)).catch(e=>{a.error({message:"Error in sending message to hosted shell",error:e.toString()})})}}