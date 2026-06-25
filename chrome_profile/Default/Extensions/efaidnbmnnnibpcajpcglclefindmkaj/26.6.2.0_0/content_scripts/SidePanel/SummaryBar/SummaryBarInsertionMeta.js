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
!function(){const e=window.SummaryBarConfig.manager.fgMetaStorageKey;function t(e){return e?String(e).toLowerCase().replace(/^www\./,""):""}function n(e,n){const r=e?.siteInsertion;if(!r||"object"!=typeof r)return null;const o=t(n);if(!o)return null;const c=r[o];if(c?.selector)return c;const u=Object.keys(r).find(e=>{const n=r[e];return n?.selector&&function(e,t){return!(!e||!t)&&(e===t||e.endsWith(`.${t}`))}(o,t(e))});return u?r[u]:null}function r(e){const t=String(e||"").trim();if(!t)return null;const n=t.includes("::prepend")||t.includes("::before"),r=t.replace("::prepend","").replace("::before","").trim();return!r||/[<>'"]/u.test(r)?null:{query:r,insertBefore:n}}function o(e){let t;try{t=document.querySelector(e.query)}catch{return null}const n=t?.parentElement;return t&&n?{parent:n,before:e.insertBefore?t:t.nextElementSibling,preferArticleColumnWidth:!0}:null}function c(t){const c=n(function(){try{const t=window.dcLocalStorage?.getItem?.(e);if(!t||"string"!=typeof t)return{};const n=JSON.parse(t);return"object"==typeof n&&null!==n?n:{}}catch{return{}}}(),t);if(!c?.selector)return null;const u=r(c.selector);return u?o(u):null}window.SummaryBarInsertionMeta=Object.freeze({parseSelectorDirective:r,resolveSiteInsertionEntry:n,resolveInsertionFromDirective:o,resolveForHost:c,resolveForCurrentHost:function(){try{return c(window.location.hostname||"")}catch{return null}}})}();