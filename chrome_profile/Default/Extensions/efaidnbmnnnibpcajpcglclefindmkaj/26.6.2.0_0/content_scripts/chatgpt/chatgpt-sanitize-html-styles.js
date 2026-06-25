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
(()=>{const t=new Promise(t=>{chrome.runtime.sendMessage({main_op:"get-chatgpt-chat-html-to-pdf-config"},e=>t(e??null))}),e=import(chrome.runtime.getURL("content_scripts/utils/util.js"));window.preExtractHook=async(s,r,{targetSectionId:a}={})=>{const[n,o]=await Promise.all([t,e]),{default:i}=await import(chrome.runtime.getURL("content_scripts/chatgpt/state.js"));if(a&&i.capturedMissingMessages.has(a)){const t=window.acrobatTargetSectionHtmlStore,e=Array.isArray(t)?t.find(t=>t.targetSectionId===a):null;return e?.element&&await(async(t,e,s,r)=>{try{const{default:a}=await import(chrome.runtime.getURL("content_scripts/chatgpt/state.js")),n=a.capturedMissingMessages.get(s);if(!n?.size)return;n.forEach((s,a)=>{const n=(e?.turnSectionAttrs??[]).map(t=>`section[${t}="${a}"]`),o=r.getFirstElementBasedOnSelectors(n,t);o&&(o.innerHTML=s)})}catch{}})(e.element,n,a,o),{targetSectionId:a}}return null},window.overrideHTMLForConvertHTMLToPDFOp=async(s,r)=>{const{targetSectionId:a}=r??{},{default:n}=await import(chrome.runtime.getURL("content_scripts/chatgpt/state.js")),[o,i]=await Promise.all([t,e]);((t,e,s)=>{if(!e?.layoutFixCSS||!t.head)return;const r=t.createElement("style");r.textContent=e.layoutFixCSS,t.head.appendChild(r);const a=(e.searchOverlayRootClasses??[]).map(t=>`[class*="${t}"]`);(s.getElementsListBasedOnSelectors(a,t)??[]).forEach(t=>{const s=[...t.children].find(t=>"DIV"===t.tagName),r=(e.turnContainerAttrs??[]).some(t=>s?.hasAttribute(t));s&&!r&&s.remove()}),s.getFirstElementBasedOnSelectors(e.headerSelectors??[],t)?.remove();const n=(e.turnContainerAttrs??[]).map(t=>`[${t}]`);(s.getElementsListBasedOnSelectors(n,t)??[]).forEach(t=>{(e.heightLockClasses??[]).forEach(e=>t.classList.remove(e)),Object.entries(e.heightLockResetProperties??{}).forEach(([e,s])=>{t.style.setProperty(e,s,"important")}),(e.heightLockCssVars??[]).forEach(e=>t.style.removeProperty(e)),(e.intersectingAttrs??[]).forEach(e=>t.setAttribute(e,"true"))}),t.querySelectorAll("img").forEach(t=>{t.removeAttribute("loading"),t.removeAttribute("decoding")})})(s,o,i),a&&n.capturedMissingMessages.has(a)&&n.capturedMissingMessages.delete(a)}})();