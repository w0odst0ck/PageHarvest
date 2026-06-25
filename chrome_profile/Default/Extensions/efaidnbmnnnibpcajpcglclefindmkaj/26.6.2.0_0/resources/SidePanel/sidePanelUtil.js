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
import e from"../../libs/readability.js";const{Readability:t,isProbablyReaderable:n}=e;export const getSidePanelTabId=()=>parseInt(new URLSearchParams(window.location.search).get("tabId"),10);export const sendMessageWithTab=(e,t)=>{chrome.runtime.sendMessage({...e,tab:{id:t}})};export const createSendAnalytics=e=>t=>{t&&sendMessageWithTab({main_op:"analytics",analytics:[t]},e)};function a(e){return e.clientHeight>0&&e.clientWidth>0}async function r(e,t=!0){const r=()=>n(e,{visibilityChecker:t?a:void 0});if(r())return!0;const s=(await chrome.runtime.sendMessage({type:"get_sidepanel_state"})).isOpen?1500:5e3;return new Promise(e=>{const t=setInterval(()=>{r()&&(clearInterval(t),clearTimeout(n),e(!0))},300),n=setTimeout(()=>{clearInterval(t),e(!1)},s)})}async function s(e){const n=(new DOMParser).parseFromString(e,"text/html");if(await r(n,!1)){return new t(n).parse().content}return e}export const HOSTED_ROUTES={HOME:"#/home",SIDE_PANEL:"#/side-panel"};export const isGenAiRoute=e=>e.startsWith(HOSTED_ROUTES.SIDE_PANEL);export const isHomeShellRoute=e=>!isGenAiRoute(e);export function connectSidePanelPort(e,t){const n=chrome.runtime.connect({name:`sidepanel_${e}_${t}`}),a=setInterval(()=>{try{n.postMessage({action:"keep_alive"})}catch{clearInterval(a)}},2e4);return n.onDisconnect.addListener(()=>clearInterval(a)),n}export{r as isProbablyReaderableAsync,s as getReadableContent};