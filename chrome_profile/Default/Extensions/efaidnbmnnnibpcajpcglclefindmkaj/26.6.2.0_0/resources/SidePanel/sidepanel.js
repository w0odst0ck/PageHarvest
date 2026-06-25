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
import{dcLocalStorage as e}from"../../common/local-storage.js";import{util as t}from"../../browser/js/content-util.js";import{checkCdnConnectivity as o}from"../../common/util.js";import{createSendAnalytics as n,getSidePanelTabId as r,HOSTED_ROUTES as a,isHomeShellRoute as i}from"./sidePanelUtil.js";import{fetchAndSendHtmlContent as m}from"./htmlContentFetcher.js";import{getGenAiPrerenderState as s,shouldShowTrefoilLoader as d,showTrefoilLoader as l}from"./loaderUIHelper.js";import{Cdn as c}from"./cdn.js";import{initHomeMode as p}from"./home.js";import{initOfflineMode as f}from"./offline.js";import{registerHostedShellListeners as I}from"./shell-listeners.js";const h=Date.now();await e.init();const E=e.getItem("isSidePanelHomeEnabled"),u=document.getElementById("tooltipTextEnabled");E&&u&&(u.id="tooltipTextEnabledHome"),t.translateElementsByAppLocale(".translate");let w=e.getItem("touchpoint");e.removeItem("touchpoint");let S=e.getItem("hashRoute");e.removeItem("hashRoute"),w||(w="ExtensionAction",S=a.HOME),E||(S=a.SIDE_PANEL);const j=i(S),b=await s(S,w);d(b)&&l(),b?.showPreRendered&&(e=>{const t=document.createElement("iframe");t.id="sidepanelPreRendered",t.title="Adobe Chatbot",t.srcdoc=e,document.body.appendChild(t)})(b.anonGenAISSRHtml);const A=e.getItem("sidepanelUrl");if(A){await o(A)?j?await p(h,S,w):await async function(e,t,o){const i=r(),s=n(i);s(`DCBrowserExt:SidePanel:Opened:${t||"Unspecified"}`);const d=new c({initTimeStamp:e,hostedHashRoute:a.SIDE_PANEL,touchpoint:t,anonGenAISSRHtml:o?.anonGenAISSRHtml,onIframeLoad:()=>s(`DCBrowserExt:SidePanel:IframeLoaded:${t}`),onIframeError:()=>s(`DCBrowserExt:SidePanel:IframeLoadError:${t}`)});I({cdn:d,sendAnalytics:s,tabId:i,touchpoint:t}),await m({cdn:d,tabId:d.tabId,touchpoint:t})}(h,w,b):f(h)}