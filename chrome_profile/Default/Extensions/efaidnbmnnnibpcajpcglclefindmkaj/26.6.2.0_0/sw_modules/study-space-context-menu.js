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
import{dcLocalStorage as e}from"../common/local-storage.js";import{loggingApi as t}from"../common/loggingApi.js";import{analytics as a}from"../common/analytics.js";import{registerRequestId as o}from"./request-validator.js";import{common as n}from"./common.js";import{handleAddWebpageToProjectContextMenu as r,ensureAndExtractWebpageHTML as s}from"./add-webpage-to-project.js";import{STORAGE_KEYS as i}from"./constant.js";export const ADD_WEBPAGE_TO_NEW_STUDY_SPACE_CONTEXT_MENU="addWebpageToNewStudySpace";export const ADD_WEBPAGE_TO_EXISTING_STUDY_SPACE_CONTEXT_MENU="addWebpageToExistingStudySpace";export const CREATE_NEW_STUDY_SPACE_WEB_PATH="/studentspaces/collection/create-new-project";export async function createStudySpaceContextMenuItems({createContextMenuItem:e,parentMenuId:t,useNewContextMenuLabel:a,htmlURL:o,util:n}){const r=a&&t?t:void 0;await e({id:"addWebpageToNewStudySpaceContextMenu",parentId:r,title:n.getTranslation("addWebpageToNewStudySpaceContextMenu"),contexts:["page"],documentUrlPatterns:o,visible:!1}),await e({id:"addWebpageToExistingStudySpaceContextMenu",parentId:r,title:n.getTranslation("addWebpageToExistingStudySpaceContextMenu"),contexts:["page"],documentUrlPatterns:o,visible:!1}),await e({id:"separatorForStudySpaceMenu",parentId:r,type:"separator",contexts:["page"],documentUrlPatterns:o,visible:!1})}async function c(a,r,i){try{const a=function(t,a){const r=e.getItem("appLocale")||chrome.i18n.getMessage("@@ui_locale"),s=chrome.runtime.id,i=`req_${Date.now()}_${Math.random().toString(36).substring(2,8)}`;o(i,a);const c=n.getWelcomePdfUrlHost(),d={tabId:t.id,title:t.title,locale:r,extensionId:s,requestId:i},p=JSON.stringify(d),_=btoa(p),E=new URL(`${c}${CREATE_NEW_STUDY_SPACE_WEB_PATH}`);return E.searchParams.set("context",a),E.searchParams.set("payload",_),E.searchParams.set("isNew","1"),E.toString()}(r,i);s(r.id),chrome.tabs.create({url:a,active:!0}),t.info({message:"Direct create new Study Space initiated",tabId:r.id})}catch(e){t.error({message:"Error in direct create new Study Space",error:e?.message})}}export async function handleAddWebpageToNewStudySpaceContextMenu(t,o,n){await e.init();const s=e.getItem(i.KW_FTE_COMPLETED);a.event(a.e.CONTEXT_MENU_ADD_WEB_PAGE_TO_NEW_STUDY_SPACE,{FTE_COMPLETED:s?"true":"false"}),s?await c(0,o,n):r(t,o,n,{studyFlow:!0})}export function handleAddWebpageToExistingStudySpaceContextMenu(e,t,o){a.event(a.e.CONTEXT_MENU_ADD_WEB_PAGE_TO_EXISTING_STUDY_SPACE,{context:o}),r(e,t,o,{studyFlow:!0})}