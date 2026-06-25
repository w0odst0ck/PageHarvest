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
import{dcLocalStorage as t}from"../../common/local-storage.js";import{analytics as e,events as o}from"../../common/analytics.js";import{LOCAL_FILE_PERMISSION_URL as n,ONE_WEEKS_IN_MS as i,POPUP_CONTEXT as a,TWO_WEEKS_IN_MS as c}from"../../common/constant.js";import{util as s}from"../js/content-util.js";import{openTabPopupOverride as l}from"../../common/action-util.js";await t.init();const{id:m,url:r}=await chrome.tabs.getCurrent(),d=t.getItem("showLocalisedGif");e.event(o.LOCAL_FTE_DISPLAYED,{VARIANT:d?"WithLocalisedGif":"WithoutLocalisedGif"});const L=t.getItem("dc")?i:c;t.setWithTTL("localFteCooldown",!0,L);const _=(t.getItem("localFteCount")||0)+1;t.setItem("localFteCount",_),$(document).ready(()=>{s.translateElements(".translate");let i=chrome.i18n.getMessage("@@ui_locale");const c=d?"fte.svg":"fte_old.svg";$("#local-file-animated-fte").css("background-image",`url(../images/LocalizedFte/${i}/${c}),url(../images/LocalizedFte/en_US/${c})`),$("#closeLocalFte").click(()=>{s.sendAnalytics(o.LOCAL_FTE_CROSS_BUTTON_CLICKED),chrome.runtime.sendMessage({main_op:"closeLocalFte"})}),$("#continueLocalFte").click(async()=>{s.sendAnalytics(o.LOCAL_FTE_GO_TO_SETTINGS_CLICKED),t.setItem("pdfViewer","true");const i=t.getItem("openSettingsInWindow");if(i){const e=t.getItem("localFteWindow"),{id:o,height:i,width:c,left:m,top:r}=e;chrome.windows.remove(o),chrome.windows.create({height:i,width:1.2*c,left:m,top:r,focused:!0,type:"normal",url:s.constructUrlWithParams(n,{context:a.LOCAL_FILE_COACHMARK,autoDismiss:!0})},e=>{l({},e.tabs[0].id),t.setItem("settingsWindow",{id:e.tabs[0].id})})}else{const{id:t,windowId:e}=await chrome.tabs.create({url:s.constructUrlWithParams(n,{context:a.LOCAL_FILE_COACHMARK,autoDismiss:!0}),active:!0});chrome.windows.update(e,{focused:!0},()=>{l({},t)})}e.event(o.LOCAL_FTE_SETTINGS_OPENED,{VARIANT:i?"InWindow":"InTab"})}),$("#localFteDontShowAgainInput").click(()=>{document.getElementById("localFteDontShowAgainInput").checked?(e.event(o.LOCAL_FTE_DONT_ASK_CHECKED),t.setItem("localFteDontShowAgain",!0)):(e.event(o.LOCAL_FTE_DONT_ASK_UNCHECKED),t.removeItem("localFteDontShowAgain"))}),_>4&&$("#localFteDontShowAgainInput,#localFteDontShowAgainText").removeAttr("hidden"),window.onbeforeunload=()=>{s.sendAnalytics(o.LOCAL_FTE_WINDOW_CLOSED);const t=Date.now();for(;Date.now()-t<60;);},document.addEventListener("keydown",t=>{"F11"==t.key&&t.preventDefault()})});