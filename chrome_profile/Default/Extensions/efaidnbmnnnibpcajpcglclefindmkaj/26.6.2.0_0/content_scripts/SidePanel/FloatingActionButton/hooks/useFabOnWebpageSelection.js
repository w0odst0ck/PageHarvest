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
import{useState,useEffect}from"react";export const useFabOnWebpageSelection=(e,t,c,a,u)=>{const[o,s]=useState({active:!1,text:""});return useEffect(()=>{e.setupSelectionModeCallback(s)},[e]),useEffect(()=>{if(o.active){e.makeFABOpaque(),t(!0),c(!0),a(!0);const o=setTimeout(()=>{a(!1),u||(t(!1),c(!1))},5e3);return()=>clearTimeout(o)}a(!1),u||(t(!1),c(!1))},[o]),o};