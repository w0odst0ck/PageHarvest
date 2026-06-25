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
import{dcLocalStorage as n}from"../../common/local-storage.js";await n.init();const e=new URLSearchParams(window.location.search).get("tabId"),i=n.getItem("signInOriginTouchpoint")||"signInSuccess",o=n.getItem("signInOriginHash")||"#/side-panel";n.removeItem("signInOriginTouchpoint"),n.removeItem("signInOriginHash"),chrome.runtime.sendMessage({main_op:"reloadTab",tabId:e,touchpoint:i,hashRoute:o}),window.close();