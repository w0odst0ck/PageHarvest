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
import{dcLocalStorage as e}from"../../common/local-storage.js";import{checkForImsSidCookie as o}from"../../common/util.js";import{largeBlobStorage as r}from"../../common/large-blob-storage.js";import t from"../../libs/lottie-light-esm.js";import{isGenAiRoute as n}from"./sidePanelUtil.js";export const hideTrefoilLoader=()=>{document.querySelector(".loader-container")?.classList.add("hidden")};export const showTrefoilLoader=()=>{document.querySelector(".loader-container").classList.remove("hidden"),t.loadAnimation({container:document.getElementById("lottie-animation"),renderer:"svg",loop:!0,autoplay:!0,path:chrome.runtime.getURL("/resources/SidePanel/TrefoilLoader-NoPad.json")})};export const getGenAiPrerenderState=async(t,a)=>{if(!n(t))return null;const i=await(async()=>{if("FABPill:Summarize"===a||"FAB:WebpageSelection:Summarize"===a)return!1;if(e.getItem("enableCSSSRForAnon")){return!await o()}return!1})(),l=await r.getItem("anonGenAISSRHtml");return{showPreRendered:i&&!!l,anonGenAISSRHtml:l}};export const shouldShowTrefoilLoader=e=>!e?.showPreRendered;