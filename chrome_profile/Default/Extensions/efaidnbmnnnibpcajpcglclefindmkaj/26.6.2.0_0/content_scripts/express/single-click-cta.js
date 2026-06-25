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
import expressUtils from"./express-utils.js";class SingleClickCTA{ENTRY_POINT_DIV_WRAPPER_CLASS="cc440d50ba-express-entrypoint-wrapper";ENTRY_POINT_BUTTON_CLASS="cc440d50ba-express-entrypoint-button";ENTRY_POINT_BUTTON_ICON_IMG_CLASS="cc440d50ba-express-entrypoint-button-icon-img";constructor(){this.ready=this.init()}async init(){await fetch(chrome.runtime.getURL("resources/express/expressSingleClickCTA.html")).then(e=>e.text()).then(e=>{this.htmlData=e}),this.ExpressCTATooltip=(await import(chrome.runtime.getURL("content_scripts/express/express-cta-tooltip.js"))).default,await expressUtils.addFontToDocument()}async renderMenuButton(e,t,s={}){await this.ready,this.surface=t;const n=document.createElement("div");n.innerHTML=this.htmlData,n.className=`${t} ${this.ENTRY_POINT_DIV_WRAPPER_CLASS}`;const i=new URL(window.location.href).hostname,{mimeType:r}=s,o=n.getElementsByClassName(this.ENTRY_POINT_BUTTON_CLASS)[0],a=n=>{n.preventDefault(),n.stopPropagation();const o="editImage",a={frequency:"always"};expressUtils.sendAnalyticsEvent([["DCBrowserExt:Express:SingleCTA:VERB:Clicked",{domain:i,VERB:o,expressTouchpoint:t,eventContext:r},a]]),s.convertCTAEnabled&&expressUtils.sendAnalyticsEvent([["DCBrowserExt:Express:SingleCTA:VERB:Clicked:ConvertEnabled",{domain:i,VERB:o,expressTouchpoint:t,eventContext:r},a]]),e(o)};o.onclick=e=>a(e),o.addEventListener("keydown",e=>{"Enter"!==e.key&&" "!==e.key||a(e)});return o.getElementsByClassName(this.ENTRY_POINT_BUTTON_ICON_IMG_CLASS)[0].src=chrome.runtime.getURL("browser/images/acrobat_prodc_appicon_24.svg"),util.translateElements(".translate",n),n.setAttribute("aria-label",util.getTranslation("expressEditImageParentContextMenu")),this.button=o,n}attachTooltip(e,t=null){const s=new this.ExpressCTATooltip({button:this.button,tooltipPosition:e,surface:this.surface});return s.addTooltipToDOM(t),s}}export default SingleClickCTA;