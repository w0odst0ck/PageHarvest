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
import{loggingApi as e}from"../../common/loggingApi.js";import{connectSidePanelPort as o,getSidePanelTabId as n}from"./sidePanelUtil.js";import{hideTrefoilLoader as i}from"./loaderUIHelper.js";export function initOfflineMode(r){const t=n();o(t,r),i();const m=document.getElementById("offline-error");m?m.classList.remove("hidden"):e.debug({message:"offline-error element not found in DOM"})}