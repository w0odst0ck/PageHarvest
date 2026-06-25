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
import{dcLocalStorage as t}from"./local-storage.js";import{POPUP_CONTEXT as e,SIDE_PANEL_SURFACE as o}from"./constant.js";import{getFloodgateFlag as n}from"./util.js";import r from"../sw_modules/dynamic-tab-context-manager.js";import{getDirectFlowShowCount as a,getDirectFlowCompleteItemsFiltered as i}from"../sw_modules/direct-verb-utils.js";import{loggingApi as c}from"./loggingApi.js";import{analytics as p,events as s}from"./analytics.js";async function u(t){t?await chrome.action.setPopup({popup:"browser/js/popup.html",tabId:t}):c.error("Tab ID is required — cannot configure toolbar action for unknown tab")}async function l(e){return t.getItem("isSidePanelHomeEnabled")?async function(t){t?await chrome.action.setPopup({popup:"",tabId:t}):c.error("Tab ID is required — cannot configure toolbar action for unknown tab")}(e):u(e)}export async function clearTabPopupOverride(t){return l(t)}export async function openTabPopupOverride(t,e){try{return await u(e),await chrome.action.openPopup(t)}catch(t){return c.error("Error in opening the extension popup menu:",t),await clearTabPopupOverride(e),Promise.reject()}}export async function getTabPopupContext(t,o){if(o)try{const t=new URL(o).searchParams.get("context");if(t)return t}catch(t){}const c=r.getPopupContext(t,o);if(c&&c!==e.DEFAULT)return c;if(await n("dc-cv-inactive-tab-direct-flow")){const t=a(),o=await i();if(t<2&&Array.isArray(o)&&o.length>0)return e.DIRECT_FLOW_COMPLETE}return e.DEFAULT}export async function configureActionOnTabContext(t){const o=await chrome.tabs.get(t).catch(()=>null),n=o?.url||o?.pendingUrl;return await getTabPopupContext(t,n)!==e.DEFAULT?u(t):l(t)}export function registerSidePanelClickHandler(t){chrome.action.onClicked.addListener(e=>{p.event(s.EXT_MENU_ICON_CLICKED,{eventContext:o.HOME}),t.getIsOpen(e.id)?chrome.sidePanel.close({tabId:e.id}).catch(t=>c.warn("Failed to close side panel via action click:",t)):chrome.sidePanel.open({tabId:e.id}).catch(t=>c.warn("Failed to open side panel via action click:",t))})}