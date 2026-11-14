const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["./SearchPage-XUcAySrQ.js","./i18n-D5ETJ7Y9.js","./LibraryPage-DFSKy9t_.js","./LibraryPage-P0f-mg77.css","./PlaylistsPage-2TXqQdyp.js","./PlaylistsPage-BJuM2ezv.css","./StatsPage-Btbb_zgF.js","./StatsPage-Dd3vWThI.css","./CachePage-J40hb-wo.js","./SettingsPage-DWYOPYUV.js","./SettingsPage-B9pc6JS1.css"])))=>i.map(i=>d[i]);
import{$t as e,At as t,B as n,Bt as r,Dt as i,E as a,Et as o,Ft as s,Gt as c,Ht as l,I as u,It as d,J as f,Jt as p,Kt as m,Mt as h,N as g,Nt as _,Ot as v,P as y,Pt as b,Qt as x,R as S,Rt as C,St as w,Tt as T,U as E,Ut as D,Vt as O,Wt as ee,X as te,Xt as ne,Y as k,Yt as A,Zt as j,_t as M,a as re,an as N,b as ie,d as ae,dt as oe,en as P,f as se,ft as F,g as I,gt as ce,h as le,ht as ue,i as de,in as L,jt as R,k as z,kt as B,l as V,mt as fe,n as pe,nn as me,nt as he,o as H,on as U,p as ge,pt as _e,qt as ve,r as ye,rn as W,s as be,st as xe,t as Se,tn as Ce,tt as we,u as Te,ut as Ee,vt as G,wt as De,y as Oe,yt as ke,z as Ae,zt as je}from"./i18n-D5ETJ7Y9.js";(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),t.credentials=e.crossOrigin===`use-credentials`?`include`:e.crossOrigin===`anonymous`?`omit`:`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var Me=3e3,Ne=P(null),Pe=P(null),Fe=e({playhead:0}),Ie=!1,Le=0,Re=P(0);function ze(e){Ne.value=e,Le=performance.now(),Re.value=Le,Fe.playhead=Ue(e.playhead),Pe.value=null}async function Be(){let e=G.value;try{let t=await Ae();e===G.value&&ze(t)}catch(t){e===G.value&&(Pe.value=t instanceof Error?t.message:String(t))}}A(G,()=>{Ne.value=null,Pe.value=null,Fe.playhead=0,Ie&&Be()});var Ve=.25,He=0;function Ue(e){return Math.floor(e/Ve)*Ve}function We(){let e=Ne.value;return!!e&&e.play&&!e.empty&&!e.prep}function Ge(){He=0;let e=Ne.value;if(!e||!We())return;let t=(performance.now()-Le)/1e3,n=e.current?.duration||0,r=e.playhead+t,i=Ue(n>0?Math.min(r,n):r);i!==Fe.playhead&&(Fe.playhead=i),He=requestAnimationFrame(Ge)}function Ke(){!He&&We()&&(He=requestAnimationFrame(Ge))}A(()=>We(),Ke);function qe(){let e=Ne.value;return e?.prep||e?.current?.download?1e3:Me}var Je,Ye=!1;async function Xe(){if(clearTimeout(Je),Je=void 0,!Ye){Ye=!0;try{await Be()}finally{Ye=!1}document.visibilityState!==`hidden`&&(Je=setTimeout(Xe,qe()))}}function Ze(){document.visibilityState===`hidden`?(clearTimeout(Je),Je=void 0):Je||Xe()}function Qe(){Ie||(Ie=!0,document.addEventListener(`visibilitychange`,Ze),Xe())}async function $e(e){let t=G.value;try{let n=await f(e);t===G.value&&ze(n)}catch(e){Pe.value=e instanceof Error?e.message:String(e)}}function et(){return Qe(),{status:Ne,error:Pe,clock:Fe,progress:o(()=>{let e=Ne.value?.current?.duration||0;return e?Math.min(1,Fe.playhead/e):0}),syncedAt:Re,refresh:Be,control:$e,applyStatus:ze}}function tt(e){(!Number.isFinite(e)||e<0)&&(e=0);let t=Math.floor(e),n=Math.floor(t/3600),r=Math.floor(t%3600/60),i=t%60,a=n>0?String(r).padStart(2,`0`):String(r),o=String(i).padStart(2,`0`);return n>0?`${n}:${a}:${o}`:`${a}:${o}`}var nt={class:`flex w-full max-w-xl flex-col items-center gap-5`},rt={class:`flex items-center gap-4`},it=[`title`,`aria-label`],at=[`title`,`aria-label`],ot={class:`flex w-full max-w-xs items-center gap-3`},st=[`aria-label`,`aria-valuetext`],ct={class:`w-8 text-right text-xs tabular-nums`,style:{color:`var(--c-text-muted)`},"aria-hidden":`true`},lt=[`aria-label`],ut=[`aria-checked`,`tabindex`,`onClick`,`onKeydown`],dt=b({__name:`Controls`,setup(e){let{status:n,control:r}=et(),a=P(.5),s=!1;A(()=>n.value?.volume,e=>{e!==void 0&&!s&&(a.value=e)},{immediate:!0});let u;function d(){s=!0,clearTimeout(u),u=setTimeout(()=>{r({action:`volume`,volume:a.value}),s=!1},150)}function f(){n.value&&r({action:n.value.play?`pause`:`resume`})}let p=[`one-shot`,`repeat`,`single`,`random`,`autoplay`],m=[],g=o(()=>Math.max(0,p.indexOf(n.value?.mode??``)));function _(e,t){let n={ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1}[e.key],i;if(n!==void 0)i=(t+n+p.length)%p.length;else if(e.key===`Home`)i=0;else if(e.key===`End`)i=p.length-1;else return;e.preventDefault(),m[i]?.focus(),r({action:`mode`,mode:p[i]})}return(e,o)=>{let s=c(`Icon`);return l(),t(`div`,nt,[i(`div`,rt,[i(`button`,{class:`flex h-14 w-14 cursor-pointer items-center justify-center rounded-full border-0`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`,boxShadow:`var(--shadow-1)`},title:W(n)?.play?W(H)(`ctl.pause`):W(H)(`ctl.play`),"aria-label":W(n)?.play?W(H)(`ctl.pause`):W(H)(`ctl.play`),onClick:f},[h(s,{icon:W(n)?.play?`pause`:`play`,class:L([`text-xl`,{"translate-x-px":!W(n)?.play}])},null,8,[`icon`,`class`])],8,it),i(`button`,{class:`flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border-0`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(H)(`ctl.skip`),"aria-label":W(H)(`ctl.skip`),onClick:o[0]||=e=>W(r)({action:`skip`})},[h(s,{icon:`forward-step`,class:`text-lg`})],8,at)]),i(`div`,ot,[h(s,{icon:`volume-low`,class:`shrink-0 text-sm`,style:{color:`var(--c-text-muted)`}}),ne(i(`input`,{"onUpdate:modelValue":o[1]||=e=>a.value=e,type:`range`,min:`0`,max:`1`,step:`0.01`,class:`volume-slider w-full`,"aria-label":W(H)(`ctl.volume`),"aria-valuetext":`${Math.round(a.value*100)}%`,onInput:d},null,40,st),[[w,a.value,void 0,{number:!0}]]),i(`span`,ct,U(Math.round(a.value*100)),1)]),i(`div`,{class:`flex max-w-full gap-1 overflow-x-auto rounded-full p-1`,style:{background:`var(--c-surface-2)`},role:`radiogroup`,"aria-label":W(H)(`ctl.mode`)},[(l(),t(T,null,ee(p,(e,t)=>i(`button`,{key:e,ref_for:!0,ref:e=>{m[t]=e},type:`button`,class:`mode-btn min-h-6 shrink-0 cursor-pointer rounded-full border-0 px-2 py-1 text-xs font-medium whitespace-nowrap capitalize pointer-coarse:min-h-11 sm:px-3`,style:N(W(n)?.mode===e?{background:`var(--c-accent)`,color:`var(--c-on-accent)`}:{background:`transparent`,color:`var(--c-text-muted)`}),role:`radio`,"aria-checked":W(n)?.mode===e,tabindex:t===g.value?0:-1,onClick:t=>W(r)({action:`mode`,mode:e}),onKeydown:e=>_(e,t)},U(W(ye)(e)),45,ut)),64))],8,lt)])}}}),ft=(e,t)=>{let n=e.__vccOpts||e;for(let[e,r]of t)n[e]=r;return n},pt=ft(dt,[[`__scopeId`,`data-v-78b8ffd5`]]),mt=300,ht=new Map;function gt(e,t){let n=ht.get(e);if(n)return ht.delete(e),ht.set(e,n),n;let r=I(e,t?{priority:t}:{}).then(async e=>e.ok?URL.createObjectURL(await e.blob()):null).catch(()=>null);for(ht.set(e,r),r.then(t=>{t===null&&ht.get(e)===r&&ht.delete(e)});ht.size>mt;){let[e,t]=ht.entries().next().value;ht.delete(e),t.then(e=>{e&&URL.revokeObjectURL(e)})}return r}var _t=[`src`],vt=b({__name:`AuthImg`,props:{src:{}},setup(e){let n=e,i=ve(),a=P(null),o=P(_e?void 0:fe(n.src)||void 0),s=!_e||i.loading!==`lazy`,c=null,u=``;async function d(){let e=fe(n.src);if(!_e||!e||e.startsWith(`data:`)||e.startsWith(`blob:`)){o.value=e||void 0;return}if(!s)return;u=e;let t=i.fetchpriority,r=await gt(e,t===`high`||t===`low`?t:void 0);u===e&&(o.value=r??`data:,`)}return A(()=>n.src,()=>{d()}),O(()=>{!s&&a.value&&`IntersectionObserver`in window?(c=new IntersectionObserver(e=>{e.some(e=>e.isIntersecting)&&(s=!0,c?.disconnect(),c=null,d())},{rootMargin:`200px`}),c.observe(a.value)):s=!0,d()}),r(()=>c?.disconnect()),(e,n)=>(l(),t(`img`,{ref_key:`el`,ref:a,src:o.value},null,8,_t))}}),yt=P(null),bt=P([]),xt=!1;async function St(){try{yt.value=await y()}catch{}}async function Ct(){if(!yt.value?.can_have_playlists)bt.value=[];else try{bt.value=await u()}catch{}}function wt(){return xt||(xt=!0,St().then(Ct)),{me:yt,playlists:bt,reloadMe:St,reloadPlaylists:Ct}}var Tt=P(new Set),Et=P(null),Dt=P(new Set),Ot=!1;async function kt(){try{let e=await a();Tt.value=new Set(e.item_ids),Et.value=e.playlist_id}catch{}}async function At(e,t){if(Dt.value.has(e))return!0;let n=!Tt.value.has(e);Dt.value=new Set(Dt.value).add(e);let r=new Set(Tt.value);n?r.add(e):r.delete(e),Tt.value=r;try{let e=await xe(t,n);return Tt.value=new Set(e.item_ids),Et.value=e.playlist_id,wt().reloadPlaylists(),!0}catch{return await kt(),!1}finally{let t=new Set(Dt.value);t.delete(e),Dt.value=t}}function jt(){if(!Ot){Ot=!0;let{me:e,reloadMe:t}=wt();(e.value?Promise.resolve():t()).then(()=>{e.value?.can_have_playlists&&kt()})}return{favoriteIds:Tt,favoritesPlaylistId:Et,favoriteBusy:Dt,reloadFavorites:kt,toggleFavorite:At}}var Mt={polite:250,assertive:50},Nt=1500,Pt=7e3,Ft={},It={polite:``,assertive:``},Lt={},Rt={},zt={polite:{text:``,at:0},assertive:{text:``,at:0}};function Bt(e){let t=document.createElement(`div`);return t.className=`visually-hidden`,e===`polite`?t.setAttribute(`role`,`status`):t.setAttribute(`aria-live`,`assertive`),t.setAttribute(`aria-atomic`,`true`),t.dataset.announcer=e,document.body.append(t),t}function Vt(){if(typeof document<`u`&&document.body)for(let e of[`polite`,`assertive`])Ft[e]?.isConnected||(Ft[e]=Bt(e))}function Ht(){try{return document.querySelector(`dialog:modal`)}catch{return document.querySelector(`dialog[open]`)}}function Ut(e){let t=It[e];if(It[e]=``,!t)return;let n=Ht();if(n){It[e]=t,n.addEventListener(`close`,()=>setTimeout(()=>Ut(e),100),{once:!0});return}let r=Date.now();if(zt[e].text===t&&r-zt[e].at<Nt)return;zt[e]={text:t,at:r};let i=document;if(typeof i.ariaNotify==`function`)try{i.ariaNotify(t,{priority:e===`assertive`?`high`:`normal`});return}catch{}Vt();let a=Ft[e];a&&(a.textContent=``,clearTimeout(Rt[e]),setTimeout(()=>{a.textContent=t,Rt[e]=setTimeout(()=>{a.textContent=``},Pt)},50))}function Wt(e,t={}){let n=e.trim();if(!n||typeof document>`u`)return;let r=t.assertive?`assertive`:`polite`;It[r]=n,clearTimeout(Lt[r]),Lt[r]=setTimeout(()=>Ut(r),Mt[r])}function Gt(){return{announce:Wt}}var Kt=[`title`,`aria-label`,`aria-expanded`,`aria-controls`],qt={key:0},Jt=[`id`],Yt={class:`px-2 pt-1 pb-1.5 text-[11px] font-semibold uppercase tracking-wider`,style:{color:`var(--c-text-faint)`}},Xt={role:`list`,class:`max-h-56 overflow-y-auto overscroll-contain`},Zt=[`onClick`],Qt={class:`flex min-w-0 items-center gap-1.5`},$t={class:`truncate`},en={class:`shrink-0 text-xs tabular-nums`,style:{color:`var(--c-text-faint)`}},tn=[`placeholder`,`aria-label`],nn={type:`submit`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs font-semibold`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`}},rn={key:2,class:`px-2 pt-1 pb-0.5 text-xs`,style:{color:`var(--c-text-muted)`}},an=null,on=b({__name:`AddToPlaylist`,props:{source:{},label:{default:``},itemTitle:{default:``}},setup(e){let n=e,{me:a,playlists:s,reloadPlaylists:u}=wt(),{reloadFavorites:d}=jt(),f=P(!1),m=P(!1),g=P(``),_=P(``),y=P(!1),b=P(null),x=P(null),S=P(null),C=P(null),E=p(),D=P(!1),O=P(0),te,k=o(()=>{if(!n.label)return n.itemTitle?H(`common.itemAction`,{action:H(`atp.title`),title:n.itemTitle}):H(`atp.title`)}),j=()=>M();function M(e=!1){clearTimeout(te),f.value&&(e&&x.value?.focus(),f.value=!1,m.value=!1,an===j&&(an=null))}function re(){D.value=!1,O.value=0,je(()=>{let e=S.value,t=b.value;if(!e||!t)return;let n=e.getBoundingClientRect(),r=t.getBoundingClientRect(),i=document.documentElement.clientWidth;n.left<8?O.value=8-n.left:n.right>i-8&&(O.value=i-8-n.right),n.bottom>window.innerHeight-8&&r.top>window.innerHeight-r.bottom&&(D.value=!0)})}function ae(){f.value?M():(an&&an!==j&&an(),an=j,f.value=!0,_.value=``,y.value=!1,m.value=!1,u(),re())}function oe(){m.value=!0,je(()=>C.value?.focus())}async function se(e){clearTimeout(te),_.value=`...`,y.value=!1;try{let t=await le(e,n.source),r=s.value.find(t=>t.id===e)?.favorites?H(`fav.name`):t.playlist.name;_.value=H(t.added?`atp.added`:`atp.already`,{name:r}),y.value=!!t.added,Wt(_.value),t.added&&d(),u(),te=setTimeout(()=>{let e=document.activeElement;M(!e||e===document.body||!!b.value?.contains(e))},900)}catch{y.value=!1,_.value=H(`atp.failed`),Wt(_.value,{assertive:!0})}}async function F(){let e=g.value.trim();if(e)try{let t=await ie(e);g.value=``,m.value=!1,await se(t.id)}catch{y.value=!1,_.value=H(`atp.createFailed`),Wt(_.value,{assertive:!0})}}function I(e){e.key!==`Escape`||!f.value||e.defaultPrevented||e.isComposing||e.keyCode===229||(e.preventDefault(),M(!!b.value?.contains(document.activeElement)))}function ce(e){let t=e.relatedTarget;f.value&&t&&!b.value?.contains(t)&&M()}function ue(e){f.value&&b.value&&!b.value.contains(e.target)&&M()}return A(f,e=>{e?(document.addEventListener(`click`,ue,!0),document.addEventListener(`keydown`,I)):(document.removeEventListener(`click`,ue,!0),document.removeEventListener(`keydown`,I))}),r(()=>{document.removeEventListener(`click`,ue,!0),document.removeEventListener(`keydown`,I),clearTimeout(te),an===j&&(an=null)}),(e,r)=>{let o=c(`Icon`);return W(a)?.can_have_playlists?(l(),t(`div`,{key:0,ref_key:`root`,ref:b,class:`relative inline-flex`,onFocusout:ce},[i(`button`,{ref_key:`trigger`,ref:x,type:`button`,class:`inline-flex cursor-pointer items-center gap-1 rounded-md border-0 px-2 py-1 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(H)(`atp.title`),"aria-label":k.value,"aria-expanded":f.value,"aria-controls":f.value?W(E):void 0,onClick:ae},[h(o,{icon:`list-ul`}),n.label?(l(),t(`span`,qt,U(n.label),1)):B(``,!0)],8,Kt),f.value?(l(),t(`div`,{key:0,id:W(E),ref_key:`panel`,ref:S,class:L([`absolute right-0 z-30 w-56 max-w-[calc(100vw-2rem)] rounded-xl p-1.5 text-left text-sm`,D.value?`bottom-full mb-1`:`top-full mt-1`]),style:N({background:`var(--c-surface)`,boxShadow:`var(--shadow-2)`,border:`1px solid var(--c-border)`,transform:O.value?`translateX(${O.value}px)`:void 0})},[i(`p`,Yt,U(W(H)(`atp.header`)),1),i(`ul`,Xt,[(l(!0),t(T,null,ee(W(s),e=>(l(),t(`li`,{key:e.id},[i(`button`,{type:`button`,class:`flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg border-0 bg-transparent px-2 py-1.5 text-left text-sm hover:opacity-80`,style:{color:`var(--c-text)`},onClick:t=>se(e.id)},[i(`span`,Qt,[e.favorites?(l(),v(o,{key:0,icon:`heart`,class:`shrink-0`,style:{color:`var(--c-danger)`}})):B(``,!0),i(`span`,$t,U(e.favorites?W(H)(`fav.name`):e.name),1)]),i(`span`,en,U(e.count),1)],8,Zt)]))),128))]),m.value?(l(),t(`form`,{key:0,class:`flex gap-1 p-1`,onSubmit:De(F,[`prevent`])},[ne(i(`input`,{ref_key:`nameInput`,ref:C,"onUpdate:modelValue":r[0]||=e=>g.value=e,maxlength:`60`,placeholder:W(H)(`atp.name`),"aria-label":W(H)(`atp.name`),class:`min-w-0 flex-1 rounded-md border px-2 py-1 text-xs`,style:{background:`var(--c-bg)`,borderColor:`var(--c-border)`,color:`var(--c-text)`}},null,8,tn),[[w,g.value]]),i(`button`,nn,U(W(H)(`atp.add`)),1)],32)):(l(),t(`button`,{key:1,type:`button`,class:`w-full cursor-pointer rounded-lg border-0 bg-transparent px-2 py-1.5 text-left text-sm`,style:{color:`var(--c-accent)`},onClick:oe},[h(o,{icon:`plus`,class:`mr-1`}),R(U(W(H)(`atp.new`)),1)])),_.value?(l(),t(`p`,rn,[y.value?(l(),v(o,{key:0,icon:`check`,class:`mr-1`,style:{color:`var(--c-success)`}})):B(``,!0),R(U(_.value),1)])):B(``,!0)],14,Jt)):B(``,!0)],544)):B(``,!0)}}}),sn=[`title`,`aria-label`,`aria-pressed`],cn={key:0},ln=b({__name:`FavButton`,props:{itemId:{},source:{},label:{default:``},itemTitle:{default:``}},setup(e){let n=e,{me:r}=wt(),{favoriteIds:i,toggleFavorite:a}=jt(),s=o(()=>!!n.itemId&&i.value.has(n.itemId)),u=P(!1),d=o(()=>{if(!n.label)return n.itemTitle?H(`common.itemAction`,{action:H(`fav.name`),title:n.itemTitle}):H(`fav.name`)});async function f(){n.itemId&&(u.value=!await a(n.itemId,n.source),u.value&&(Wt(H(`fav.failed`),{assertive:!0}),setTimeout(()=>u.value=!1,2500)))}return(e,i)=>{let a=c(`Icon`);return W(r)?.can_have_playlists&&n.itemId?(l(),t(`button`,{key:0,type:`button`,class:`inline-flex cursor-pointer items-center gap-1 rounded-md border-0 px-2 py-1 text-xs`,style:N({background:`var(--c-surface-2)`,color:s.value?`var(--c-danger)`:`var(--c-text)`}),title:u.value?W(H)(`fav.failed`):W(H)(s.value?`fav.remove`:`fav.add`),"aria-label":d.value,"aria-pressed":s.value,onClick:De(f,[`stop`])},[h(a,{icon:s.value?`heart`:[`far`,`heart`]},null,8,[`icon`]),n.label?(l(),t(`span`,cn,U(n.label),1)):B(``,!0)],12,sn)):B(``,!0)}}}),un={class:`w-full max-w-xl rounded-2xl p-4`,style:{background:`var(--c-surface)`,boxShadow:`var(--shadow-1)`}},dn={class:`flex items-baseline justify-between gap-2`},fn={class:`text-sm font-semibold`,style:{color:`var(--c-accent)`}},pn={class:`text-xs tabular-nums`,style:{color:`var(--c-text-muted)`}},mn={class:`mt-3 grid grid-cols-4 gap-1.5`,role:`list`},hn=[`aria-current`],gn={class:`mt-1 text-[11px]`,style:{color:`var(--c-text-faint)`}},_n={key:0,class:`mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs tabular-nums`,style:{color:`var(--c-text-muted)`}},vn={key:0},yn={key:1},bn={key:2},xn={key:3},Sn={key:1,class:`mt-2 text-[11px]`,style:{color:`var(--c-text-faint)`}},Cn={key:2,class:`mt-2 text-[11px]`,style:{color:`var(--c-text-faint)`}},wn=b({__name:`PrepPanel`,props:{prep:{},syncedAt:{}},setup(e){let a=e,s=P(performance.now()),u;function d(){s.value=performance.now(),u=setTimeout(d,p.value<10?250:1e3)}O(d),r(()=>clearTimeout(u));let f=o(()=>Math.max(0,(s.value-a.syncedAt)/1e3)),p=o(()=>a.prep.elapsed+f.value),m=o(()=>a.prep.eta===null?null:Math.max(0,a.prep.eta-f.value)),h=[{key:`info`,label:`prep.info`,hint:`prep.infoHint`},{key:`connect`,label:`prep.connect`,hint:`prep.connectHint`},{key:`buffer`,label:`prep.buffer`,hint:`prep.bufferHint`},{key:`play`,label:`prep.play`,hint:null}],g=o(()=>{switch(a.prep.stage){case`pending`:case`fetching_info`:return 0;case`starting`:return 1;case`downloading`:return 2;default:return 3}});A(g,e=>Wt(H(h[e].label)));let _=o(()=>{let e=a.prep;return e.stage===`downloading`?e.streaming&&e.target_secs>0?Math.min(100,e.buffered_secs/e.target_secs*100):Math.min(100,e.progress*100):0});function y(e){return e<10?H(`prep.secs`,{n:e.toFixed(1)}):e<90?H(`prep.secs`,{n:Math.round(e)}):H(`prep.minSecs`,{m:Math.floor(e/60),s:Math.round(e%60)})}let b=o(()=>a.prep.stage===`launching`||a.prep.stage===`ready`?H(`prep.startingNow`):m.value===null?H(`prep.estimating`):m.value<.5?H(`prep.anyMoment`):H(`prep.startsIn`,{eta:`${a.prep.eta_estimated?`~`:``}${y(m.value)}`}));return(r,a)=>{let o=c(`Icon`);return l(),t(`div`,un,[i(`div`,dn,[i(`p`,fn,U(b.value),1),i(`p`,pn,U(W(H)(`prep.waiting`,{t:y(p.value)})),1)]),i(`ol`,mn,[(l(),t(T,null,ee(h,(e,t)=>i(`li`,{key:e.key,class:`min-w-0`,"aria-current":t===g.value?`step`:void 0},[i(`div`,C({class:`h-1.5 overflow-hidden rounded-full`,style:{background:`var(--c-surface-2)`}},{ref_for:!0},t===2&&g.value===2?{role:`progressbar`,"aria-label":W(H)(`prep.buffer`),"aria-valuemin":0,"aria-valuemax":100,"aria-valuenow":Math.round(_.value)}:{"aria-hidden":`true`}),[i(`div`,{class:L([`h-full rounded-full`,t===g.value&&t<3?`motion-safe:animate-pulse`:``]),style:N({width:t<g.value?`100%`:t===g.value?t===2?`${Math.max(_.value,6)}%`:`100%`:`0%`,background:(g.value,`var(--c-accent)`),opacity:t<g.value?.55:1,transition:`width 400ms ease`})},null,6)],16),i(`p`,{class:`mt-1 truncate text-[11px]`,style:N({color:t===g.value?`var(--c-text)`:`var(--c-text-faint)`,fontWeight:t===g.value?600:400})},[t<g.value?(l(),v(o,{key:0,icon:`check`,class:`mr-1`})):B(``,!0),R(U(W(H)(e.label)),1)],4)],8,hn)),64))]),i(`p`,gn,[R(U(h[g.value]?.hint?W(H)(h[g.value].hint):``),1),e.prep.stage_elapsed>0&&g.value<3?(l(),t(T,{key:0},[R(` · `+U(y(e.prep.stage_elapsed+f.value)),1)],64)):B(``,!0)]),e.prep.stage===`downloading`?(l(),t(`div`,_n,[e.prep.streaming?(l(),t(`span`,vn,U(W(H)(`prep.buffered`,{have:Math.floor(e.prep.buffered_secs),need:Math.ceil(e.prep.target_secs)})),1)):(l(),t(`span`,yn,U(W(H)(`prep.downloaded`,{pct:Math.round(e.prep.progress*100)})),1)),e.prep.speed?(l(),t(`span`,bn,U(W(n)(e.prep.speed))+`/s`,1)):B(``,!0),e.prep.total?(l(),t(`span`,xn,U(W(n)(e.prep.downloaded))+` / `+U(W(n)(e.prep.total)),1)):B(``,!0)])):B(``,!0),e.prep.streaming&&g.value>=1?(l(),t(`p`,Sn,U(W(H)(`prep.streamingHint`,{n:Math.ceil(e.prep.target_secs)})),1)):!e.prep.streaming&&e.prep.stage===`downloading`?(l(),t(`p`,Cn,U(W(H)(`prep.wholeFileHint`)),1)):B(``,!0)])}}}),Tn=[`aria-label`],En={class:`mb-2 flex items-center gap-2 text-xs`,style:{color:`var(--c-text-muted)`}},Dn=[`aria-expanded`],On={key:0,class:`truncate`,style:{color:`var(--c-text-faint)`}},kn={key:1,class:`ml-auto flex items-center gap-1 pointer-coarse:gap-2`},An={key:0,class:`tabular-nums`,style:{color:`var(--c-text-faint)`}},jn=[`title`,`aria-label`],Mn=[`title`,`aria-label`],Nn={key:0,class:`lyr-note`},Pn={key:1,class:`lyr-note`},Fn={key:2,class:`lyr-note`},In={key:0,class:`mb-2 text-[11px]`,style:{color:`var(--c-text-faint)`}},Ln={class:`lyr-wrap`},Rn=[`tabindex`],zn={key:0,class:`h-28`,"aria-hidden":`true`},Bn=[`data-line`],Vn=[`tabindex`,`onClick`,`onKeydown`],Hn={key:0},Un={key:1,"aria-hidden":`true`},Wn={key:2,class:`lyr-trans`},Gn={key:0},Kn={key:1,"aria-hidden":`true`},qn={key:2,class:`lyr-trans`},Jn={key:2,class:`whitespace-pre-line text-sm leading-7`,style:{color:`var(--c-text)`}},Yn={key:3,class:`h-28`,"aria-hidden":`true`},Xn=null,Zn=ft(b({__name:`LyricsPanel`,props:{current:{},previewAt:{},canSeek:{type:Boolean}},emits:[`seek`],setup(e,{emit:n}){let a=e,s=n,{clock:u}=et(),d=`lyricsHidden`,f=P(Te(d)===`1`);function p(){f.value=!f.value,se(d,f.value?`1`:`0`)}let m=P(null),_=P(``);A(()=>[a.current.id,a.current.lyrics],async([e,t])=>{if(_.value!==e&&(m.value=null,_.value=``),!(t!==`found`&&t!==`instrumental`||_.value===e)){Xn?.id===e&&(m.value=Xn.data,_.value=e);try{let t=await g(e);if(a.current.id!==e)return;m.value=t,_.value=e,Xn={id:e,data:t}}catch{}}},{immediate:!0});let v=o(()=>m.value?.lines??[]),y=P(0);A(()=>m.value?.offset,e=>{y.value=e??0},{immediate:!0});let b=o(()=>v.value.length>0&&(!!m.value?.aligned||y.value!==(m.value?.offset??0))),x=o(()=>a.canSeek&&b.value),S=o(()=>{if(!b.value)return-1;let e=(a.previewAt??u.playhead)-y.value+.2,t=v.value,n=0,r=t.length-1,i=-1;for(;n<=r;){let a=n+r>>1;t[a][0]<=e?(i=a,n=a+1):r=a-1}return i}),C=P(null),w=0;function E(){w=performance.now()}let D=typeof matchMedia==`function`&&matchMedia(`(prefers-reduced-motion: reduce)`).matches;function O(e){let t=C.value?.querySelector(`[data-line="${S.value}"]`);C.value&&t&&C.value.scrollTo({top:t.offsetTop-C.value.clientHeight/2+t.clientHeight/2,behavior:e&&!D?`smooth`:`auto`})}function te(){try{return!!C.value?.querySelector(`:focus-visible`)}catch{return!1}}A(S,()=>{performance.now()-w<4e3||te()||je(()=>O(!0))}),A([f,m],()=>je(()=>O(!1)));function ne(e){x.value&&s(`seek`,Math.max(0,e+y.value))}let j=o(()=>Math.max(0,S.value));function M(e,t){let n=v.value.length-1,r;if(e.key===`ArrowDown`)r=Math.min(n,t+1);else if(e.key===`ArrowUp`)r=Math.max(0,t-1);else if(e.key===`Home`)r=0;else if(e.key===`End`)r=n;else return;e.preventDefault(),C.value?.querySelector(`[data-line="${r}"] > .lyr-seek`)?.focus()}let re;function N(e){y.value=Math.round((y.value+e)*10)/10,ae()}function ie(){y.value=0,ae()}function ae(){clearTimeout(re);let e=a.current.id,t=y.value;re=setTimeout(async()=>{try{let n=await k(e,t);Xn={id:e,data:n},a.current.id===e&&(m.value=n)}catch{}},600)}r(()=>clearTimeout(re));let oe=o(()=>{let e=y.value;return H(`lyrics.offset`,{s:`${e>0?`+`:``}${e.toFixed(1)}`})}),F=o(()=>{let e=m.value?.source;return e===`netease`?H(`lyrics.netease`):e===`lrclib`?`LRCLIB`:e||``}),I=o(()=>a.current.lyrics??`off`);return(e,n)=>{let r=c(`Icon`);return I.value!==`off`&&I.value!==``?(l(),t(`section`,{key:0,class:`w-full max-w-xl`,"aria-label":W(H)(`lyrics.title`)},[i(`div`,En,[i(`button`,{type:`button`,class:`lyr-toggle flex min-h-6 cursor-pointer items-center gap-1.5 rounded-md border-0 bg-transparent px-1 py-0.5 text-xs font-medium`,style:{color:`var(--c-text-muted)`},"aria-expanded":!f.value,onClick:p},[h(r,{icon:`chevron-down`,class:L([`transition-transform motion-reduce:transition-none`,f.value?`-rotate-90`:``])},null,8,[`class`]),R(` `+U(W(H)(`lyrics.title`)),1)],8,Dn),F.value&&!f.value?(l(),t(`span`,On,U(W(H)(`lyrics.source`,{source:F.value})),1)):B(``,!0),!f.value&&v.value.length?(l(),t(`div`,kn,[y.value===0?B(``,!0):(l(),t(`span`,An,U(oe.value),1)),i(`button`,{type:`button`,class:`lyr-btn`,title:W(H)(`lyrics.earlier`),"aria-label":W(H)(`common.itemAction`,{action:`−0.5s`,title:W(H)(`lyrics.earlier`)}),onClick:n[0]||=e=>N(-.5)},`−0.5s`,8,jn),i(`button`,{type:`button`,class:`lyr-btn`,title:W(H)(`lyrics.later`),"aria-label":W(H)(`common.itemAction`,{action:`+0.5s`,title:W(H)(`lyrics.later`)}),onClick:n[1]||=e=>N(.5)},`+0.5s`,8,Mn),y.value===0?B(``,!0):(l(),t(`button`,{key:1,type:`button`,class:`lyr-btn`,onClick:ie},U(W(H)(`lyrics.reset`)),1))])):B(``,!0)]),f.value?B(``,!0):(l(),t(T,{key:0},[I.value===`waiting`||I.value===`pending`||I.value===`found`&&!m.value?(l(),t(`p`,Nn,U(W(H)(I.value===`waiting`?`lyrics.waiting`:`lyrics.pending`)),1)):I.value===`none`?(l(),t(`p`,Pn,U(W(H)(`lyrics.none`)),1)):I.value===`instrumental`?(l(),t(`p`,Fn,U(W(H)(`lyrics.instrumental`)),1)):m.value?(l(),t(T,{key:3},[v.value.length&&!b.value?(l(),t(`p`,In,U(W(H)(`lyrics.unaligned`)),1)):B(``,!0),i(`div`,Ln,[i(`div`,{ref_key:`box`,ref:C,class:L([`lyr-box relative h-72 overflow-y-auto px-2 text-center`,{"lyr-box--follow":b.value}]),tabindex:x.value?void 0:0,onWheelPassive:E,onTouchmovePassive:E,onKeydown:E},[b.value?(l(),t(`div`,zn)):B(``,!0),v.value.length?(l(!0),t(T,{key:1},ee(v.value,(e,n)=>(l(),t(`p`,{key:n,"data-line":n,class:L([`lyr-line`,{"lyr-line--active":n===S.value,"lyr-line--past":b.value&&n<S.value}])},[x.value?(l(),t(`button`,{key:0,type:`button`,class:`lyr-seek`,tabindex:n===j.value?0:-1,onClick:t=>ne(e[0]),onKeydown:e=>M(e,n)},[e[1]?(l(),t(`span`,Hn,U(e[1]),1)):(l(),t(`span`,Un,`♪`)),e[2]?(l(),t(`span`,Wn,U(e[2]),1)):B(``,!0)],40,Vn)):(l(),t(T,{key:1},[e[1]?(l(),t(`span`,Gn,U(e[1]),1)):(l(),t(`span`,Kn,`♪`)),e[2]?(l(),t(`span`,qn,U(e[2]),1)):B(``,!0)],64))],10,Bn))),128)):(l(),t(`p`,Jn,U(m.value.plain),1)),b.value?(l(),t(`div`,Yn)):B(``,!0)],42,Rn)])],64)):B(``,!0)],64))],8,Tn)):B(``,!0)}}}),[[`__scopeId`,`data-v-8d25b064`]]),Qn={class:`mx-auto flex w-full max-w-3xl flex-col items-center gap-6 px-4 py-8 sm:py-14`},$n={key:0,class:`w-full rounded-xl px-3 py-2 text-sm`,style:{background:`var(--c-accent-soft)`,color:`var(--c-text)`}},er={class:`relative aspect-square w-56 overflow-hidden sm:w-72`,style:{borderRadius:`var(--radius-l)`,boxShadow:`var(--shadow-2)`}},tr={key:1,class:`flex h-full w-full items-center justify-center`,style:{background:`linear-gradient(135deg, var(--c-accent-soft), var(--c-surface-2))`}},nr={class:`flex w-full flex-col items-center gap-1 text-center`},rr={class:`max-w-full text-xl font-semibold text-balance sm:text-2xl`,style:{color:`var(--c-text-muted)`}},ir={class:`max-w-full truncate text-xs`,style:{color:`var(--c-text-faint)`}},ar=[`title`],or={class:`flex items-center gap-2 text-sm`,style:{color:`var(--c-text-muted)`}},sr={class:`rounded-full px-2 py-0.5 text-xs font-medium`,style:{background:`var(--c-accent-soft)`,color:`var(--c-accent)`}},cr={key:0},lr=[`title`],ur=[`title`],dr={class:`text-xl font-semibold sm:text-2xl`,style:{color:`var(--c-text-muted)`}},fr={class:`text-sm`,style:{color:`var(--c-text-faint)`}},pr={key:2,class:`w-full max-w-xl`},mr=[`title`],hr=[`max`,`value`,`aria-label`,`aria-valuetext`],gr={class:`mt-1.5 flex justify-between text-xs tabular-nums`,style:{color:`var(--c-text-muted)`}},_r={key:0,class:`mt-1 text-center text-[11px] tabular-nums`,style:{color:`var(--c-text-faint)`}},vr={key:1,class:`mt-1 text-center text-[11px]`,style:{color:`var(--c-text-faint)`}},yr={key:4,class:`text-sm`,style:{color:`var(--c-text-muted)`}},br={key:0,style:{color:`var(--c-accent)`}},xr={key:5,class:`rounded-md px-3 py-2 text-sm`,style:{background:`var(--c-accent-soft)`,color:`var(--c-danger)`}},Sr=ft(b({__name:`NowPlaying`,setup(e){let{status:r,error:a,clock:s,syncedAt:u,applyStatus:d}=et(),p=o(()=>r.value?.current??null),m=P(null),g=P(``);A(()=>[p.value?.id,p.value?.has_thumbnail,p.value?.artwork],([e,t,n])=>{m.value=e&&t?Ee(e,{version:n||`pending`}):null,g.value=n||``},{immediate:!0});let _=o(()=>p.value?.duration||0),y=o(()=>_.value>0),b=P(null),x=P(null),S=P(null),C=P(0),w=o(()=>x.value??s.playhead),E=o(()=>_.value?Math.min(1,Math.max(0,w.value/_.value)):0);function D(e){let t=b.value.getBoundingClientRect();return Math.min(1,Math.max(0,(e.clientX-t.left)/t.width))*_.value}function O(e){y.value&&e.button===0&&(b.value.setPointerCapture(e.pointerId),x.value=D(e),e.preventDefault())}function te(e){y.value&&(x.value!==null&&b.value.hasPointerCapture(e.pointerId)?x.value=D(e):S.value=D(e))}function ne(e){if(x.value===null||!b.value.hasPointerCapture(e.pointerId))return;let t=x.value;ce(t)}function k(){x.value=null}function j(e){return Math.min(Math.max(0,_.value-1),Math.max(0,e))}let M;function re(e){x.value=e,clearTimeout(M),M=setTimeout(()=>x.value!==null&&ce(x.value),400)}function ie(e){if(!y.value)return;let t={ArrowLeft:-5,ArrowDown:-5,ArrowRight:5,ArrowUp:5,PageDown:-30,PageUp:30}[e.key],n;if(e.key===`Home`)n=0;else if(e.key===`End`)n=_.value-1;else if(t!==void 0)n=(x.value??s.playhead)+t;else return;e.preventDefault(),re(j(n))}let ae=P(!1),oe=P(0),se=o(()=>Math.round(x.value??(ae.value?oe.value:s.playhead)));function F(){oe.value=s.playhead,ae.value=!0}function I(e){let t=e.target,n=Number(t.value)-se.value;if(!n)return;let r=j((x.value??s.playhead)+(Math.abs(n)<5?Math.sign(n)*5:n));re(r),t.value=String(Math.round(r))}async function ce(e){clearTimeout(M),C.value=performance.now(),s.playhead=e,oe.value=e;try{d(await f({action:`seek`,position:e}))}catch{}finally{x.value=null}}let le=o(()=>!p.value||!r.value?.prep?!1:!C.value||performance.now()-C.value>4e3);A(()=>r.value?.prep,e=>{e||(C.value=0)}),A(()=>p.value?.id,()=>{x.value=null,C.value=0});let ue=o(()=>!!r.value?.prep&&/^https?:\/\//.test(p.value?.title??``)),de=o(()=>{let e=p.value?.duration||0;return e?(p.value?.skip_segments??[]).map(([t,n])=>({start:t,end:n,left:t/e*100,width:(Math.min(n,e)-t)/e*100})):[]}),z=o(()=>p.value?.track||p.value?.title||``),fe=o(()=>{let e=p.value?.album?.trim().toLowerCase();return!!e&&e!==z.value.trim().toLowerCase()}),pe=o(()=>V(p.value?.type??``)),me=o(()=>!!r.value&&!r.value.voice_channel);return A(me,e=>{e&&Wt(H(`np.notInVoice`))}),A(a,e=>{e&&Wt(H(`np.unreachable`,{error:e}),{assertive:!0})}),(e,o)=>{let s=c(`Icon`);return l(),t(`section`,Qn,[me.value?(l(),t(`p`,$n,[h(s,{icon:`triangle-exclamation`,class:`mr-1.5`,style:{color:`var(--c-accent)`}}),R(U(W(H)(`np.notInVoice`)),1)])):B(``,!0),i(`div`,er,[m.value?(l(),t(T,{key:0},[g.value===`video`?(l(),v(vt,{key:0,src:m.value,alt:``,"aria-hidden":`true`,class:`absolute inset-0 h-full w-full scale-125 object-cover opacity-80 blur-2xl`},null,8,[`src`])):B(``,!0),h(vt,{src:m.value,alt:``,fetchpriority:`high`,class:L([`relative h-full w-full transition-[filter] duration-500`,[g.value===`video`?`object-contain`:`object-cover`,g.value?``:`scale-110 blur-xl`]])},null,8,[`src`,`class`])],64)):(l(),t(`div`,tr,[h(s,{icon:`music`,class:`text-7xl opacity-40`,"aria-hidden":`true`})]))]),i(`div`,nr,[p.value?(l(),t(T,{key:0},[ue.value?(l(),t(T,{key:0},[i(`h1`,rr,U(W(H)(`np.loadingTitle`)),1),i(`p`,ir,U(p.value.title),1)],64)):(l(),t(`h1`,{key:1,class:`line-clamp-2 max-w-full text-xl font-semibold text-balance [overflow-wrap:anywhere] sm:text-2xl`,title:p.value.title},U(z.value||W(H)(`common.untitled`)),9,ar)),i(`p`,or,[i(`span`,sr,U(pe.value),1),p.value.artist&&p.value.artist!==`??`?(l(),t(`span`,cr,U(p.value.artist),1)):B(``,!0),fe.value?(l(),t(`span`,{key:1,class:`hidden max-w-48 truncate sm:inline`,title:p.value.album},`· `+U(p.value.album),9,lr)):B(``,!0),p.value.requester?(l(),t(`span`,{key:2,class:`max-w-40 truncate text-xs`,style:{color:`var(--c-text-faint)`},title:W(H)(`queue.requestedBy`,{name:p.value.requester})},[h(s,{icon:`user`,class:`mr-1`}),R(U(p.value.requester),1)],8,ur)):B(``,!0),h(ln,{"item-id":p.value.id,source:{source:`library`,item_id:p.value.id},label:W(H)(`np.save`)},null,8,[`item-id`,`source`,`label`]),h(on,{source:{source:`current`},label:W(H)(`atp.header`)},null,8,[`label`])])],64)):(l(),t(T,{key:1},[i(`h1`,dr,U(W(H)(`np.nothing`)),1),i(`p`,fr,U(W(H)(`np.emptyHint`)),1)],64))]),le.value&&W(r)?.prep?(l(),v(wn,{key:1,prep:W(r).prep,"synced-at":W(u)},null,8,[`prep`,`synced-at`])):p.value?(l(),t(`div`,pr,[i(`div`,{ref_key:`bar`,ref:b,class:L([`seek-bar group relative flex h-6 w-full items-center pointer-coarse:-my-2.5 pointer-coarse:h-11`,y.value?`cursor-pointer touch-pan-y`:``]),onPointerdown:O,onPointermove:te,onPointerup:ne,onPointercancel:k,onPointerleave:o[1]||=e=>S.value=null},[i(`div`,{class:L([`relative h-1.5 w-full overflow-hidden rounded-full transition-[height] duration-150 group-has-[:focus-visible]:h-2`,y.value?`group-hover:h-2`:``]),style:{background:`var(--c-surface-2)`}},[p.value.download?(l(),t(`div`,{key:0,class:`absolute inset-y-0 left-0 rounded-full`,style:N({width:`${p.value.download.progress*100}%`,background:`var(--c-accent-soft)`,transition:`width 800ms linear`})},null,4)):B(``,!0),i(`div`,{class:`absolute inset-0 rounded-full`,style:N({transform:`translateX(${(E.value-1)*100}%)`,background:`var(--c-accent)`,transition:x.value===null?`transform 250ms linear`:`none`})},null,4),(l(!0),t(T,null,ee(de.value,(e,n)=>(l(),t(`div`,{key:n,class:`absolute inset-y-0`,style:N({left:`${e.left}%`,width:`${e.width}%`,background:`repeating-linear-gradient(135deg, var(--c-decor) 0 3px, transparent 3px 6px)`,opacity:.7}),title:W(H)(`np.skipped`,{from:W(tt)(e.start),to:W(tt)(e.end)})},null,12,mr))),128))],2),y.value?(l(),t(`div`,{key:0,class:L([`pointer-events-none absolute top-1/2 left-0 h-3.5 w-3.5 rounded-full opacity-0 group-hover:opacity-100 group-has-[:focus-visible]:opacity-100`,x.value===null?``:`opacity-100`]),style:N({transform:`translate(calc(${E.value} * 100cqi - 50%), -50%)`,transition:x.value===null?`opacity 150ms, transform 250ms linear`:`opacity 150ms`,background:`var(--c-accent)`,boxShadow:`var(--shadow-2)`})},null,6)):B(``,!0),y.value?(l(),t(`input`,{key:1,type:`range`,class:`seek-input`,min:`0`,max:Math.max(1,Math.round(_.value)),step:`1`,value:se.value,"aria-label":W(H)(`np.seek`),"aria-valuetext":W(H)(`np.seekValue`,{at:W(tt)(se.value),total:W(tt)(_.value)}),onFocus:F,onBlur:o[0]||=e=>ae.value=!1,onKeydown:ie,onInput:I},null,40,hr)):B(``,!0),y.value&&(x.value??S.value)!==null?(l(),t(`div`,{key:2,class:`pointer-events-none absolute -top-6 -translate-x-1/2 rounded px-1.5 py-0.5 text-[11px] tabular-nums`,style:N({left:`${(x.value??S.value)/_.value*100}%`,background:`var(--c-surface-2)`,color:`var(--c-text)`,boxShadow:`var(--shadow-2)`}),"aria-hidden":`true`},U(W(tt)(x.value??S.value)),5)):B(``,!0)],34),i(`div`,gr,[i(`span`,null,U(W(tt)(w.value)),1),i(`span`,null,U(p.value.duration?W(tt)(p.value.duration):`--:--`),1)]),p.value.download?(l(),t(`p`,_r,[h(s,{icon:`download`,class:`mr-1`}),R(U(W(H)(`np.bgDownload`,{pct:Math.round(p.value.download.progress*100)})),1),p.value.download.speed?(l(),t(T,{key:0},[R(` · `+U(W(n)(p.value.download.speed))+`/s`,1)],64)):B(``,!0),p.value.download.eta?(l(),t(T,{key:1},[R(` · `+U(W(H)(`np.bgDone`,{eta:W(tt)(p.value.download.eta)})),1)],64)):B(``,!0)])):B(``,!0),de.value.length?(l(),t(`p`,vr,[h(s,{icon:`forward-step`,class:`mr-1`}),R(U(W(H)(`np.skipping`,{n:de.value.length})),1)])):B(``,!0)])):B(``,!0),h(pt),p.value?(l(),v(Zn,{key:3,current:p.value,"preview-at":x.value,"can-seek":y.value,onSeek:ce},null,8,[`current`,`preview-at`,`can-seek`])):B(``,!0),W(r)&&!W(r).empty?(l(),t(`p`,yr,[R(U(W(H)(`np.summary`,{n:W(r).queue_length,mode:W(ye)(W(r).mode)}))+` `,1),W(r).play?B(``,!0):(l(),t(`span`,br,` · `+U(W(H)(`np.paused`)),1))])):B(``,!0),W(a)?(l(),t(`p`,xr,U(W(H)(`np.unreachable`,{error:W(a)})),1)):B(``,!0)])}}}),[[`__scopeId`,`data-v-69357938`]]),Cr={class:`mx-auto w-full max-w-3xl px-4 py-8`},wr={class:`rounded-2xl p-5 text-center`,style:{background:`var(--c-surface)`,boxShadow:`var(--shadow-1)`}},Tr={class:`text-sm`},Er={class:`mt-4 flex flex-wrap justify-center gap-2`},Dr=Symbol(`retryView`),Or=b({__name:`ViewLoadError`,props:{error:{}},setup(e){let n=()=>location.reload(),r=d(Dr,n);return O(()=>Wt(H(`nav.loadFailed`),{assertive:!0})),(e,a)=>{let o=c(`Icon`);return l(),t(`section`,Cr,[i(`div`,wr,[i(`p`,Tr,[h(o,{icon:`triangle-exclamation`,class:`mr-1.5`,"aria-hidden":`true`,style:{color:`var(--c-danger)`}}),R(U(W(H)(`nav.loadFailed`)),1)]),i(`div`,Er,[i(`button`,{type:`button`,class:`cursor-pointer rounded-full border-0 px-4 py-2 text-xs font-semibold`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`},onClick:a[0]||=(...e)=>W(r)&&W(r)(...e)},U(W(H)(`common.retry`)),1),i(`button`,{type:`button`,class:`cursor-pointer rounded-full border-0 px-4 py-2 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},onClick:n},U(W(H)(`nav.reload`)),1)])])])}}});function kr(e,t){let n,r=!1,i=!1,a=()=>document.visibilityState===`hidden`;function o(){clearTimeout(n),n=void 0}function s(){o(),r&&!a()&&(n=setTimeout(c,typeof t==`function`?t():t))}async function c(){if(n=void 0,r&&!i){i=!0;try{await e()}catch{}finally{i=!1}s()}}function l(){r&&(a()?o():!n&&!i&&c())}function u(e=!1){r||(r=!0,document.addEventListener(`visibilitychange`,l)),e?(o(),c()):!n&&!i&&s()}function d(){r=!1,o(),document.removeEventListener(`visibilitychange`,l)}return j()&&x(d),{start:u,stop:d}}var Ar=[`aria-current`],jr={class:`h-10 w-10 shrink-0 overflow-hidden rounded-lg`,style:{background:`var(--c-surface-2)`}},Mr={key:1,class:`flex h-full w-full items-center justify-center opacity-40`},Nr={class:`min-w-0 flex-1`},Pr=[`title`],Fr={class:`truncate text-xs`,style:{color:`var(--c-text-muted)`}},Ir={key:0},Lr=[`title`],Rr={key:2,style:{color:`var(--c-accent)`}},zr={class:`flex shrink-0 items-center gap-1 transition-opacity [@media(hover:hover)]:opacity-80 group-hover:opacity-100 group-focus-within:opacity-100 has-[[aria-expanded=true]]:opacity-100 @max-[36rem]:basis-full @max-[36rem]:justify-end`},Br=[`title`,`aria-label`,`disabled`],Vr=[`title`,`aria-label`,`disabled`],Hr=[`title`,`aria-label`],Ur=[`title`,`aria-label`],Wr=[`title`,`aria-label`],Gr=b({__name:`QueueRow`,props:{item:{},index:{},isNext:{type:Boolean},isLast:{type:Boolean},dragOver:{type:Boolean},dragging:{type:Boolean},nested:{type:Boolean}},emits:[`act`,`move`],setup(e,{emit:n}){let r=e,a=n,s=o(()=>r.item.title||H(`common.untitled`)),u=e=>H(`common.itemAction`,{action:e,title:s.value});return(e,n)=>{let o=c(`Icon`);return l(),t(`li`,{class:`group flex cursor-grab items-center gap-3 rounded-xl px-3 py-2 active:cursor-grabbing @max-[36rem]:flex-wrap`,style:N({...r.item.is_current?{background:`var(--c-accent-soft)`}:r.nested?{background:`var(--c-surface)`}:{background:`var(--c-surface)`,boxShadow:`var(--shadow-1)`},...r.dragOver?{outline:`2px solid var(--c-accent)`,outlineOffset:`-2px`}:{},...r.dragging?{opacity:.4}:{}}),"aria-current":r.item.is_current?`true`:void 0,draggable:`true`},[h(o,{icon:`grip-vertical`,class:`shrink-0 select-none text-xs`,style:{color:`var(--c-decor)`},"aria-hidden":`true`}),i(`div`,jr,[r.item.has_thumbnail?(l(),v(vt,{key:0,src:W(Ee)(r.item.id,{small:!0}),alt:``,class:`h-full w-full object-cover`,loading:`lazy`},null,8,[`src`])):(l(),t(`div`,Mr,[h(o,{icon:`music`})]))]),i(`div`,Nr,[i(`p`,{class:`truncate text-sm font-medium`,title:r.item.title},[r.item.is_current?(l(),v(o,{key:0,icon:`caret-right`,class:`mr-1`,style:{color:`var(--c-accent)`}})):B(``,!0),R(U(s.value),1)],8,Pr),i(`p`,Fr,[R(U(W(V)(r.item.type)),1),r.item.duration?(l(),t(`span`,Ir,` · `+U(W(tt)(r.item.duration)),1)):B(``,!0),r.item.requester&&!r.nested?(l(),t(`span`,{key:1,title:W(H)(`queue.requestedBy`,{name:r.item.requester})},[n[5]||=R(` · `,-1),h(o,{icon:`user`,class:`text-[10px]`}),R(` `+U(r.item.requester),1)],8,Lr)):B(``,!0),r.item.download&&!r.item.is_current?(l(),t(`span`,Rr,[n[6]||=R(` · `,-1),h(o,{icon:`download`}),R(` `+U(r.item.download.stage===`downloading`?`${Math.round(r.item.download.progress*100)}%`:W(H)(`queue.preparing`)),1)])):B(``,!0)])]),i(`div`,zr,[i(`button`,{type:`button`,"data-move":`up`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs disabled:cursor-default`,style:N({background:`var(--c-surface-2)`,color:r.index===0?`var(--c-decor)`:`var(--c-text)`}),title:W(H)(`queue.moveUp`),"aria-label":u(W(H)(`queue.moveUp`)),disabled:r.index===0,onClick:n[0]||=e=>a(`move`,`up`)},[h(o,{icon:`angle-left`,rotation:`90`})],12,Br),i(`button`,{type:`button`,"data-move":`down`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs disabled:cursor-default`,style:N({background:`var(--c-surface-2)`,color:r.isLast?`var(--c-decor)`:`var(--c-text)`}),title:W(H)(`queue.moveDown`),"aria-label":u(W(H)(`queue.moveDown`)),disabled:r.isLast,onClick:n[1]||=e=>a(`move`,`down`)},[h(o,{icon:`angle-right`,rotation:`90`})],12,Vr),r.item.is_current?B(``,!0):(l(),t(`button`,{key:0,type:`button`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(H)(`common.playNow`),"aria-label":u(W(H)(`common.playNow`)),onClick:n[2]||=e=>a(`act`,{action:`play`,index:r.index})},[h(o,{icon:`play`})],8,Hr)),!r.item.is_current&&!r.isNext?(l(),t(`button`,{key:1,type:`button`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(H)(`common.playNext`),"aria-label":u(W(H)(`common.playNext`)),onClick:n[3]||=e=>a(`act`,{action:`top`,index:r.index})},[h(o,{icon:`arrow-turn-up`})],8,Ur)):B(``,!0),h(ln,{"item-id":r.item.id,"item-title":s.value,source:{source:`library`,item_id:r.item.id}},null,8,[`item-id`,`item-title`,`source`]),h(on,{source:{source:`queue`,index:r.index},"item-title":s.value},null,8,[`source`,`item-title`]),i(`button`,{type:`button`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-danger)`},title:W(H)(`common.remove`),"aria-label":u(W(H)(`common.remove`)),onClick:n[4]||=e=>a(`act`,{action:`remove`,index:r.index})},[h(o,{icon:`xmark`})],8,Wr)])],12,Ar)}}}),Kr={key:0,class:`mx-auto w-full max-w-3xl px-4 pb-12`},qr={class:`mb-3 flex items-center justify-between`},Jr={class:`text-sm font-semibold uppercase tracking-wider`,style:{color:`var(--c-text-muted)`}},Yr={class:`flex items-center gap-1.5`},Xr=[`aria-current`],Zr={class:`group flex items-center gap-3 px-3 py-2.5`},Qr=[`aria-expanded`,`onClick`],$r={class:`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg`,style:{background:`var(--c-surface-2)`,color:`var(--c-accent)`}},ei={class:`block min-w-0 flex-1`},ti={class:`flex min-w-0 items-center gap-2 text-sm font-medium`},ni=[`title`],ri={class:`shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium`,style:{background:`var(--c-surface-2)`,color:`var(--c-text-muted)`}},ii={class:`block truncate text-xs`,style:{color:`var(--c-text-muted)`}},ai=[`title`],oi={class:`flex shrink-0 items-center gap-1 transition-opacity [@media(hover:hover)]:opacity-80 group-hover:opacity-100 group-focus-within:opacity-100`},si=[`title`,`aria-label`,`onClick`],ci=[`title`,`aria-label`,`onClick`],li={key:0,role:`list`,class:`@container flex flex-col gap-1 px-2 pb-2`},ui={key:0},di=[`onClick`],K=P([]),fi=P(new Set),pi=P(new Set),mi,hi=b({__name:`QueueList`,setup(e){let{status:n,applyStatus:r}=et(),a=P(!1),s=P(null),u=P(null),d=P(null),f=o(()=>{let e=new Map;return K.value.map(t=>{let n=e.get(t.id)??0;return e.set(t.id,n+1),`${t.id}#${n}`})}),p=o(()=>{let e=[],t=K.value,n=f.value,r=new Map,i=0;for(;i<t.length;){let a=t[i],o=a.group?.key,s=i+1;if(o)for(;s<t.length&&t[s].group?.key===o;)s++;if(o&&s-i>1){let c=t.slice(i,s).map((e,t)=>({item:e,index:i+t,key:n[i+t]})),l=r.get(o)??0;r.set(o,l+1),e.push({kind:`group`,key:`g-${o}#${l}`,group:a.group,members:c,currentPos:c.findIndex(e=>e.item.is_current),duration:c.reduce((e,t)=>e+(t.item.duration||0),0)})}else for(let r=i;r<s;r++)e.push({kind:`item`,key:n[r],member:{item:t[r],index:r,key:n[r]}});i=s}return e});function m(e,t){let n=new Set(e);return n.has(t)?n.delete(t):n.add(t),n}let g=e=>fi.value=m(fi.value,e),_=e=>pi.value=m(pi.value,e);function y(e){if(pi.value.has(e.group.key)||e.members.length<=100)return e.members;let t=e.currentPos>50?e.currentPos-10:0;return e.members.slice(t,t+100)}let b=o(()=>(n.value?.current_index??-1)+1);function x(e,t){s.value=e,t.dataTransfer&&(t.dataTransfer.effectAllowed=`move`,t.dataTransfer.setData(`text/plain`,String(e)))}function C(e,t){t.preventDefault(),u.value=e,t.dataTransfer&&(t.dataTransfer.dropEffect=`move`)}async function w(e){let t=s.value;s.value=null,u.value=null,t!==null&&t!==e&&await E(t,e)}async function E(e,t){if(a.value||t<0||t>=K.value.length||e===t)return!1;let n=K.value[e].title||H(`common.untitled`),r=K.value.splice(e,1)[0];K.value.splice(t,0,r);let i=await j({action:`move`,index:e,to:t});return i&&Wt(H(`queue.moved`,{title:n,n:t+1})),i}async function D(e,t){let n=t===`up`?e-1:e+1,r=f.value[e];if(r===void 0)return;let i=async(i,a=!0)=>{await je();let o=document.activeElement;if(i&&o&&o!==document.body)return;let s=(a?f.value[n]:f.value[e])??r,c=d.value?.querySelector(`[data-key="${CSS.escape(s)}"]`),l=c?.querySelector(`[data-move="${t}"]:not(:disabled)`)??c?.querySelector(`[data-move]:not(:disabled)`);c&&l&&(c.scrollIntoView({block:`nearest`,inline:`nearest`}),o!==l&&l.focus({preventScroll:!0}))};if(a.value||n<0||n>=K.value.length)return;let o=E(e,n);await i(!1),await i(!0,await o)}function O(){s.value=null,u.value=null}async function ne(e=!1){let t=G.value;try{let n=await S({background:e});if(t!==G.value)return;K.value=n.items,mi=t}catch{}}function k(){K.value=[],fi.value=new Set,pi.value=new Set,mi=void 0}mi!==G.value&&k(),A(G,k),A([G,()=>n.value?.version],()=>ne(),{immediate:!0}),kr(()=>ne(!0),()=>K.value.some(e=>e.download)?3e3:1e4).start();async function j(e){if(a.value)return!1;a.value=!0;try{return r(await te(e)),await ne(),!0}catch{return await ne(),!1}finally{a.value=!1}}return(e,n)=>{let r=c(`Icon`);return K.value.length?(l(),t(`section`,Kr,[i(`div`,qr,[i(`h2`,Jr,U(W(H)(`queue.title`,{n:K.value.length})),1),i(`div`,Yr,[h(on,{source:{source:`all_queue`},label:W(H)(`queue.save`)},null,8,[`label`]),i(`button`,{type:`button`,class:`cursor-pointer rounded-full border-0 px-3 py-1 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-text-muted)`},onClick:n[0]||=e=>j({action:`clear`})},U(W(H)(`queue.clear`)),1)])]),i(`ul`,{ref_key:`listEl`,ref:d,role:`list`,class:`@container flex flex-col gap-1.5`},[(l(!0),t(T,null,ee(p.value,e=>(l(),t(T,{key:e.key},[e.kind===`item`?(l(),v(Gr,{key:0,"data-key":e.key,item:e.member.item,index:e.member.index,"is-next":e.member.index===b.value,"is-last":e.member.index===K.value.length-1,"drag-over":u.value===e.member.index&&s.value!==null&&s.value!==e.member.index,dragging:s.value===e.member.index,onAct:j,onMove:t=>D(e.member.index,t),onDragstart:t=>x(e.member.index,t),onDragover:t=>C(e.member.index,t),onDrop:De(t=>w(e.member.index),[`prevent`]),onDragend:O},null,8,[`data-key`,`item`,`index`,`is-next`,`is-last`,`drag-over`,`dragging`,`onMove`,`onDragstart`,`onDragover`,`onDrop`])):(l(),t(`li`,{key:1,class:`rounded-xl`,style:N({background:e.currentPos>=0?`var(--c-accent-soft)`:`var(--c-surface)`,boxShadow:`var(--shadow-1)`}),"aria-current":e.currentPos>=0&&!fi.value.has(e.group.key)?`true`:void 0},[i(`div`,Zr,[i(`button`,{type:`button`,class:`flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-lg border-0 bg-transparent p-0 text-left`,style:{color:`inherit`},"aria-expanded":fi.value.has(e.group.key),onClick:t=>g(e.group.key)},[h(r,{icon:fi.value.has(e.group.key)?`chevron-down`:`chevron-right`,class:`w-3 shrink-0 text-xs`,style:{color:`var(--c-text-faint)`}},null,8,[`icon`]),i(`span`,$r,[h(r,{icon:e.group.kind===`url_playlist`?`globe`:`list-ul`},null,8,[`icon`])]),i(`span`,ei,[i(`span`,ti,[i(`span`,{class:`truncate`,title:e.group.name},U(e.group.name||W(H)(`common.untitled`)),9,ni),i(`span`,ri,U(W(H)(e.group.kind===`url_playlist`?`queue.groupKindOnline`:`queue.groupKindPlaylist`)),1)]),i(`span`,ii,[e.currentPos>=0?(l(),t(T,{key:0},[h(r,{icon:`caret-right`,class:`mr-1`,style:{color:`var(--c-accent)`}}),R(U(W(H)(`queue.groupNow`,{i:e.currentPos+1,n:e.members.length,title:e.members[e.currentPos].item.title||W(H)(`common.untitled`)})),1)],64)):(l(),t(T,{key:1},[R(U(W(H)(`queue.groupSongs`,{n:e.members.length,time:W(tt)(e.duration)})),1)],64)),e.members[0].item.requester?(l(),t(`span`,{key:2,title:W(H)(`queue.requestedBy`,{name:e.members[0].item.requester})},[n[1]||=R(` · `,-1),h(r,{icon:`user`,class:`text-[10px]`}),R(` `+U(e.members[0].item.requester),1)],8,ai)):B(``,!0)])])],8,Qr),i(`div`,oi,[e.currentPos===0?B(``,!0):(l(),t(`button`,{key:0,type:`button`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(H)(`queue.groupPlay`),"aria-label":W(H)(`common.itemAction`,{action:W(H)(`queue.groupPlay`),title:e.group.name||W(H)(`common.untitled`)}),onClick:t=>j({action:`play`,index:e.members[0].index})},[h(r,{icon:`play`})],8,si)),i(`button`,{type:`button`,class:`cursor-pointer rounded-md border-0 px-2 py-1 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-danger)`},title:W(H)(`queue.groupRemove`),"aria-label":W(H)(`common.itemAction`,{action:W(H)(`queue.groupRemove`),title:e.group.name||W(H)(`common.untitled`)}),onClick:t=>j({action:`remove_group`,group:e.group.key})},[h(r,{icon:`xmark`})],8,ci)])]),fi.value.has(e.group.key)?(l(),t(`ul`,li,[(l(!0),t(T,null,ee(y(e),e=>(l(),v(Gr,{key:e.key,"data-key":e.key,nested:``,item:e.item,index:e.index,"is-next":e.index===b.value,"is-last":e.index===K.value.length-1,"drag-over":u.value===e.index&&s.value!==null&&s.value!==e.index,dragging:s.value===e.index,onAct:j,onMove:t=>D(e.index,t),onDragstart:t=>x(e.index,t),onDragover:t=>C(e.index,t),onDrop:De(t=>w(e.index),[`prevent`]),onDragend:O},null,8,[`data-key`,`item`,`index`,`is-next`,`is-last`,`drag-over`,`dragging`,`onMove`,`onDragstart`,`onDragover`,`onDrop`]))),128)),y(e).length<e.members.length?(l(),t(`li`,ui,[i(`button`,{type:`button`,class:`w-full cursor-pointer rounded-lg border-0 bg-transparent py-1.5 text-xs`,style:{color:`var(--c-accent)`},onClick:t=>_(e.group.key)},U(W(H)(`queue.showAll`,{n:e.members.length})),9,di)])):B(``,!0)])):B(``,!0)],12,Xr))],64))),128))],512)])):B(``,!0)}}}),gi=me(null),_i=0,vi=0;function yi(){return _i++,()=>{_i--}}function bi(e){try{return window.confirm(e)}catch{return!1}}function xi(e){let t=typeof e==`string`?{message:e}:e;return _i===0?Promise.resolve(bi(t.message)):(gi.value?.resolve(!1),new Promise(e=>{let n=!1,r={...t,id:++vi,resolve:t=>{n||(n=!0,gi.value===r&&(gi.value=null),e(t))}};gi.value=r}))}function Si(){return{confirm:xi}}var Ci=P([]),wi=P(!1),Ti=P(!1),Ei=P(!1),Di=!1;async function Oi(){try{let e=await z();Ci.value=e.guilds,wi.value=e.owner,Ti.value=e.multi;let t=e.guilds.map(e=>e.id);t.includes(G.value)||(G.value=e.guilds.find(e=>e.selected)?.id??t[0]??``)}catch{}finally{Ei.value=!0}}function ki(e){e!==G.value&&(G.value=e)}var Ai=o(()=>Ci.value.find(e=>e.id===G.value)??null),ji=o(()=>!!Ai.value?.can_manage),Mi=o(()=>Ei.value&&Ti.value&&Ci.value.length===0);function Ni(){return Di||(Di=!0,Oi()),{guilds:Ci,owner:wi,multi:Ti,loaded:Ei,selectedGuild:G,currentGuild:Ai,canManage:ji,noAccess:Mi,reloadGuilds:Oi,selectGuild:ki}}var Pi=[`id`,`title`,`aria-expanded`,`aria-controls`],Fi={class:`truncate`},Ii=[`id`,`aria-labelledby`],Li={class:`text-xs`,style:{color:`var(--c-text-muted)`}},Ri=[`title`],zi={class:`mt-0.5 text-[11px]`,style:{color:`var(--c-text-faint)`}},Bi=[`for`],Vi=[`id`],Hi=[`id`,`placeholder`,`aria-invalid`,`aria-describedby`],Ui=[`aria-disabled`],Wi={class:`mt-2 flex items-center justify-between`},Gi=[`id`],Ki={class:`mt-4 border-t pt-3`,style:{borderColor:`var(--c-border)`}},qi={class:`text-xs font-medium`,style:{color:`var(--c-text-muted)`}},Ji={class:`mt-1 flex items-center justify-between`},Yi={class:`text-sm`},Xi={class:`mt-1 text-[11px]`,style:{color:`var(--c-text-faint)`}},Zi={key:0},Qi={class:`mt-1 text-[11px]`,style:{color:`var(--c-text-faint)`}},$i=[`title`],ea={class:`font-sans text-[11px]`,style:{color:`var(--c-text-faint)`}},ta={class:`mt-1 text-[11px]`,style:{color:`var(--c-text-faint)`}},na={class:`font-medium`},ra={class:`mt-1 text-xs leading-relaxed`,style:{color:`var(--c-text-muted)`}},ia=[`href`],aa=16,oa=b({__name:`UserChip`,setup(e){let{me:n}=wt(),{announce:a}=Gt(),{confirm:s}=Si(),u=P(!1),d=P(``),f=P(!1),m=P(``),g=P(!1),_=P(!1),b=P(null),x=P(null),S=P(null),C=P(null),D=P(null),te=P(null),k=p(),A={trigger:`${k}-trigger`,panel:`${k}-panel`,alias:`${k}-alias`,hint:`${k}-hint`,msg:`${k}-msg`},{reloadGuilds:j}=Ni(),M=o(()=>(n.value?.display_name||`?`).trim().charAt(0).toUpperCase()),re=o(()=>!!n.value?.identity),ie=o(()=>n.value?.source===`discord`),ae=o(()=>!_e&&n.value?.discord_login_available&&!ie.value?`${ge}?next=${encodeURIComponent(location.pathname+location.search)}`:null);async function se(){try{await E()}catch{}location.href=`../auth/logout`}let F=P({});function I(){let e=b.value;if(!e)return;let t=e.getBoundingClientRect(),n=document.documentElement.clientWidth,r=Math.min(288,n-32),i=Math.min(0,t.right-r-aa);F.value={width:`${r}px`,right:`${i}px`,maxHeight:`${Math.max(160,window.innerHeight-t.bottom-8-aa)}px`}}function ce(){u.value=!0,d.value=n.value?.alias??``,m.value=``,_.value=!1,I(),window.addEventListener(`resize`,I)}function le(e=!1){u.value&&(e&&x.value?.focus(),u.value=!1,window.removeEventListener(`resize`,I))}function ue(){u.value?le():ce()}function de(e){je(()=>{let t=document.activeElement;u.value&&(!t||t===document.body)&&e()?.focus()})}async function L(e){if(!f.value){f.value=!0,m.value=``;try{n.value=await he(e.trim()),m.value=H(e.trim()?`me.saved`:`me.cleared`),g.value=!0,_.value=!1,d.value=n.value.alias,a(m.value),de(()=>S.value)}catch(e){let t=e instanceof Error?e.message:``;m.value=H(t===`taken`?`me.taken`:t===`invalid`?`me.invalid`:`common.saveFailed`),g.value=!1,_.value=t===`taken`||t===`invalid`,a(m.value,{assertive:!0})}finally{f.value=!1}}}let z=P(null),V=P(``),fe=P(!1),pe=P(!1);function me(e,t,n=!1){V.value=e,fe.value=t,a(e,{assertive:n})}async function ve(){if(!z.value||Date.now()/1e3>z.value.expires_at)ye.stop(),z.value&&me(H(`me.codeExpired`),!1),z.value=null,de(()=>D.value);else try{let e=await y();e.discord&&(n.value=e,z.value=null,me(H(`me.linked`,{name:e.discord.discord_name}),!0),ye.stop(),de(()=>te.value),j())}catch{}}let ye=kr(ve,3e3);async function xe(){V.value=``,fe.value=!1;try{z.value=await Oe(),de(()=>C.value),ye.start()}catch{me(H(`me.codeFailed`),!1,!0)}}async function Se(){if(z.value)try{await navigator.clipboard.writeText(z.value.command),pe.value=!0,a(H(`me.copied`)),setTimeout(()=>pe.value=!1,1500)}catch{}}async function Ce(){if(await s({message:H(`me.confirmUnlink`),confirmLabel:H(`me.unlink`),destructive:!0})){try{n.value=await oe()}catch{me(H(`common.failed`),!1,!0);return}me(H(`me.unlinked`),!1),de(()=>D.value),j()}}function we(e){return e instanceof Element&&!!e.closest(`dialog`)}function Te(e){u.value&&b.value&&!we(e.target)&&(b.value.contains(e.target)||le())}function Ee(e){e.key!==`Escape`||!u.value||e.defaultPrevented||we(e.target)||le(!!b.value?.contains(document.activeElement))}function G(e){let t=e.relatedTarget;u.value&&t instanceof Node&&!we(t)&&b.value&&!b.value.contains(t)&&le()}O(()=>{document.addEventListener(`click`,Te,!0),document.addEventListener(`keydown`,Ee)}),r(()=>{document.removeEventListener(`click`,Te,!0),document.removeEventListener(`keydown`,Ee),window.removeEventListener(`resize`,I)});let ke={discord:`me.src.discord`,cloudflare:`me.src.cloudflare`,"cloudflare-jwt":`me.src.cloudflareJwt`,"web-user":`me.src.webUser`,anonymous:`me.src.anonymous`};return(e,r)=>{let a=c(`Icon`);return l(),t(`div`,{ref_key:`root`,ref:b,class:`relative`,onFocusout:G},[i(`button`,{id:A.trigger,ref_key:`trigger`,ref:x,type:`button`,class:`flex h-9 max-w-[9rem] cursor-pointer items-center gap-2 rounded-full border-0 py-1 pr-3 pl-1 text-xs font-medium`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(n)?.email||W(H)(`me.whoami`),"aria-expanded":u.value,"aria-controls":u.value?A.panel:void 0,onClick:ue},[i(`span`,{class:`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold`,style:N(re.value?{background:`var(--c-accent)`,color:`var(--c-on-accent)`}:{background:`var(--c-border)`,color:`var(--c-text-muted)`}),"aria-hidden":`true`},U(re.value?M.value:`?`),5),i(`span`,Fi,U(re.value?W(n)?.display_name:W(H)(`me.guest`)),1)],8,Pi),u.value?(l(),t(`div`,{key:0,id:A.panel,role:`group`,"aria-labelledby":A.trigger,class:`absolute top-full right-0 z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-2xl p-4 text-sm`,style:N({background:`var(--c-surface)`,boxShadow:`var(--shadow-2)`,border:`1px solid var(--c-border)`,...F.value})},[re.value?(l(),t(T,{key:0},[i(`p`,Li,U(W(H)(`me.signedInAs`)),1),i(`p`,{class:`truncate font-medium`,title:W(n)?.email||W(n)?.identity||``},U(W(n)?.email||W(n)?.identity),9,Ri),i(`p`,zi,U(W(H)(`me.via`,{source:W(H)(ke[W(n)?.source??`anonymous`]??`me.src.anonymous`)})),1),i(`label`,{class:`mt-4 block text-xs font-medium`,style:{color:`var(--c-text-muted)`},for:A.alias},U(W(H)(`me.displayName`)),9,Bi),i(`p`,{id:A.hint,class:`text-[11px]`,style:{color:`var(--c-text-faint)`}},U(W(H)(`me.displayNameHint`)),9,Vi),i(`form`,{class:`mt-2 flex gap-2`,onSubmit:r[1]||=De(e=>L(d.value),[`prevent`])},[ne(i(`input`,{id:A.alias,ref_key:`aliasInput`,ref:S,"onUpdate:modelValue":r[0]||=e=>d.value=e,maxlength:`24`,placeholder:W(n)?.email?.split(`@`)[0]??W(H)(`me.aliasPlaceholder`),class:`min-w-0 flex-1 rounded-lg border px-3 py-1.5 text-sm`,style:N({background:`var(--c-bg)`,borderColor:_.value?`var(--c-danger)`:`var(--c-border)`,color:`var(--c-text)`}),"aria-invalid":_.value?`true`:void 0,"aria-describedby":_.value?`${A.msg} ${A.hint}`:A.hint},null,12,Hi),[[w,d.value]]),i(`button`,{type:`submit`,class:`cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-semibold`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`},"aria-disabled":f.value?`true`:void 0},U(W(H)(`common.save`)),9,Ui)],32),i(`div`,Wi,[i(`span`,{id:A.msg,class:`text-xs`,style:N({color:g.value?`var(--c-success)`:`var(--c-danger)`})},[g.value?(l(),v(a,{key:0,icon:`check`,class:`mr-1`,"aria-hidden":`true`})):B(``,!0),R(U(m.value),1)],12,Gi),W(n)?.alias?(l(),t(`button`,{key:0,type:`button`,class:`cursor-pointer border-0 bg-transparent p-0 text-xs underline`,style:{color:`var(--c-text-muted)`},onClick:r[2]||=e=>L(``)},U(W(H)(`me.clear`)),1)):B(``,!0)]),i(`div`,Ki,[i(`p`,qi,U(W(H)(`me.discord`)),1),W(n)?.discord?(l(),t(T,{key:0},[i(`div`,Ji,[i(`span`,Yi,[h(a,{icon:`headphones`,class:`mr-1.5`,"aria-hidden":`true`,style:{color:`var(--c-accent)`}}),R(U(W(n).discord.discord_name),1)]),i(`button`,{ref_key:`unlinkBtn`,ref:te,type:`button`,class:`cursor-pointer border-0 bg-transparent p-0 text-xs underline`,style:{color:`var(--c-text-muted)`},onClick:Ce},U(W(H)(`me.unlink`)),513)]),i(`p`,Xi,[(l(!0),t(T,null,ee(W(be)(`me.discordHint`,{mylist:`/mylist`,fav:`/fav`}),(e,n)=>(l(),t(T,{key:n},[e.param?(l(),t(`b`,Zi,U(e.text),1)):(l(),t(T,{key:1},[R(U(e.text),1)],64))],64))),128))])],64)):z.value?(l(),t(T,{key:1},[i(`p`,Qi,U(W(H)(`me.sendThis`)),1),i(`button`,{ref_key:`copyBtn`,ref:C,type:`button`,class:`mt-1.5 flex w-full cursor-pointer items-center justify-between rounded-lg border-0 px-3 py-2 font-mono text-base tracking-wider`,style:{background:`var(--c-bg)`,color:`var(--c-text)`},title:W(H)(`me.copy`),onClick:Se},[R(U(z.value.command),1),i(`span`,ea,[pe.value?(l(),v(a,{key:0,icon:`check`,class:`mr-1`,"aria-hidden":`true`})):B(``,!0),R(U(W(H)(pe.value?`me.copied`:`me.copy`)),1)])],8,$i),i(`p`,ta,U(W(H)(`me.validFor`)),1)],64)):(l(),t(`button`,{key:2,ref_key:`linkBtn`,ref:D,type:`button`,class:`mt-1.5 w-full cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-medium`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},onClick:xe},U(W(H)(`me.link`)),513)),V.value?(l(),t(`p`,{key:3,class:`mt-1 text-xs`,style:N({color:fe.value?`var(--c-success)`:`var(--c-text-muted)`})},[fe.value?(l(),v(a,{key:0,icon:`check`,class:`mr-1`,"aria-hidden":`true`})):B(``,!0),R(U(V.value),1)],4)):B(``,!0)])],64)):(l(),t(T,{key:1},[i(`p`,na,U(W(H)(`me.guestTitle`)),1),i(`p`,ra,U(W(H)(`me.guestHint`)),1)],64)),ae.value?(l(),t(`a`,{key:2,href:ae.value,class:`mt-4 flex w-full items-center justify-center rounded-lg px-3 py-1.5 text-xs font-semibold no-underline`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`}},[h(a,{icon:`headphones`,class:`mr-1.5`,"aria-hidden":`true`}),R(U(W(H)(`me.loginDiscord`)),1)],8,ia)):B(``,!0),ie.value&&!W(_e)?(l(),t(`button`,{key:3,type:`button`,class:`mt-4 w-full cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-medium`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},onClick:se},[h(a,{icon:`right-from-bracket`,class:`mr-1.5`,"aria-hidden":`true`}),R(U(W(H)(`me.logout`)),1)])):B(``,!0)],12,Ii)):B(``,!0)],544)}}}),sa=[`title`,`aria-label`,`aria-expanded`,`aria-controls`],ca=[`src`],la={key:1,class:`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold`,style:{background:`var(--c-border)`,color:`var(--c-text-muted)`},"aria-hidden":`true`},ua={class:`truncate`},da=[`aria-current`,`onClick`],fa=[`src`],pa={key:1,class:`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold`,style:{background:`var(--c-border)`,color:`var(--c-text-muted)`},"aria-hidden":`true`},ma={class:`min-w-0 flex-1 truncate`},ha=b({__name:`GuildSwitcher`,setup(e){let{guilds:n,currentGuild:a,selectGuild:s}=Ni(),u=P(!1),d=P(null),f=P(null),m=o(()=>n.value.length>1),h=p(),g=`${h}-trigger`,_=`${h}-panel`;function y(e){return(e||`?`).trim().charAt(0).toUpperCase()}function b(e=!1,t=!1){u.value&&=(e&&f.value?.focus({focusVisible:!t}),!1)}function x(){m.value&&(u.value?b():u.value=!0)}function S(e,t){s(e),b(!0,t.detail>0)}function C(e){u.value&&d.value&&!d.value.contains(e.target)&&b()}function w(e){e.key===`Escape`&&u.value&&!e.defaultPrevented&&b(!!d.value?.contains(document.activeElement))}function E(e){let t=e.relatedTarget;u.value&&t instanceof Node&&d.value&&!d.value.contains(t)&&b()}return O(()=>{document.addEventListener(`click`,C,!0),document.addEventListener(`keydown`,w)}),r(()=>{document.removeEventListener(`click`,C,!0),document.removeEventListener(`keydown`,w)}),(e,r)=>{let o=c(`Icon`);return W(a)?(l(),t(`div`,{key:0,ref_key:`root`,ref:d,class:`relative min-w-0`,onFocusout:E},[i(`button`,{id:g,ref_key:`trigger`,ref:f,type:`button`,class:L([`flex h-9 max-w-[12rem] min-w-0 items-center gap-2 rounded-full border-0 py-1 pr-3 pl-1 text-xs font-medium`,m.value?`cursor-pointer`:`cursor-default`]),style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:m.value?W(H)(`guild.switch`):W(a).name,"aria-label":m.value?`${W(H)(`guild.switch`)}: ${W(a).name}`:`${W(H)(`guild.label`)}: ${W(a).name}`,"aria-expanded":m.value?u.value:void 0,"aria-controls":m.value&&u.value?_:void 0,onClick:x},[W(a).icon?(l(),t(`img`,{key:0,src:W(a).icon,alt:``,class:`h-7 w-7 shrink-0 rounded-full`},null,8,ca)):(l(),t(`span`,la,U(y(W(a).name)),1)),i(`span`,ua,U(W(a).name),1),m.value?(l(),v(o,{key:2,icon:`chevron-down`,class:`shrink-0 text-[10px] opacity-60`,"aria-hidden":`true`})):B(``,!0)],10,sa),u.value?(l(),t(`ul`,{key:0,id:_,role:`list`,"aria-labelledby":g,class:`absolute top-full left-0 z-30 mt-2 max-h-80 w-64 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-2xl p-1.5 text-sm`,style:{background:`var(--c-surface)`,boxShadow:`var(--shadow-2)`,border:`1px solid var(--c-border)`}},[(l(!0),t(T,null,ee(W(n),e=>(l(),t(`li`,{key:e.id},[i(`button`,{type:`button`,"aria-current":e.id===W(a).id?`true`:void 0,class:`flex w-full cursor-pointer items-center gap-2.5 rounded-xl border-0 px-2 py-1.5 text-left`,style:N(e.id===W(a).id?{background:`var(--c-accent-soft)`,color:`var(--c-text)`}:{background:`transparent`,color:`var(--c-text)`}),onClick:t=>S(e.id,t)},[e.icon?(l(),t(`img`,{key:0,src:e.icon,alt:``,class:`h-7 w-7 shrink-0 rounded-full`},null,8,fa)):(l(),t(`span`,pa,U(y(e.name)),1)),i(`span`,ma,U(e.name),1),e.id===W(a).id?(l(),v(o,{key:2,icon:`check`,class:`shrink-0 text-xs`,"aria-hidden":`true`,style:{color:`var(--c-accent)`}})):B(``,!0)],12,da)]))),128))])):B(``,!0)],544)):B(``,!0)}}}),ga={class:`flex h-full items-center gap-3 px-3`},_a={class:`h-12 w-12 shrink-0 overflow-hidden rounded-lg`,style:{background:`var(--c-surface-2)`}},va={class:`min-w-0 flex-1`},ya={class:`truncate text-sm font-medium`},ba={key:0,class:`truncate text-xs`,style:{color:`var(--c-text-muted)`}},xa=[`title`,`aria-label`],Sa=[`title`,`aria-label`],Ca=b({__name:`ActivityMini`,setup(e){let{status:n,control:r}=et(),a=o(()=>n.value?.current??null);function s(){n.value&&r({action:n.value.play?`pause`:`resume`})}return(e,o)=>{let u=c(`Icon`);return l(),t(`div`,ga,[i(`div`,_a,[a.value?.has_thumbnail?(l(),v(vt,{key:0,src:W(Ee)(a.value.id,{small:!0}),alt:``,class:`h-full w-full object-cover`},null,8,[`src`])):B(``,!0)]),i(`div`,va,[i(`p`,ya,U(a.value?.title||W(H)(`np.nothing`)),1),a.value?.artist?(l(),t(`p`,ba,U(a.value.artist),1)):B(``,!0)]),i(`button`,{class:`flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`},title:W(n)?.play?W(H)(`ctl.pause`):W(H)(`ctl.play`),"aria-label":W(n)?.play?W(H)(`ctl.pause`):W(H)(`ctl.play`),onClick:s},[h(u,{icon:W(n)?.play?`pause`:`play`},null,8,[`icon`])],8,xa),i(`button`,{class:`flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(H)(`ctl.skip`),"aria-label":W(H)(`ctl.skip`),onClick:o[0]||=e=>W(r)({action:`skip`})},[h(u,{icon:`forward-step`})],8,Sa)])}}}),wa={key:1,class:`flex min-h-full flex-col`},Ta={class:`mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3`},Ea={class:`flex min-w-0 items-center gap-2`},Da={class:`flex h-8 w-8 shrink-0 items-center justify-center rounded-full`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`}},Oa={class:`order-last flex w-full min-w-0 rounded-full md:order-none md:w-auto`,style:{background:`var(--c-surface-2)`}},ka=[`aria-current`,`onClick`],Aa={class:`flex items-center gap-2`},ja=[`value`,`title`,`aria-label`],Ma=[`value`],Na=[`aria-label`,`title`],Pa={key:0,class:`sr-only`},Fa={key:1,class:`mx-auto mt-6 w-full max-w-3xl px-4`},Ia={class:`rounded-2xl p-5`,style:{background:`var(--c-surface)`,boxShadow:`var(--shadow-1)`}},La={class:`font-medium`},Ra={class:`mt-1 text-sm`,style:{color:`var(--c-text-muted)`}},za=ft(b({__name:`App`,setup(e){let n={search:()=>M(()=>import(`./SearchPage-XUcAySrQ.js`),__vite__mapDeps([0,1]),import.meta.url),library:()=>M(()=>import(`./LibraryPage-DFSKy9t_.js`),__vite__mapDeps([2,1,3]),import.meta.url),lists:()=>M(()=>import(`./PlaylistsPage-2TXqQdyp.js`),__vite__mapDeps([4,1,5]),import.meta.url),stats:()=>M(()=>import(`./StatsPage-Btbb_zgF.js`),__vite__mapDeps([6,1,7]),import.meta.url),cache:()=>M(()=>import(`./CachePage-J40hb-wo.js`),__vite__mapDeps([8,1]),import.meta.url),settings:()=>M(()=>import(`./SettingsPage-DWYOPYUV.js`),__vite__mapDeps([9,1,10]),import.meta.url)};function a(e){return _({loader:n[e],errorComponent:Or,onError(e,t,n,r){r<=1?setTimeout(t,1e3):n()}})}let s=Ce({});for(let e of Object.keys(n))s[e]=a(e);let u=P(null);D(Dr,()=>{let e=y.value;if(e===`home`)return;let t=u.value;t&&(t.tabIndex=-1,t.addEventListener(`blur`,()=>t.removeAttribute(`tabindex`),{once:!0}),t.focus()),s[e]=a(e)});let d={auto:`theme.auto`,light:`theme.light`,dark:`theme.dark`},f=[`home`,`search`,`library`,`lists`,`stats`,`cache`,`settings`],p={home:`nav.home`,search:`nav.search`,library:`nav.library`,lists:`nav.lists`,stats:`nav.stats`,cache:`nav.cache`,settings:`nav.settings`},g=[`search`,`library`,`stats`,`cache`],y=P(`home`),{noAccess:b}=Ni(),x=_e?window.matchMedia(`(max-height: 300px)`):null,S=P(!!x?.matches);function C(e){S.value=e.matches}x?.addEventListener(`change`,C);let w=document.documentElement,E=window.matchMedia(`(prefers-color-scheme: dark)`),te=P(E.matches);function ne(e){te.value=e.matches}E.addEventListener(`change`,ne);let k=o(()=>w.getAttribute(`data-theme-default`)===`dark`||te.value?`dark`:`light`);function j(){let e=Te(`theme`);return e===`light`||e===`dark`?e:`auto`}let ie=P(j()),oe=o(()=>ie.value===`auto`?k.value:ie.value);function F(e,t=!0){ie.value=e,e===`auto`?w.removeAttribute(`data-theme`):w.setAttribute(`data-theme`,e),document.querySelector(`meta[name="color-scheme"]`)?.setAttribute(`content`,e===`auto`?w.hasAttribute(`data-theme-default`)?`dark`:`light dark`:e),t&&(e===`auto`?ae(`theme`):se(`theme`,e))}F(ie.value,!1);function I(){let e=oe.value===`dark`?`light`:`dark`;F(e===k.value?`auto`:e)}let ce=o(()=>H(oe.value===`dark`?`theme.toLight`:`theme.toDark`)),le=o(()=>H(`theme.title`,{mode:ie.value===`auto`?H(`theme.autoAs`,{mode:H(d[k.value])}):H(d[ie.value])}));function ue(e){e.key===`theme`&&F(e.newValue===`light`||e.newValue===`dark`?e.newValue:`auto`,!1)}window.addEventListener(`storage`,ue);async function de(e){let t=e.target,n=t.value;!await re(n)&&t.value===n&&(t.value=pe.value)}A([y,pe],()=>{document.title=`${H(p[y.value])} · DJ Bot`},{immediate:!0});let L=P(null);function z(e,t){y.value=e;let n=t.currentTarget;je(()=>n.scrollIntoView({block:`nearest`,inline:`nearest`,container:`nearest`}))}let V=null;function fe(){let e=L.value;if(!e||V||typeof IntersectionObserver>`u`||typeof CSS<`u`&&CSS.supports(`animation-timeline`,`scroll()`))return;let t=e.firstElementChild,n=e.lastElementChild;t&&n&&(V=new IntersectionObserver(n=>{for(let{target:r,intersectionRatio:i}of n)e.classList.toggle(r===t?`more-start`:`more-end`,i<1)},{root:e,threshold:1,rootMargin:`1px`}),V.observe(t),V.observe(n))}A(S,e=>{e?(V?.disconnect(),V=null):je(fe)});function me(){let e=()=>{for(let e of Object.values(n))e().catch(()=>{})};`requestIdleCallback`in window?window.requestIdleCallback(e,{timeout:4e3}):setTimeout(e,1500)}return O(()=>{fe(),me()}),r(()=>{x?.removeEventListener(`change`,C),E.removeEventListener(`change`,ne),window.removeEventListener(`storage`,ue),V?.disconnect()}),(e,n)=>{let r=c(`Icon`);return S.value?(l(),v(Ca,{key:0,class:`h-full`})):(l(),t(`div`,wa,[i(`header`,{class:`sticky top-0 z-10 border-b backdrop-blur`,style:N({borderColor:`var(--c-border)`,background:`color-mix(in srgb, var(--c-bg) 85%, transparent)`,...W(_e)?{marginTop:`calc(-1 * var(--discord-safe-area-inset-top, 0px))`,paddingTop:`var(--discord-safe-area-inset-top, 0px)`}:{}})},[i(`div`,Ta,[i(`div`,Ea,[i(`span`,Da,[h(r,{icon:`music`,class:`text-sm`,"aria-hidden":`true`})]),n[0]||=i(`span`,{class:`hidden text-base font-semibold tracking-tight sm:inline`},`DJ Bot`,-1),W(_e)?B(``,!0):(l(),v(ha,{key:0}))]),i(`nav`,Oa,[i(`div`,{ref_key:`navScroller`,ref:L,class:`nav-scroller flex min-w-0 flex-1 gap-1 overflow-x-auto p-1`},[(l(),t(T,null,ee(f,e=>i(`button`,{key:e,type:`button`,class:`shrink-0 cursor-pointer rounded-full border-0 px-3.5 py-1.5 text-xs font-medium whitespace-nowrap`,style:N(y.value===e?{background:`var(--c-surface)`,color:`var(--c-text)`,boxShadow:`var(--shadow-1)`}:{background:`transparent`,color:`var(--c-text-muted)`}),"aria-current":y.value===e?`page`:void 0,onClick:t=>z(e,t)},U(W(H)(p[e])),13,ka)),64))],512)]),i(`div`,Aa,[h(oa),i(`select`,{value:W(pe),onChange:de,class:`h-9 cursor-pointer rounded-full border-0 px-2.5 text-xs`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},title:W(H)(`lang.title`),"aria-label":W(H)(`lang.title`)},[(l(!0),t(T,null,ee(W(Se),e=>(l(),t(`option`,{key:e.code,value:e.code},U(e.label),9,Ma))),128))],40,ja),i(`button`,{type:`button`,class:`flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border-0 text-sm`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`},"aria-label":ce.value,title:`${ce.value} · ${le.value}`,onClick:I},[h(r,{icon:oe.value===`dark`?`moon`:`sun`,"aria-hidden":`true`},null,8,[`icon`])],8,Na)])])],4),i(`main`,{ref_key:`mainEl`,ref:u,class:`flex-1`},[g.includes(y.value)?(l(),t(`h1`,Pa,U(W(H)(p[y.value])),1)):B(``,!0),W(b)?(l(),t(`div`,Fa,[i(`div`,Ia,[i(`p`,La,[h(r,{icon:`lock`,class:`mr-2`,"aria-hidden":`true`,style:{color:`var(--c-text-muted)`}}),R(U(W(H)(`guild.noAccessTitle`)),1)]),i(`p`,Ra,U(W(H)(`guild.noAccessHint`)),1)])])):B(``,!0),y.value===`home`?(l(),t(T,{key:2},[h(Sr),h(hi)],64)):(l(),v(m(W(s)[y.value]),{key:3}))],512)]))}}}),[[`__scopeId`,`data-v-1fd484a2`]]),Ba={key:1,class:`flex min-h-full items-center justify-center p-6`},Va={key:0,class:`w-full max-w-sm rounded-2xl p-5 text-center`,style:{background:`var(--c-surface)`,boxShadow:`var(--shadow-1)`}},Ha={class:`text-base font-medium`},Ua={class:`mt-2 text-sm leading-relaxed`,style:{color:`var(--c-text-muted)`}},Wa={key:1,class:`text-sm`,style:{color:`var(--c-text-muted)`}},Ga=b({__name:`ActivityGate`,setup(e){let n=[`not_in_voice_channel`,`not_a_member`,`guild_not_served`,`guild_required`,`activity_disabled`,`authorize_cancelled`,`discord_auth_failed`],a=o(()=>n.includes(F.error)?H(`act.err.${F.error}`):H(`act.err.other`,{code:F.error||`?`}));A(()=>F.phase,e=>{e===`error`&&Wt(`${H(`act.failedTitle`)}: ${a.value}`,{assertive:!0})});function s(){ue()}return O(()=>{_e&&(ue(),window.addEventListener(`pagehide`,ce))}),r(()=>window.removeEventListener(`pagehide`,ce)),(e,n)=>{let r=c(`Icon`);return!W(_e)||W(F).phase===`ready`?(l(),v(za,{key:0})):(l(),t(`div`,Ba,[W(F).phase===`error`?(l(),t(`div`,Va,[i(`h1`,Ha,U(W(H)(`act.failedTitle`)),1),i(`p`,Ua,U(a.value),1),i(`button`,{type:`button`,class:`mt-4 cursor-pointer rounded-full border-0 px-4 py-2 text-sm font-semibold`,style:{background:`var(--c-accent)`,color:`var(--c-on-accent)`},onClick:s},U(W(H)(`act.retry`)),1)])):(l(),t(`p`,Wa,[h(r,{icon:`music`,class:`mr-2`,"aria-hidden":`true`}),R(U(W(H)(`act.connecting`)),1)]))]))}}}),Ka=[`aria-labelledby`,`aria-describedby`],qa={method:`dialog`,class:`p-5`},Ja=[`id`],Ya=[`id`],Xa={class:`mt-5 flex flex-wrap justify-end gap-2`},Za=b({__name:`ConfirmDialog`,setup(e){let n=P(),a=P(),o=P(null),s=p(),c=p(),u;O(()=>{u=yi()}),r(()=>{u?.(),o.value?.resolve(!1)}),A(gi,async e=>{if(!e)return;o.value=e,await je();let t=n.value;if(!t)e.resolve(bi(e.message));else if(t.open)a.value?.focus();else{t.returnValue=``;try{t.showModal()}catch{e.resolve(bi(e.message))}}});function d(){let e=n.value,t=e?.returnValue===`confirm`;e&&(e.returnValue=``),o.value?.resolve(t)}return(e,r)=>(l(),t(`dialog`,{ref_key:`dlg`,ref:n,class:`m-auto w-[min(26rem,calc(100vw-2rem))] rounded-2xl border-0 p-0`,style:{background:`var(--c-surface)`,color:`var(--c-text)`,boxShadow:`var(--shadow-2)`},"aria-labelledby":W(s),"aria-describedby":o.value?.title?W(c):void 0,onClose:d},[i(`form`,qa,[i(`h2`,{id:W(s),class:`text-base font-semibold leading-snug break-words`},U(o.value?.title||o.value?.message),9,Ja),o.value?.title?(l(),t(`p`,{key:0,id:W(c),class:`mt-2 text-sm leading-relaxed break-words`,style:{color:`var(--c-text-muted)`}},U(o.value.message),9,Ya)):B(``,!0),i(`div`,Xa,[i(`button`,{ref_key:`cancelBtn`,ref:a,value:`cancel`,autofocus:``,class:`min-h-10 cursor-pointer rounded-full border-0 px-4 text-sm font-medium`,style:{background:`var(--c-surface-2)`,color:`var(--c-text)`}},U(o.value?.cancelLabel||W(H)(`common.cancel`)),513),i(`button`,{value:`confirm`,class:`min-h-10 cursor-pointer rounded-full border-0 px-4 text-sm font-semibold`,style:N(o.value?.destructive?{background:`var(--c-danger)`,color:`var(--c-on-danger)`}:{background:`var(--c-accent)`,color:`var(--c-on-accent)`})},U(o.value?.confirmLabel||W(H)(`common.confirm`)),5)])])],40,Ka))}});function Qa(e,t){(t==null||t>e.length)&&(t=e.length);for(var n=0,r=Array(t);n<t;n++)r[n]=e[n];return r}function $a(e){if(Array.isArray(e))return e}function eo(e){if(Array.isArray(e))return Qa(e)}function to(e,t){if(!(e instanceof t))throw TypeError(`Cannot call a class as a function`)}function no(e,t){for(var n=0;n<t.length;n++){var r=t[n];r.enumerable=r.enumerable||!1,r.configurable=!0,`value`in r&&(r.writable=!0),Object.defineProperty(e,mo(r.key),r)}}function ro(e,t,n){return t&&no(e.prototype,t),n&&no(e,n),Object.defineProperty(e,"prototype",{writable:!1}),e}function io(e,t){var n=typeof Symbol<`u`&&e[Symbol.iterator]||e[`@@iterator`];if(!n){if(Array.isArray(e)||(n=go(e))||t&&e&&typeof e.length==`number`){n&&(e=n);var r=0,i=function(){};return{s:i,n:function(){return r>=e.length?{done:!0}:{done:!1,value:e[r++]}},e:function(e){throw e},f:i}}throw TypeError(`Invalid attempt to iterate non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}var a,o=!0,s=!1;return{s:function(){n=n.call(e)},n:function(){var e=n.next();return o=e.done,e},e:function(e){s=!0,a=e},f:function(){try{o||n.return==null||n.return()}finally{if(s)throw a}}}}function q(e,t,n){return(t=mo(t))in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}function ao(e){if(typeof Symbol<`u`&&e[Symbol.iterator]!=null||e[`@@iterator`]!=null)return Array.from(e)}function oo(e,t){var n=e==null?null:typeof Symbol<`u`&&e[Symbol.iterator]||e[`@@iterator`];if(n!=null){var r,i,a,o,s=[],c=!0,l=!1;try{if(a=(n=n.call(e)).next,t===0){if(Object(n)!==n)return;c=!1}else for(;!(c=(r=a.call(n)).done)&&(s.push(r.value),s.length!==t);c=!0);}catch(e){l=!0,i=e}finally{try{if(!c&&n.return!=null&&(o=n.return(),Object(o)!==o))return}finally{if(l)throw i}}return s}}function so(){throw TypeError(`Invalid attempt to destructure non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function co(){throw TypeError(`Invalid attempt to spread non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function lo(e,t){var n=Object.keys(e);if(Object.getOwnPropertySymbols){var r=Object.getOwnPropertySymbols(e);t&&(r=r.filter(function(t){return Object.getOwnPropertyDescriptor(e,t).enumerable})),n.push.apply(n,r)}return n}function J(e){for(var t=1;t<arguments.length;t++){var n=arguments[t]==null?{}:arguments[t];t%2?lo(Object(n),!0).forEach(function(t){q(e,t,n[t])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(n)):lo(Object(n)).forEach(function(t){Object.defineProperty(e,t,Object.getOwnPropertyDescriptor(n,t))})}return e}function uo(e,t){return $a(e)||oo(e,t)||go(e,t)||so()}function fo(e){return eo(e)||ao(e)||go(e)||co()}function po(e,t){if(typeof e!=`object`||!e)return e;var n=e[Symbol.toPrimitive];if(n!==void 0){var r=n.call(e,t||`default`);if(typeof r!=`object`)return r;throw TypeError(`@@toPrimitive must return a primitive value.`)}return(t===`string`?String:Number)(e)}function mo(e){var t=po(e,`string`);return typeof t==`symbol`?t:t+``}function ho(e){"@babel/helpers - typeof";return ho=typeof Symbol==`function`&&typeof Symbol.iterator==`symbol`?function(e){return typeof e}:function(e){return e&&typeof Symbol==`function`&&e.constructor===Symbol&&e!==Symbol.prototype?`symbol`:typeof e},ho(e)}function go(e,t){if(e){if(typeof e==`string`)return Qa(e,t);var n={}.toString.call(e).slice(8,-1);return n===`Object`&&e.constructor&&(n=e.constructor.name),n===`Map`||n===`Set`?Array.from(e):n===`Arguments`||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)?Qa(e,t):void 0}}var _o=function(){},vo={},yo={},bo=null,xo={mark:_o,measure:_o};try{typeof window<`u`&&(vo=window),typeof document<`u`&&(yo=document),typeof MutationObserver<`u`&&(bo=MutationObserver),typeof performance<`u`&&(xo=performance)}catch{}var So=(vo.navigator||{}).userAgent,Co=So===void 0?``:So,wo=vo,Y=yo,To=bo,Eo=xo;wo.document;var Do=!!Y.documentElement&&!!Y.head&&typeof Y.addEventListener==`function`&&typeof Y.createElement==`function`,Oo=~Co.indexOf(`MSIE`)||~Co.indexOf(`Trident/`),ko,Ao=/fa(k|kd|s|r|l|t|d|dr|dl|dt|b|slr|slpr|wsb|tl|ns|nds|es|gt|jr|jfr|jdr|usb|ufsb|udsb|cr|ss|sr|sl|st|sds|sdr|sdl|sdt|sldr|slpdr|pr|ms|vs)?[\-\ ]/,jo=/Font ?Awesome ?([567 ]*)(Solid|Regular|Light|Thin|Duotone|Brands|Free|Pro|Sharp Duotone|Sharp|Kit|Notdog Duo|Notdog|Chisel|Etch|Graphite|Thumbprint|Jelly Fill|Jelly Duo|Jelly|Utility|Utility Fill|Utility Duo|Slab Press|Slab|Slab Duo|Slab Press Duo|Pixel|Mosaic|Vellum|Whiteboard)?.*/i,Mo={classic:{fa:`solid`,fas:`solid`,"fa-solid":`solid`,far:`regular`,"fa-regular":`regular`,fal:`light`,"fa-light":`light`,fat:`thin`,"fa-thin":`thin`,fab:`brands`,"fa-brands":`brands`},duotone:{fa:`solid`,fad:`solid`,"fa-solid":`solid`,"fa-duotone":`solid`,fadr:`regular`,"fa-regular":`regular`,fadl:`light`,"fa-light":`light`,fadt:`thin`,"fa-thin":`thin`},sharp:{fa:`solid`,fass:`solid`,"fa-solid":`solid`,fasr:`regular`,"fa-regular":`regular`,fasl:`light`,"fa-light":`light`,fast:`thin`,"fa-thin":`thin`},"sharp-duotone":{fa:`solid`,fasds:`solid`,"fa-solid":`solid`,fasdr:`regular`,"fa-regular":`regular`,fasdl:`light`,"fa-light":`light`,fasdt:`thin`,"fa-thin":`thin`},slab:{"fa-regular":`regular`,faslr:`regular`},"slab-press":{"fa-regular":`regular`,faslpr:`regular`},"slab-duo":{"fa-regular":`regular`,fasldr:`regular`},"slab-press-duo":{"fa-regular":`regular`,faslpdr:`regular`},thumbprint:{"fa-light":`light`,fatl:`light`},vellum:{"fa-solid":`solid`,favs:`solid`},pixel:{"fa-regular":`regular`,fapr:`regular`},mosaic:{"fa-solid":`solid`,fams:`solid`},whiteboard:{"fa-semibold":`semibold`,fawsb:`semibold`},notdog:{"fa-solid":`solid`,fans:`solid`},"notdog-duo":{"fa-solid":`solid`,fands:`solid`},etch:{"fa-solid":`solid`,faes:`solid`},graphite:{"fa-thin":`thin`,fagt:`thin`},jelly:{"fa-regular":`regular`,fajr:`regular`},"jelly-fill":{"fa-regular":`regular`,fajfr:`regular`},"jelly-duo":{"fa-regular":`regular`,fajdr:`regular`},chisel:{"fa-regular":`regular`,facr:`regular`},utility:{"fa-semibold":`semibold`,fausb:`semibold`},"utility-duo":{"fa-semibold":`semibold`,faudsb:`semibold`},"utility-fill":{"fa-semibold":`semibold`,faufsb:`semibold`}},No={GROUP:`duotone-group`,SWAP_OPACITY:`swap-opacity`,PRIMARY:`primary`,SECONDARY:`secondary`},Po=[`fa-classic`,`fa-duotone`,`fa-sharp`,`fa-sharp-duotone`,`fa-thumbprint`,`fa-whiteboard`,`fa-notdog`,`fa-notdog-duo`,`fa-chisel`,`fa-etch`,`fa-graphite`,`fa-jelly`,`fa-jelly-fill`,`fa-jelly-duo`,`fa-slab`,`fa-slab-press`,`fa-slab-press-duo`,`fa-slab-duo`,`fa-mosaic`,`fa-pixel`,`fa-vellum`,`fa-utility`,`fa-utility-duo`,`fa-utility-fill`],X=`classic`,Fo=`duotone`,Io=`sharp`,Lo=`sharp-duotone`,Ro=`chisel`,zo=`etch`,Bo=`graphite`,Vo=`jelly`,Ho=`jelly-duo`,Uo=`jelly-fill`,Wo=`mosaic`,Go=`notdog`,Ko=`notdog-duo`,qo=`pixel`,Jo=`slab`,Yo=`slab-duo`,Xo=`slab-press`,Zo=`slab-press-duo`,Qo=`thumbprint`,$o=`utility`,es=`utility-duo`,ts=`utility-fill`,ns=`vellum`,rs=`whiteboard`,is=`Classic`,as=`Duotone`,os=`Sharp`,ss=`Sharp Duotone`,cs=`Chisel`,ls=`Etch`,us=`Graphite`,ds=`Jelly`,fs=`Jelly Duo`,ps=`Jelly Fill`,ms=`Mosaic`,hs=`Notdog`,gs=`Notdog Duo`,_s=`Pixel`,vs=`Slab`,ys=`Slab Duo`,bs=`Slab Press`,xs=`Slab Press Duo`,Ss=`Thumbprint`,Cs=`Utility`,ws=`Utility Duo`,Ts=`Utility Fill`,Es=`Vellum`,Ds=`Whiteboard`,Os=[X,Fo,Io,Lo,Ro,zo,Bo,Vo,Ho,Uo,Wo,Go,Ko,qo,Jo,Yo,Xo,Zo,Qo,$o,es,ts,ns,rs];ko={},q(q(q(q(q(q(q(q(q(q(ko,X,is),Fo,as),Io,os),Lo,ss),Ro,cs),zo,ls),Bo,us),Vo,ds),Ho,fs),Uo,ps),q(q(q(q(q(q(q(q(q(q(ko,Wo,ms),Go,hs),Ko,gs),qo,_s),Jo,vs),Yo,ys),Xo,bs),Zo,xs),Qo,Ss),$o,Cs),q(q(q(q(ko,es,ws),ts,Ts),ns,Es),rs,Ds);var ks={classic:{900:`fas`,400:`far`,normal:`far`,300:`fal`,100:`fat`},duotone:{900:`fad`,400:`fadr`,300:`fadl`,100:`fadt`},sharp:{900:`fass`,400:`fasr`,300:`fasl`,100:`fast`},"sharp-duotone":{900:`fasds`,400:`fasdr`,300:`fasdl`,100:`fasdt`},slab:{400:`faslr`},"slab-press":{400:`faslpr`},"slab-duo":{400:`fasldr`},"slab-press-duo":{400:`faslpdr`},vellum:{900:`favs`},mosaic:{900:`fams`},pixel:{400:`fapr`},whiteboard:{600:`fawsb`},thumbprint:{300:`fatl`},notdog:{900:`fans`},"notdog-duo":{900:`fands`},etch:{900:`faes`},graphite:{100:`fagt`},chisel:{400:`facr`},jelly:{400:`fajr`},"jelly-fill":{400:`fajfr`},"jelly-duo":{400:`fajdr`},utility:{600:`fausb`},"utility-duo":{600:`faudsb`},"utility-fill":{600:`faufsb`}},As={"Font Awesome 7 Free":{900:`fas`,400:`far`},"Font Awesome 7 Pro":{900:`fas`,400:`far`,normal:`far`,300:`fal`,100:`fat`},"Font Awesome 7 Brands":{400:`fab`,normal:`fab`},"Font Awesome 7 Duotone":{900:`fad`,400:`fadr`,normal:`fadr`,300:`fadl`,100:`fadt`},"Font Awesome 7 Sharp":{900:`fass`,400:`fasr`,normal:`fasr`,300:`fasl`,100:`fast`},"Font Awesome 7 Sharp Duotone":{900:`fasds`,400:`fasdr`,normal:`fasdr`,300:`fasdl`,100:`fasdt`},"Font Awesome 7 Jelly":{400:`fajr`,normal:`fajr`},"Font Awesome 7 Jelly Fill":{400:`fajfr`,normal:`fajfr`},"Font Awesome 7 Jelly Duo":{400:`fajdr`,normal:`fajdr`},"Font Awesome 7 Slab":{400:`faslr`,normal:`faslr`},"Font Awesome 7 Slab Press":{400:`faslpr`,normal:`faslpr`},"Font Awesome 7 Slab Duo":{400:`fasldr`,normal:`fasldr`},"Font Awesome 7 Slab Press Duo":{400:`faslpdr`,normal:`faslpdr`},"Font Awesome 7 Pixel":{400:`fapr`,normal:`fapr`},"Font Awesome 7 Mosaic":{900:`fams`,normal:`fams`},"Font Awesome 7 Vellum":{900:`favs`,normal:`favs`},"Font Awesome 7 Thumbprint":{300:`fatl`,normal:`fatl`},"Font Awesome 7 Notdog":{900:`fans`,normal:`fans`},"Font Awesome 7 Notdog Duo":{900:`fands`,normal:`fands`},"Font Awesome 7 Etch":{900:`faes`,normal:`faes`},"Font Awesome 7 Graphite":{100:`fagt`,normal:`fagt`},"Font Awesome 7 Chisel":{400:`facr`,normal:`facr`},"Font Awesome 7 Whiteboard":{600:`fawsb`,normal:`fawsb`},"Font Awesome 7 Utility":{600:`fausb`,normal:`fausb`},"Font Awesome 7 Utility Duo":{600:`faudsb`,normal:`faudsb`},"Font Awesome 7 Utility Fill":{600:`faufsb`,normal:`faufsb`}},js=new Map([[`classic`,{defaultShortPrefixId:`fas`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`,`brands`],futureStyleIds:[],defaultFontWeight:900}],[`duotone`,{defaultShortPrefixId:`fad`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`],futureStyleIds:[],defaultFontWeight:900}],[`sharp`,{defaultShortPrefixId:`fass`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`],futureStyleIds:[],defaultFontWeight:900}],[`sharp-duotone`,{defaultShortPrefixId:`fasds`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`],futureStyleIds:[],defaultFontWeight:900}],[`chisel`,{defaultShortPrefixId:`facr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`etch`,{defaultShortPrefixId:`faes`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`graphite`,{defaultShortPrefixId:`fagt`,defaultStyleId:`thin`,styleIds:[`thin`],futureStyleIds:[],defaultFontWeight:100}],[`jelly`,{defaultShortPrefixId:`fajr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`jelly-duo`,{defaultShortPrefixId:`fajdr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`jelly-fill`,{defaultShortPrefixId:`fajfr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`mosaic`,{defaultShortPrefixId:`fams`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`notdog`,{defaultShortPrefixId:`fans`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`notdog-duo`,{defaultShortPrefixId:`fands`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`pixel`,{defaultShortPrefixId:`fapr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`slab`,{defaultShortPrefixId:`faslr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`slab-duo`,{defaultShortPrefixId:`fasldr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`slab-press`,{defaultShortPrefixId:`faslpr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`slab-press-duo`,{defaultShortPrefixId:`faslpdr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`thumbprint`,{defaultShortPrefixId:`fatl`,defaultStyleId:`light`,styleIds:[`light`],futureStyleIds:[],defaultFontWeight:300}],[`utility`,{defaultShortPrefixId:`fausb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}],[`utility-duo`,{defaultShortPrefixId:`faudsb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}],[`utility-fill`,{defaultShortPrefixId:`faufsb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}],[`vellum`,{defaultShortPrefixId:`favs`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`whiteboard`,{defaultShortPrefixId:`fawsb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}]]),Ms={chisel:{regular:`facr`},classic:{brands:`fab`,light:`fal`,regular:`far`,solid:`fas`,thin:`fat`},duotone:{light:`fadl`,regular:`fadr`,solid:`fad`,thin:`fadt`},etch:{solid:`faes`},graphite:{thin:`fagt`},jelly:{regular:`fajr`},"jelly-duo":{regular:`fajdr`},"jelly-fill":{regular:`fajfr`},mosaic:{solid:`fams`},notdog:{solid:`fans`},"notdog-duo":{solid:`fands`},pixel:{regular:`fapr`},sharp:{light:`fasl`,regular:`fasr`,solid:`fass`,thin:`fast`},"sharp-duotone":{light:`fasdl`,regular:`fasdr`,solid:`fasds`,thin:`fasdt`},slab:{regular:`faslr`},"slab-duo":{regular:`fasldr`},"slab-press":{regular:`faslpr`},"slab-press-duo":{regular:`faslpdr`},thumbprint:{light:`fatl`},utility:{semibold:`fausb`},"utility-duo":{semibold:`faudsb`},"utility-fill":{semibold:`faufsb`},vellum:{solid:`favs`},whiteboard:{semibold:`fawsb`}},Ns=[`fak`,`fa-kit`,`fakd`,`fa-kit-duotone`],Ps={kit:{fak:`kit`,"fa-kit":`kit`},"kit-duotone":{fakd:`kit-duotone`,"fa-kit-duotone":`kit-duotone`}},Fs=[`kit`];q(q({},`kit`,`Kit`),`kit-duotone`,`Kit Duotone`);var Is={kit:{"fa-kit":`fak`},"kit-duotone":{"fa-kit-duotone":`fakd`}},Ls={"Font Awesome Kit":{400:`fak`,normal:`fak`},"Font Awesome Kit Duotone":{400:`fakd`,normal:`fakd`}},Rs={kit:{fak:`fa-kit`},"kit-duotone":{fakd:`fa-kit-duotone`}},zs={kit:{kit:`fak`},"kit-duotone":{"kit-duotone":`fakd`}},Bs,Vs={GROUP:`duotone-group`,SWAP_OPACITY:`swap-opacity`,PRIMARY:`primary`,SECONDARY:`secondary`},Hs=[`fa-classic`,`fa-duotone`,`fa-sharp`,`fa-sharp-duotone`,`fa-thumbprint`,`fa-whiteboard`,`fa-notdog`,`fa-notdog-duo`,`fa-chisel`,`fa-etch`,`fa-graphite`,`fa-jelly`,`fa-jelly-fill`,`fa-jelly-duo`,`fa-slab`,`fa-slab-press`,`fa-slab-press-duo`,`fa-slab-duo`,`fa-mosaic`,`fa-pixel`,`fa-vellum`,`fa-utility`,`fa-utility-duo`,`fa-utility-fill`];Bs={},q(q(q(q(q(q(q(q(q(q(Bs,`classic`,`Classic`),`duotone`,`Duotone`),`sharp`,`Sharp`),`sharp-duotone`,`Sharp Duotone`),`chisel`,`Chisel`),`etch`,`Etch`),`graphite`,`Graphite`),`jelly`,`Jelly`),`jelly-duo`,`Jelly Duo`),`jelly-fill`,`Jelly Fill`),q(q(q(q(q(q(q(q(q(q(Bs,`mosaic`,`Mosaic`),`notdog`,`Notdog`),`notdog-duo`,`Notdog Duo`),`pixel`,`Pixel`),`slab`,`Slab`),`slab-duo`,`Slab Duo`),`slab-press`,`Slab Press`),`slab-press-duo`,`Slab Press Duo`),`thumbprint`,`Thumbprint`),`utility`,`Utility`),q(q(q(q(Bs,`utility-duo`,`Utility Duo`),`utility-fill`,`Utility Fill`),`vellum`,`Vellum`),`whiteboard`,`Whiteboard`),q(q({},`kit`,`Kit`),`kit-duotone`,`Kit Duotone`);var Us={classic:{"fa-brands":`fab`,"fa-duotone":`fad`,"fa-light":`fal`,"fa-regular":`far`,"fa-solid":`fas`,"fa-thin":`fat`},duotone:{"fa-regular":`fadr`,"fa-light":`fadl`,"fa-thin":`fadt`},sharp:{"fa-solid":`fass`,"fa-regular":`fasr`,"fa-light":`fasl`,"fa-thin":`fast`},"sharp-duotone":{"fa-solid":`fasds`,"fa-regular":`fasdr`,"fa-light":`fasdl`,"fa-thin":`fasdt`},slab:{"fa-regular":`faslr`},"slab-press":{"fa-regular":`faslpr`},"slab-duo":{"fa-regular":`fasldr`},"slab-press-duo":{"fa-regular":`faslpdr`},pixel:{"fa-regular":`fapr`},mosaic:{"fa-solid":`fams`},vellum:{"fa-solid":`favs`},whiteboard:{"fa-semibold":`fawsb`},thumbprint:{"fa-light":`fatl`},notdog:{"fa-solid":`fans`},"notdog-duo":{"fa-solid":`fands`},etch:{"fa-solid":`faes`},graphite:{"fa-thin":`fagt`},jelly:{"fa-regular":`fajr`},"jelly-fill":{"fa-regular":`fajfr`},"jelly-duo":{"fa-regular":`fajdr`},chisel:{"fa-regular":`facr`},utility:{"fa-semibold":`fausb`},"utility-duo":{"fa-semibold":`faudsb`},"utility-fill":{"fa-semibold":`faufsb`}},Ws={classic:[`fas`,`far`,`fal`,`fat`,`fad`],duotone:[`fadr`,`fadl`,`fadt`],sharp:[`fass`,`fasr`,`fasl`,`fast`],"sharp-duotone":[`fasds`,`fasdr`,`fasdl`,`fasdt`],slab:[`faslr`],"slab-press":[`faslpr`],"slab-duo":[`fasldr`],"slab-press-duo":[`faslpdr`],pixel:[`fapr`],mosaic:[`fams`],vellum:[`favs`],whiteboard:[`fawsb`],thumbprint:[`fatl`],notdog:[`fans`],"notdog-duo":[`fands`],etch:[`faes`],graphite:[`fagt`],jelly:[`fajr`],"jelly-fill":[`fajfr`],"jelly-duo":[`fajdr`],chisel:[`facr`],utility:[`fausb`],"utility-duo":[`faudsb`],"utility-fill":[`faufsb`]},Gs={classic:{fab:`fa-brands`,fad:`fa-duotone`,fal:`fa-light`,far:`fa-regular`,fas:`fa-solid`,fat:`fa-thin`},duotone:{fadr:`fa-regular`,fadl:`fa-light`,fadt:`fa-thin`},sharp:{fass:`fa-solid`,fasr:`fa-regular`,fasl:`fa-light`,fast:`fa-thin`},"sharp-duotone":{fasds:`fa-solid`,fasdr:`fa-regular`,fasdl:`fa-light`,fasdt:`fa-thin`},slab:{faslr:`fa-regular`},"slab-press":{faslpr:`fa-regular`},"slab-duo":{fasldr:`fa-regular`},"slab-press-duo":{faslpdr:`fa-regular`},pixel:{fapr:`fa-regular`},mosaic:{fams:`fa-solid`},vellum:{favs:`fa-solid`},whiteboard:{fawsb:`fa-semibold`},thumbprint:{fatl:`fa-light`},notdog:{fans:`fa-solid`},"notdog-duo":{fands:`fa-solid`},etch:{faes:`fa-solid`},graphite:{fagt:`fa-thin`},jelly:{fajr:`fa-regular`},"jelly-fill":{fajfr:`fa-regular`},"jelly-duo":{fajdr:`fa-regular`},chisel:{facr:`fa-regular`},utility:{fausb:`fa-semibold`},"utility-duo":{faudsb:`fa-semibold`},"utility-fill":{faufsb:`fa-semibold`}},Ks=`fa.fas.far.fal.fat.fad.fadr.fadl.fadt.fab.fass.fasr.fasl.fast.fasds.fasdr.fasdl.fasdt.faslr.faslpr.fasldr.faslpdr.fapr.fams.favs.fawsb.fatl.fans.fands.faes.fagt.fajr.fajfr.fajdr.facr.fausb.faudsb.faufsb`.split(`.`).concat(Hs,[`fa-solid`,`fa-regular`,`fa-light`,`fa-thin`,`fa-duotone`,`fa-brands`,`fa-semibold`]),qs=[`solid`,`regular`,`light`,`thin`,`duotone`,`brands`,`semibold`],Js=[1,2,3,4,5,6,7,8,9,10],Ys=Js.concat([11,12,13,14,15,16,17,18,19,20]),Xs=[].concat(fo(Object.keys(Ws)),qs,[`aw`,`fw`,`pull-left`,`pull-right`],[`2xs`,`xs`,`sm`,`lg`,`xl`,`2xl`,`beat`,`beat-fade`,`border`,`bounce`,`buzz`,`canvas-square`,`canvas-roomy`,`fade`,`flip-360`,`flip-both`,`flip-horizontal`,`flip-vertical`,`flip`,`float`,`inverse`,`jello`,`layers`,`layers-bottom-left`,`layers-bottom-right`,`layers-counter`,`layers-text`,`layers-top-left`,`layers-top-right`,`li`,`pull-end`,`pull-start`,`pulse`,`rotate-180`,`rotate-270`,`rotate-90`,`rotate-by`,`shake`,`spin-pulse`,`spin-reverse`,`spin`,`spin-snap`,`spin-snap-4`,`spin-snap-8`,`stack-1x`,`stack-2x`,`stack`,`swing`,`ul`,`wag`,`width-auto`,`width-fixed`,Vs.GROUP,Vs.SWAP_OPACITY,Vs.PRIMARY,Vs.SECONDARY],Js.map(function(e){return`${e}x`}),Ys.map(function(e){return`w-${e}`})),Zs={"Font Awesome 5 Free":{900:`fas`,400:`far`},"Font Awesome 5 Pro":{900:`fas`,400:`far`,normal:`far`,300:`fal`},"Font Awesome 5 Brands":{400:`fab`,normal:`fab`},"Font Awesome 5 Duotone":{900:`fad`}},Qs=`___FONT_AWESOME___`,$s=16,ec=`fa`,tc=`svg-inline--fa`,nc=`data-fa-i2svg`,rc=`data-fa-pseudo-element`,ic=`data-fa-pseudo-element-pending`,ac=`data-prefix`,oc=`data-icon`,sc=`fontawesome-i2svg`,cc=`async`,lc=[`HTML`,`HEAD`,`STYLE`,`SCRIPT`],uc=[`::before`,`::after`,`:before`,`:after`],dc=function(){try{return!0}catch{return!1}}();function fc(e){return new Proxy(e,{get:function(e,t){return t in e?e[t]:e[X]}})}var pc=J({},Mo);pc[X]=J(J(J(J({},{"fa-duotone":`duotone`}),Mo[X]),Ps.kit),Ps[`kit-duotone`]);var mc=fc(pc),hc=J({},Ms);hc[X]=J(J(J(J({},{duotone:`fad`}),hc[X]),zs.kit),zs[`kit-duotone`]);var gc=fc(hc),_c=J({},Gs);_c[X]=J(J({},_c[X]),Rs.kit);var vc=fc(_c),yc=J({},Us);yc[X]=J(J({},yc[X]),Is.kit),fc(yc);var bc=Ao,xc=`fa-layers-text`,Sc=jo;fc(J({},ks));var Cc=[`class`,`data-prefix`,`data-icon`,`data-fa-transform`,`data-fa-mask`],wc=No,Tc=[].concat(fo(Fs),fo(Xs)),Ec=wo.FontAwesomeConfig||{};function Dc(e){var t=Y.querySelector(`script[`+e+`]`);if(t)return t.getAttribute(e)}function Oc(e){return e===``?!0:e===`false`?!1:e===`true`||e}Y&&typeof Y.querySelector==`function`&&[[`data-family-prefix`,`familyPrefix`],[`data-css-prefix`,`cssPrefix`],[`data-family-default`,`familyDefault`],[`data-style-default`,`styleDefault`],[`data-replacement-class`,`replacementClass`],[`data-auto-replace-svg`,`autoReplaceSvg`],[`data-auto-add-css`,`autoAddCss`],[`data-search-pseudo-elements`,`searchPseudoElements`],[`data-search-pseudo-elements-warnings`,`searchPseudoElementsWarnings`],[`data-search-pseudo-elements-full-scan`,`searchPseudoElementsFullScan`],[`data-observe-mutations`,`observeMutations`],[`data-mutate-approach`,`mutateApproach`],[`data-keep-original-source`,`keepOriginalSource`],[`data-measure-performance`,`measurePerformance`],[`data-show-missing-icons`,`showMissingIcons`]].forEach(function(e){var t=uo(e,2),n=t[0],r=t[1],i=Oc(Dc(n));i!=null&&(Ec[r]=i)});var kc={styleDefault:`solid`,familyDefault:X,cssPrefix:ec,replacementClass:tc,autoReplaceSvg:!0,autoAddCss:!0,searchPseudoElements:!1,searchPseudoElementsWarnings:!0,searchPseudoElementsFullScan:!1,observeMutations:!0,mutateApproach:`async`,keepOriginalSource:!0,measurePerformance:!1,showMissingIcons:!0};Ec.familyPrefix&&(Ec.cssPrefix=Ec.familyPrefix);var Ac=J(J({},kc),Ec);Ac.autoReplaceSvg||(Ac.observeMutations=!1);var Z={};Object.keys(kc).forEach(function(e){Object.defineProperty(Z,e,{enumerable:!0,set:function(t){Ac[e]=t,jc.forEach(function(e){return e(Z)})},get:function(){return Ac[e]}})}),Object.defineProperty(Z,"familyPrefix",{enumerable:!0,set:function(e){Ac.cssPrefix=e,jc.forEach(function(e){return e(Z)})},get:function(){return Ac.cssPrefix}}),wo.FontAwesomeConfig=Z;var jc=[];function Mc(e){return jc.push(e),function(){jc.splice(jc.indexOf(e),1)}}var Nc=$s,Pc={size:16,x:0,y:0,rotate:0,flipX:!1,flipY:!1};function Fc(e){if(e&&Do){var t=Y.createElement(`style`);t.setAttribute(`type`,`text/css`),t.innerHTML=e;for(var n=Y.head.childNodes,r=null,i=n.length-1;i>-1;i--){var a=n[i],o=(a.tagName||``).toUpperCase();[`STYLE`,`LINK`].indexOf(o)>-1&&(r=a)}return Y.head.insertBefore(t,r),e}}var Ic=`0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ`;function Lc(){for(var e=12,t=``;e-->0;)t+=Ic[Math.random()*62|0];return t}function Rc(e){for(var t=[],n=(e||[]).length>>>0;n--;)t[n]=e[n];return t}function zc(e){return e.classList?Rc(e.classList):(e.getAttribute(`class`)||``).split(` `).filter(function(e){return e})}function Bc(e){return`${e}`.replace(/&/g,`&amp;`).replace(/"/g,`&quot;`).replace(/'/g,`&#39;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`)}function Vc(e){return Object.keys(e||{}).reduce(function(t,n){return t+`${n}="${Bc(e[n])}" `},``).trim()}function Hc(e){return Object.keys(e||{}).reduce(function(t,n){return t+`${n}: ${e[n].trim()};`},``)}function Uc(e){return e.size!==Pc.size||e.x!==Pc.x||e.y!==Pc.y||e.rotate!==Pc.rotate||e.flipX||e.flipY}function Wc(e){var t=e.transform,n=e.containerWidth,r=e.iconWidth;return{outer:{transform:`translate(${n/2} 256)`},inner:{transform:`${`translate(${t.x*32}, ${t.y*32}) `} ${`scale(${t.size/16*(t.flipX?-1:1)}, ${t.size/16*(t.flipY?-1:1)}) `} ${`rotate(${t.rotate} 0 0)`}`},path:{transform:`translate(${r/2*-1} -256)`}}}function Gc(e){var t=e.transform,n=e.width,r=n===void 0?$s:n,i=e.height,a=i===void 0?$s:i,o=e.startCentered,s=o!==void 0&&o,c=``;return c+=s&&Oo?`translate(${t.x/Nc-r/2}em, ${t.y/Nc-a/2}em) `:s?`translate(calc(-50% + ${t.x/Nc}em), calc(-50% + ${t.y/Nc}em)) `:`translate(${t.x/Nc}em, ${t.y/Nc}em) `,c+=`scale(${t.size/Nc*(t.flipX?-1:1)}, ${t.size/Nc*(t.flipY?-1:1)}) `,c+=`rotate(${t.rotate}deg) `,c}var Kc=`:root, :host {
  --fa-font-solid: normal 900 1em/1 'Font Awesome 7 Free';
  --fa-font-regular: normal 400 1em/1 'Font Awesome 7 Free';
  --fa-font-light: normal 300 1em/1 'Font Awesome 7 Pro';
  --fa-font-thin: normal 100 1em/1 'Font Awesome 7 Pro';
  --fa-font-duotone: normal 900 1em/1 'Font Awesome 7 Duotone';
  --fa-font-duotone-regular: normal 400 1em/1 'Font Awesome 7 Duotone';
  --fa-font-duotone-light: normal 300 1em/1 'Font Awesome 7 Duotone';
  --fa-font-duotone-thin: normal 100 1em/1 'Font Awesome 7 Duotone';
  --fa-font-brands: normal 400 1em/1 'Font Awesome 7 Brands';
  --fa-font-sharp-solid: normal 900 1em/1 'Font Awesome 7 Sharp';
  --fa-font-sharp-regular: normal 400 1em/1 'Font Awesome 7 Sharp';
  --fa-font-sharp-light: normal 300 1em/1 'Font Awesome 7 Sharp';
  --fa-font-sharp-thin: normal 100 1em/1 'Font Awesome 7 Sharp';
  --fa-font-sharp-duotone-solid: normal 900 1em/1 'Font Awesome 7 Sharp Duotone';
  --fa-font-sharp-duotone-regular: normal 400 1em/1 'Font Awesome 7 Sharp Duotone';
  --fa-font-sharp-duotone-light: normal 300 1em/1 'Font Awesome 7 Sharp Duotone';
  --fa-font-sharp-duotone-thin: normal 100 1em/1 'Font Awesome 7 Sharp Duotone';
  --fa-font-slab-regular: normal 400 1em/1 'Font Awesome 7 Slab';
  --fa-font-slab-press-regular: normal 400 1em/1 'Font Awesome 7 Slab Press';
  --fa-font-slab-duo-regular: normal 400 1em/1 'Font Awesome 7 Slab Duo';
  --fa-font-slab-press-duo-regular: normal 400 1em/1 'Font Awesome 7 Slab Press Duo';
  --fa-font-pixel-regular: normal 400 1em/1 'Font Awesome 7 Pixel';
  --fa-font-mosaic-solid: normal 900 1em/1 'Font Awesome 7 Mosaic';
  --fa-font-vellum-solid: normal 900 1em/1 'Font Awesome 7 Vellum';
  --fa-font-whiteboard-semibold: normal 600 1em/1 'Font Awesome 7 Whiteboard';
  --fa-font-thumbprint-light: normal 300 1em/1 'Font Awesome 7 Thumbprint';
  --fa-font-notdog-solid: normal 900 1em/1 'Font Awesome 7 Notdog';
  --fa-font-notdog-duo-solid: normal 900 1em/1 'Font Awesome 7 Notdog Duo';
  --fa-font-etch-solid: normal 900 1em/1 'Font Awesome 7 Etch';
  --fa-font-graphite-thin: normal 100 1em/1 'Font Awesome 7 Graphite';
  --fa-font-jelly-regular: normal 400 1em/1 'Font Awesome 7 Jelly';
  --fa-font-jelly-fill-regular: normal 400 1em/1 'Font Awesome 7 Jelly Fill';
  --fa-font-jelly-duo-regular: normal 400 1em/1 'Font Awesome 7 Jelly Duo';
  --fa-font-chisel-regular: normal 400 1em/1 'Font Awesome 7 Chisel';
  --fa-font-utility-semibold: normal 600 1em/1 'Font Awesome 7 Utility';
  --fa-font-utility-duo-semibold: normal 600 1em/1 'Font Awesome 7 Utility Duo';
  --fa-font-utility-fill-semibold: normal 600 1em/1 'Font Awesome 7 Utility Fill';
}

.svg-inline--fa {
  box-sizing: content-box;
  display: var(--fa-display, inline-block);
  height: 1em;
  overflow: visible;
  vertical-align: -0.125em;
  width: var(--fa-width, 1.25em);
}
.svg-inline--fa.fa-2xs {
  vertical-align: 0.1em;
}
.svg-inline--fa.fa-xs {
  vertical-align: 0em;
}
.svg-inline--fa.fa-sm {
  vertical-align: -0.0714285714em;
}
.svg-inline--fa.fa-lg {
  vertical-align: -0.2em;
}
.svg-inline--fa.fa-xl {
  vertical-align: -0.25em;
}
.svg-inline--fa.fa-2xl {
  vertical-align: -0.3125em;
}
.svg-inline--fa.fa-pull-left,
.svg-inline--fa .fa-pull-start {
  float: inline-start;
  margin-inline-end: var(--fa-pull-margin, 0.3em);
}
.svg-inline--fa.fa-pull-right,
.svg-inline--fa .fa-pull-end {
  float: inline-end;
  margin-inline-start: var(--fa-pull-margin, 0.3em);
}
.svg-inline--fa.fa-li {
  width: var(--fa-li-width, 2em);
  inset-inline-start: calc(-1 * var(--fa-li-width, 2em));
  inset-block-start: 0.25em; /* syncing vertical alignment with Web Font rendering */
}

.fa-layers-counter, .fa-layers-text {
  display: inline-block;
  position: absolute;
  text-align: center;
}

.fa-layers {
  display: inline-block;
  height: 1em;
  position: relative;
  text-align: center;
  vertical-align: -0.125em;
  width: var(--fa-width, 1.25em);
}
.fa-layers .svg-inline--fa {
  inset: 0;
  margin: auto;
  position: absolute;
  transform-origin: center center;
}

.fa-layers-text {
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  transform-origin: center center;
}

.fa-layers-counter {
  background-color: var(--fa-counter-background-color, #ff253a);
  border-radius: var(--fa-counter-border-radius, 1em);
  box-sizing: border-box;
  color: var(--fa-inverse, #fff);
  line-height: var(--fa-counter-line-height, 1);
  max-width: var(--fa-counter-max-width, 5em);
  min-width: var(--fa-counter-min-width, 1.5em);
  overflow: hidden;
  padding: var(--fa-counter-padding, 0.25em 0.5em);
  right: var(--fa-right, 0);
  text-overflow: ellipsis;
  top: var(--fa-top, 0);
  transform: scale(var(--fa-counter-scale, 0.25));
  transform-origin: top right;
}

.fa-layers-bottom-right {
  bottom: var(--fa-bottom, 0);
  right: var(--fa-right, 0);
  top: auto;
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: bottom right;
}

.fa-layers-bottom-left {
  bottom: var(--fa-bottom, 0);
  left: var(--fa-left, 0);
  right: auto;
  top: auto;
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: bottom left;
}

.fa-layers-top-right {
  top: var(--fa-top, 0);
  right: var(--fa-right, 0);
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: top right;
}

.fa-layers-top-left {
  left: var(--fa-left, 0);
  right: auto;
  top: var(--fa-top, 0);
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: top left;
}

.fa-1x {
  font-size: 1em;
}

.fa-2x {
  font-size: 2em;
}

.fa-3x {
  font-size: 3em;
}

.fa-4x {
  font-size: 4em;
}

.fa-5x {
  font-size: 5em;
}

.fa-6x {
  font-size: 6em;
}

.fa-7x {
  font-size: 7em;
}

.fa-8x {
  font-size: 8em;
}

.fa-9x {
  font-size: 9em;
}

.fa-10x {
  font-size: 10em;
}

.fa-2xs {
  font-size: calc(10 / 16 * 1em); /* converts a 10px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 10 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 10 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-xs {
  font-size: calc(12 / 16 * 1em); /* converts a 12px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 12 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 12 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-sm {
  font-size: calc(14 / 16 * 1em); /* converts a 14px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 14 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 14 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-lg {
  font-size: calc(20 / 16 * 1em); /* converts a 20px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 20 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 20 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-xl {
  font-size: calc(24 / 16 * 1em); /* converts a 24px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 24 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 24 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-2xl {
  font-size: calc(32 / 16 * 1em); /* converts a 32px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 32 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 32 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-width-auto {
  --fa-width: auto;
}

.fa-fw,
.fa-width-fixed {
  --fa-width: 1.25em;
}

.fa-canvas-square {
  padding-block: 0.125em;
  margin-block-end: -0.125em;
}

.fa-canvas-roomy {
  padding-block: 0.25em;
  padding-inline: 0.125em;
  margin-block-end: -0.25em;
  box-sizing: content-box;
}

.fa-ul {
  list-style-type: none;
  margin-inline-start: var(--fa-li-margin, 2.5em);
  padding-inline-start: 0;
}
.fa-ul > li {
  position: relative;
}

.fa-li {
  inset-inline-start: calc(-1 * var(--fa-li-width, 2em));
  position: absolute;
  text-align: center;
  width: var(--fa-li-width, 2em);
  line-height: inherit;
}

/* Heads Up: Bordered Icons will not be supported in the future!
  - This feature will be deprecated in the next major release of Font Awesome (v8)!
  - You may continue to use it in this version *v7), but it will not be supported in Font Awesome v8.
*/
/* Notes:
* --@{v.$css-prefix}-border-width = 1/16 by default (to render as ~1px based on a 16px default font-size)
* --@{v.$css-prefix}-border-padding =
  ** 3/16 for vertical padding (to give ~2px of vertical whitespace around an icon considering it's vertical alignment)
  ** 4/16 for horizontal padding (to give ~4px of horizontal whitespace around an icon)
*/
.fa-border {
  border-color: var(--fa-border-color, #eee);
  border-radius: var(--fa-border-radius, 0.1em);
  border-style: var(--fa-border-style, solid);
  border-width: var(--fa-border-width, 0.0625em);
  box-sizing: var(--fa-border-box-sizing, content-box);
  padding: var(--fa-border-padding, 0.1875em 0.25em);
}

.fa-pull-left,
.fa-pull-start {
  float: inline-start;
  margin-inline-end: var(--fa-pull-margin, 0.3em);
}

.fa-pull-right,
.fa-pull-end {
  float: inline-end;
  margin-inline-start: var(--fa-pull-margin, 0.3em);
}

.fa-beat {
  animation-name: fa-beat;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-bounce {
  animation-name: fa-bounce;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, cubic-bezier(0.28, 0.84, 0.42, 1));
}

.fa-fade {
  animation-name: fa-fade;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-beat-fade {
  animation-name: fa-beat-fade;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-flip {
  animation-name: fa-flip;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1.5s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-flip-360 {
  animation-name: fa-flip-360;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-shake {
  animation-name: fa-shake;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 0.75s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-spin {
  animation-name: fa-spin;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 2s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, linear);
}

.fa-spin-reverse {
  --fa-animation-direction: reverse;
}

.fa-pulse,
.fa-spin-pulse {
  animation-name: fa-spin;
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, steps(8));
}

.fa-spin-snap {
  animation-name: fa-spin-snap;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 3s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, linear);
}

.fa-spin-snap-4 {
  animation-name: fa-spin-snap-4;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 2.4s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, linear);
}

.fa-spin-snap-8 {
  animation-name: fa-spin-snap-8;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 4s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, linear);
}

.fa-buzz {
  animation-name: fa-buzz;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 0.6s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, linear);
}

.fa-wag {
  animation-name: fa-wag;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 0.9s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-out);
  transform-origin: bottom center;
}

.fa-float {
  animation-name: fa-float;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 3s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
  will-change: transform;
}

.fa-swing {
  animation-name: fa-swing;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1.2s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-out);
  transform-origin: top center;
}

.fa-jello {
  animation-name: fa-jello;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 0.9s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .fa-beat,
  .fa-bounce,
  .fa-fade,
  .fa-beat-fade,
  .fa-flip,
  .fa-flip-360,
  .fa-pulse,
  .fa-shake,
  .fa-spin,
  .fa-spin-pulse,
  .fa-buzz,
  .fa-float,
  .fa-jello,
  .fa-spin-snap,
  .fa-spin-snap-4,
  .fa-spin-snap-8,
  .fa-swing,
  .fa-wag {
    animation: none !important;
    transition: none !important;
  }
}
@keyframes fa-beat {
  0% {
    transform: scale(1);
  }
  25% {
    transform: scale(calc(1.25 * var(--fa-beat-scale, 1.25)));
  }
  45% {
    transform: scale(calc(1.22 * var(--fa-beat-scale, 1.22)));
  }
  65% {
    transform: scale(calc(1.25 * var(--fa-beat-scale, 1.25)));
  }
  90% {
    transform: scale(1);
  }
}
@keyframes fa-bounce {
  0% {
    transform: scale(1, 1) translateY(0);
    animation-timing-function: var(--fa-animation-timing);
  }
  14% {
    transform: scale(var(--fa-bounce-start-scale-x, 1.06), var(--fa-bounce-start-scale-y, 0.94)) translateY(var(--fa-bounce-anticipation, 3px));
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
  }
  32% {
    transform: scale(var(--fa-bounce-jump-scale-x, 0.94), var(--fa-bounce-jump-scale-y, 1.12)) translateY(calc(-1 * var(--fa-bounce-height, 0.5em)));
    animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
  }
  52% {
    transform: scale(1, 1) translateY(calc(-1 * var(--fa-bounce-height, 0.5em) * 1.1));
    animation-timing-function: cubic-bezier(0.5, 0, 1, 0.5);
  }
  70% {
    transform: scale(var(--fa-bounce-land-scale-x, 1.06), var(--fa-bounce-land-scale-y, 0.92)) translateY(0);
    animation-timing-function: cubic-bezier(0.33, 0.33, 0.66, 1);
  }
  85% {
    transform: scale(0.98, 1.04) translateY(calc(-2px * var(--fa-bounce-rebound, 1)));
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
  }
  100% {
    transform: scale(1, 1) translateY(0);
  }
}
@keyframes fa-fade {
  0% {
    opacity: 1;
    transform: scale(1);
    animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
  }
  40% {
    opacity: var(--fa-fade-opacity, 0.4);
    transform: scale(0.98);
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
@keyframes fa-beat-fade {
  0% {
    opacity: var(--fa-beat-fade-opacity, 0.4);
    transform: scale(1);
    animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
  }
  25% {
    opacity: calc(var(--fa-beat-fade-opacity, 0.4) + 0.4);
    transform: scale(var(--fa-beat-fade-scale, 1.28));
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  45% {
    opacity: 1;
    transform: scale(var(--fa-beat-fade-scale, 1.25));
    animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
  65% {
    opacity: calc(var(--fa-beat-fade-opacity, 0.4) + 0.4);
    transform: scale(var(--fa-beat-fade-scale, 1.28));
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  100% {
    opacity: var(--fa-beat-fade-opacity, 0.4);
    transform: scale(1);
  }
}
@keyframes fa-flip {
  0% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), 0deg);
    animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
  }
  8% {
    transform: perspective(2em) scale(var(--fa-flip-anticipation-scale, 0.95)) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), 0deg);
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
  }
  35% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), calc(var(--fa-flip-angle, -360deg) * 0.6));
    animation-timing-function: linear;
  }
  65% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), calc(var(--fa-flip-angle, -360deg) * 0.5));
    animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
  }
  92% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), calc(var(--fa-flip-angle, -360deg) * var(--fa-flip-overshoot, 1.04)));
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
  }
  100% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), var(--fa-flip-angle, -360deg));
  }
}
@keyframes fa-flip-360 {
  0% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), 0deg);
    animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
  }
  8% {
    transform: perspective(2em) scale(var(--fa-flip-anticipation-scale, 0.95)) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), 0deg);
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
  }
  50% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), calc(var(--fa-flip-angle, -360deg) * 0.6));
    animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
  }
  80% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), calc(var(--fa-flip-angle, -360deg) * var(--fa-flip-overshoot, 1.04)));
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
  }
  100% {
    transform: perspective(2em) scale(1) rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), var(--fa-flip-angle, -360deg));
  }
}
@keyframes fa-shake {
  0% {
    transform: rotate(0deg);
    animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
  }
  8% {
    transform: rotate(35deg) translateX(1px);
    animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
  }
  20% {
    transform: rotate(-22deg) translateX(-1px);
    animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
  }
  35% {
    transform: rotate(15deg) translateX(1px);
    animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
  }
  50% {
    transform: rotate(-9deg);
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  65% {
    transform: rotate(5deg);
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  78% {
    transform: rotate(-3deg);
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  90% {
    transform: rotate(1deg);
    animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
  100% {
    transform: rotate(0deg);
  }
}
@keyframes fa-spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
@keyframes fa-spin-snap {
  0% {
    transform: rotate(0deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  12% {
    transform: rotate(60deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  16.67% {
    transform: rotate(60deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  28.67% {
    transform: rotate(120deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  33.33% {
    transform: rotate(120deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  45.33% {
    transform: rotate(180deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  50% {
    transform: rotate(180deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  62% {
    transform: rotate(240deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  66.67% {
    transform: rotate(240deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  78.67% {
    transform: rotate(300deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  83.33% {
    transform: rotate(300deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  95.33% {
    transform: rotate(360deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  100% {
    transform: rotate(360deg);
  }
}
@keyframes fa-spin-snap-4 {
  0% {
    transform: rotate(0deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  15% {
    transform: rotate(90deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  25% {
    transform: rotate(90deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  40% {
    transform: rotate(180deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  50% {
    transform: rotate(180deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  65% {
    transform: rotate(270deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  75% {
    transform: rotate(270deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  90% {
    transform: rotate(360deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  100% {
    transform: rotate(360deg);
  }
}
@keyframes fa-spin-snap-8 {
  0% {
    transform: rotate(0deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  9% {
    transform: rotate(45deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  12.5% {
    transform: rotate(45deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  21.5% {
    transform: rotate(90deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  25% {
    transform: rotate(90deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  34% {
    transform: rotate(135deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  37.5% {
    transform: rotate(135deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  46.5% {
    transform: rotate(180deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  50% {
    transform: rotate(180deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  59% {
    transform: rotate(225deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  62.5% {
    transform: rotate(225deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  71.5% {
    transform: rotate(270deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  75% {
    transform: rotate(270deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  84% {
    transform: rotate(315deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  87.5% {
    transform: rotate(315deg);
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  96.5% {
    transform: rotate(360deg);
    animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
  }
  100% {
    transform: rotate(360deg);
  }
}
@keyframes fa-buzz {
  0% {
    transform: translateX(0) rotate(0deg);
    animation-timing-function: cubic-bezier(0.1, 0, 0.9, 1);
  }
  5% {
    transform: translateX(var(--fa-buzz-distance, 4px)) rotate(0.5deg);
  }
  10% {
    transform: translateX(calc(-1 * var(--fa-buzz-distance, 4px))) rotate(-0.5deg);
  }
  15% {
    transform: translateX(var(--fa-buzz-distance, 4px)) rotate(0.3deg);
  }
  20% {
    transform: translateX(calc(-1 * var(--fa-buzz-distance, 4px))) rotate(-0.3deg);
  }
  25% {
    transform: translateX(calc(var(--fa-buzz-distance, 4px) * 0.7)) rotate(0.2deg);
  }
  30% {
    transform: translateX(calc(-1 * var(--fa-buzz-distance, 4px) * 0.7)) rotate(-0.2deg);
  }
  35% {
    transform: translateX(calc(var(--fa-buzz-distance, 4px) * 0.4)) rotate(0.1deg);
  }
  40% {
    transform: translateX(0) rotate(0deg);
  }
  100% {
    transform: translateX(0) rotate(0deg);
  }
}
@keyframes fa-wag {
  0% {
    transform: rotate(0deg);
    animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
  }
  12% {
    transform: rotate(var(--fa-wag-angle, 12deg));
    animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
  24% {
    transform: rotate(2deg);
    animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
  }
  36% {
    transform: rotate(calc(var(--fa-wag-angle, 12deg) * 0.85));
    animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
  48% {
    transform: rotate(1deg);
    animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
  }
  58% {
    transform: rotate(calc(var(--fa-wag-angle, 12deg) * 0.6));
    animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
  68% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(0deg);
  }
}
@keyframes fa-float {
  0% {
    transform: translateY(0) translateX(0) rotate(0deg) scale(var(--fa-float-squash-x, 1.02), var(--fa-float-squash-y, 0.98));
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
  }
  15% {
    transform: translateY(calc(-0.4 * var(--fa-float-height, 6px))) translateX(var(--fa-float-drift, 1px)) rotate(var(--fa-float-tilt, 1deg)) scale(1, 1);
    animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
  }
  35% {
    transform: translateY(calc(-1 * var(--fa-float-height, 6px))) translateX(0) rotate(0deg) scale(var(--fa-float-stretch-x, 0.98), var(--fa-float-stretch-y, 1.03));
    animation-timing-function: cubic-bezier(0.5, 0, 0.5, 0);
  }
  50% {
    transform: translateY(calc(-0.92 * var(--fa-float-height, 6px))) translateX(calc(-0.5 * var(--fa-float-drift, 1px))) rotate(calc(-0.5 * var(--fa-float-tilt, 1deg))) scale(0.995, 1.01);
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
  }
  70% {
    transform: translateY(calc(-0.3 * var(--fa-float-height, 6px))) translateX(calc(-1 * var(--fa-float-drift, 1px))) rotate(calc(-1 * var(--fa-float-tilt, 1deg))) scale(1, 1);
    animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
  }
  90% {
    transform: translateY(calc(0.05 * var(--fa-float-height, 6px))) translateX(0) rotate(0deg) scale(var(--fa-float-squash-x, 1.02), var(--fa-float-squash-y, 0.98));
    animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
  }
  100% {
    transform: translateY(0) translateX(0) rotate(0deg) scale(var(--fa-float-squash-x, 1.02), var(--fa-float-squash-y, 0.98));
  }
}
@keyframes fa-swing {
  0% {
    transform: rotate(0deg);
    animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
  }
  8% {
    transform: rotate(var(--fa-swing-angle, 22deg));
    animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
  }
  18% {
    transform: rotate(calc(-1 * var(--fa-swing-angle, 22deg) * 0.85));
    animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
  }
  28% {
    transform: rotate(calc(var(--fa-swing-angle, 22deg) * 0.65));
    animation-timing-function: cubic-bezier(0.35, 0, 0.65, 1);
  }
  38% {
    transform: rotate(calc(-1 * var(--fa-swing-angle, 22deg) * 0.45));
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  48% {
    transform: rotate(calc(var(--fa-swing-angle, 22deg) * 0.25));
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  56% {
    transform: rotate(calc(-1 * var(--fa-swing-angle, 22deg) * 0.1));
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  64% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(0deg);
  }
}
@keyframes fa-jello {
  0% {
    transform: scale(1, 1);
    animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
  }
  12% {
    transform: scale(var(--fa-jello-scale-x, 1.15), calc(2 - var(--fa-jello-scale-x, 1.15)));
    animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
  }
  24% {
    transform: scale(calc(2 - var(--fa-jello-scale-y, 1.12)), var(--fa-jello-scale-y, 1.12));
    animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
  }
  36% {
    transform: scale(calc(1 + (var(--fa-jello-scale-x, 1.15) - 1) * 0.5), calc(2 - (1 + (var(--fa-jello-scale-x, 1.15) - 1) * 0.5)));
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  48% {
    transform: scale(calc(2 - (1 + (var(--fa-jello-scale-y, 1.12) - 1) * 0.3)), calc(1 + (var(--fa-jello-scale-y, 1.12) - 1) * 0.3));
    animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
  }
  58% {
    transform: scale(1.02, 0.98);
    animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
  68% {
    transform: scale(1, 1);
  }
  100% {
    transform: scale(1, 1);
  }
}
.fa-rotate-90 {
  transform: rotate(90deg);
}

.fa-rotate-180 {
  transform: rotate(180deg);
}

.fa-rotate-270 {
  transform: rotate(270deg);
}

.fa-flip-horizontal {
  transform: scale(-1, 1);
}

.fa-flip-vertical {
  transform: scale(1, -1);
}

.fa-flip-both,
.fa-flip-horizontal.fa-flip-vertical {
  transform: scale(-1, -1);
}

.fa-rotate-by {
  transform: rotate(var(--fa-rotate-angle, 0));
}

.svg-inline--fa .fa-primary {
  fill: var(--fa-primary-color, currentColor);
  opacity: var(--fa-primary-opacity, 1);
}

.svg-inline--fa .fa-secondary {
  fill: var(--fa-secondary-color, currentColor);
  opacity: var(--fa-secondary-opacity, 0.4);
}

.svg-inline--fa.fa-swap-opacity .fa-primary {
  opacity: var(--fa-secondary-opacity, 0.4);
}

.svg-inline--fa.fa-swap-opacity .fa-secondary {
  opacity: var(--fa-primary-opacity, 1);
}

.svg-inline--fa mask .fa-primary,
.svg-inline--fa mask .fa-secondary {
  fill: black;
}

.svg-inline--fa.fa-inverse {
  fill: var(--fa-inverse, #fff);
}

.fa-stack {
  display: inline-block;
  height: 2em;
  line-height: 2em;
  position: relative;
  vertical-align: middle;
  width: 2.5em;
}

.fa-inverse {
  color: var(--fa-inverse, #fff);
}

.svg-inline--fa.fa-stack-1x {
  --fa-width: 1.25em;
  height: 1em;
  width: var(--fa-width);
}
.svg-inline--fa.fa-stack-2x {
  --fa-width: 2.5em;
  height: 2em;
  width: var(--fa-width);
}

.fa-stack-1x,
.fa-stack-2x {
  inset: 0;
  margin: auto;
  position: absolute;
  z-index: var(--fa-stack-z-index, auto);
}`;function qc(){var e=ec,t=tc,n=Z.cssPrefix,r=Z.replacementClass,i=Kc;if(n!==e||r!==t){var a=RegExp(`\\.${e}\\-`,`g`),o=RegExp(`\\--${e}\\-`,`g`),s=RegExp(`\\.${t}`,`g`);i=i.replace(a,`.${n}-`).replace(o,`--${n}-`).replace(s,`.${r}`)}return i}var Jc=!1;function Yc(){Z.autoAddCss&&!Jc&&(Fc(qc()),Jc=!0)}var Xc={mixout:function(){return{dom:{css:qc,insertCss:Yc}}},hooks:function(){return{beforeDOMElementCreation:function(){Yc()},beforeI2svg:function(){Yc()}}}},Zc=wo||{};Zc[Qs]||(Zc[Qs]={}),Zc[Qs].styles||(Zc[Qs].styles={}),Zc[Qs].hooks||(Zc[Qs].hooks={}),Zc[Qs].shims||(Zc[Qs].shims=[]);var Qc=Zc[Qs],$c=[],el=function(){Y.removeEventListener(`DOMContentLoaded`,el),tl=1,$c.map(function(e){return e()})},tl=!1;Do&&(tl=(Y.documentElement.doScroll?/^loaded|^c/:/^loaded|^i|^c/).test(Y.readyState),tl||Y.addEventListener(`DOMContentLoaded`,el));function nl(e){Do&&(tl?setTimeout(e,0):$c.push(e))}function rl(e){var t=e.tag,n=e.attributes,r=n===void 0?{}:n,i=e.children,a=i===void 0?[]:i;return typeof e==`string`?Bc(e):`<${t} ${Vc(r)}>${a.map(rl).join(``)}</${t}>`}function il(e,t,n){if(e&&e[t]&&e[t][n])return{prefix:t,iconName:n,icon:e[t][n]}}var al=function(e,t){return function(n,r,i,a){return e.call(t,n,r,i,a)}},ol=function(e,t,n,r){var i=Object.keys(e),a=i.length,o=r===void 0?t:al(t,r),s,c,l;for(n===void 0?(s=1,l=e[i[0]]):(s=0,l=n);s<a;s++)c=i[s],l=o(l,e[c],c,e);return l};function sl(e){return fo(e).length===1?e.codePointAt(0).toString(16):null}function cl(e){return Object.keys(e).reduce(function(t,n){var r=e[n];return r.icon?t[r.iconName]=r.icon:t[n]=r,t},{})}function ll(e,t){var n=(arguments.length>2&&arguments[2]!==void 0?arguments[2]:{}).skipHooks,r=n!==void 0&&n,i=cl(t);typeof Qc.hooks.addPack==`function`&&!r?Qc.hooks.addPack(e,cl(t)):Qc.styles[e]=J(J({},Qc.styles[e]||{}),i),e===`fas`&&ll(`fa`,t)}var ul=Qc.styles,dl=Qc.shims,fl=Object.keys(vc),pl=fl.reduce(function(e,t){return e[t]=Object.keys(vc[t]),e},{}),ml=null,hl={},gl={},_l={},vl={},yl={};function bl(e){return~Tc.indexOf(e)}function xl(e,t){var n=t.split(`-`),r=n[0],i=n.slice(1).join(`-`);return r===e&&i!==``&&!bl(i)?i:null}var Sl=function(){var e=function(e){return ol(ul,function(t,n,r){return t[r]=ol(n,e,{}),t},{})};hl=e(function(e,t,n){return t[3]&&(e[t[3]]=n),t[2]&&t[2].filter(function(e){return typeof e==`number`}).forEach(function(t){e[t.toString(16)]=n}),e}),gl=e(function(e,t,n){return e[n]=n,t[2]&&t[2].filter(function(e){return typeof e==`string`}).forEach(function(t){e[t]=n}),e}),yl=e(function(e,t,n){var r=t[2];return e[n]=n,r.forEach(function(t){e[t]=n}),e});var t=`far`in ul||Z.autoFetchSvg,n=ol(dl,function(e,n){var r=n[0],i=n[1],a=n[2];return i===`far`&&!t&&(i=`fas`),typeof r==`string`&&(e.names[r]={prefix:i,iconName:a}),typeof r==`number`&&(e.unicodes[r.toString(16)]={prefix:i,iconName:a}),e},{names:{},unicodes:{}});_l=n.names,vl=n.unicodes,ml=jl(Z.styleDefault,{family:Z.familyDefault})};Mc(function(e){ml=jl(e.styleDefault,{family:Z.familyDefault})}),Sl();function Cl(e,t){return(hl[e]||{})[t]}function wl(e,t){return(gl[e]||{})[t]}function Tl(e,t){return(yl[e]||{})[t]}function El(e){return _l[e]||{prefix:null,iconName:null}}function Dl(e){var t=vl[e],n=Cl(`fas`,e);return t||(n?{prefix:`fas`,iconName:n}:null)||{prefix:null,iconName:null}}function Ol(){return ml}var kl=function(){return{prefix:null,iconName:null,rest:[]}};function Al(e){var t=X,n=fl.reduce(function(e,t){return e[t]=`${Z.cssPrefix}-${t}`,e},{});return Os.forEach(function(r){(e.includes(n[r])||e.some(function(e){return pl[r].includes(e)}))&&(t=r)}),t}function jl(e){var t=(arguments.length>1&&arguments[1]!==void 0?arguments[1]:{}).family,n=t===void 0?X:t,r=mc[n][e];if(n===Fo&&!e)return`fad`;var i=gc[n][e]||gc[n][r],a=e in Qc.styles?e:null;return i||a||null}function Ml(e){var t=[],n=null;return e.forEach(function(e){var r=xl(Z.cssPrefix,e);r?n=r:e&&t.push(e)}),{iconName:n,rest:t}}function Nl(e){return e.sort().filter(function(e,t,n){return n.indexOf(e)===t})}var Pl=Ks.concat(Ns);function Fl(e){var t=(arguments.length>1&&arguments[1]!==void 0?arguments[1]:{}).skipLookups,n=t!==void 0&&t,r=null,i=Nl(e.filter(function(e){return Pl.includes(e)})),a=Nl(e.filter(function(e){return!Pl.includes(e)})),o=uo(i.filter(function(e){return r=e,!Po.includes(e)}),1)[0],s=o===void 0?null:o,c=Al(i),l=J(J({},Ml(a)),{},{prefix:jl(s,{family:c})});return J(J(J({},l),zl({values:e,family:c,styles:ul,config:Z,canonical:l,givenPrefix:r})),Il(n,r,l))}function Il(e,t,n){var r=n.prefix,i=n.iconName;if(e||!r||!i)return{prefix:r,iconName:i};var a=t===`fa`?El(i):{},o=Tl(r,i);return i=a.iconName||o||i,r=a.prefix||r,r===`far`&&!ul.far&&ul.fas&&!Z.autoFetchSvg&&(r=`fas`),{prefix:r,iconName:i}}var Ll=Os.filter(function(e){return e!==X||e!==Fo}),Rl=Object.keys(Gs).filter(function(e){return e!==X}).map(function(e){return Object.keys(Gs[e])}).flat();function zl(e){var t=e.values,n=e.family,r=e.canonical,i=e.givenPrefix,a=i===void 0?``:i,o=e.styles,s=o===void 0?{}:o,c=e.config,l=c===void 0?{}:c,u=n===Fo,d=t.includes(`fa-duotone`)||t.includes(`fad`),f=l.familyDefault===`duotone`,p=r.prefix===`fad`||r.prefix===`fa-duotone`;return!u&&(d||f||p)&&(r.prefix=`fad`),(t.includes(`fa-brands`)||t.includes(`fab`))&&(r.prefix=`fab`),!r.prefix&&Ll.includes(n)&&(Object.keys(s).find(function(e){return Rl.includes(e)})||l.autoFetchSvg)&&(r.prefix=js.get(n).defaultShortPrefixId,r.iconName=Tl(r.prefix,r.iconName)||r.iconName),(r.prefix===`fa`||a===`fa`)&&(r.prefix=Ol()||`fas`),r}var Bl=function(){function e(){to(this,e),this.definitions={}}return ro(e,[{key:`add`,value:function(){var e=this,t=[...arguments].reduce(this._pullDefinitions,{});Object.keys(t).forEach(function(n){e.definitions[n]=J(J({},e.definitions[n]||{}),t[n]),ll(n,t[n]);var r=vc[X][n];r&&ll(r,t[n]),Sl()})}},{key:`reset`,value:function(){this.definitions={}}},{key:`_pullDefinitions`,value:function(e,t){var n=t.prefix&&t.iconName&&t.icon?{0:t}:t;return Object.keys(n).map(function(t){var r=n[t],i=r.prefix,a=r.iconName,o=r.icon,s=o[2];e[i]||(e[i]={}),s.length>0&&s.forEach(function(t){typeof t==`string`&&(e[i][t]=o)}),e[i][a]=o}),e}}])}(),Vl=[],Hl={},Ul={},Wl=Object.keys(Ul);function Gl(e,t){var n=t.mixoutsTo;return Vl=e,Hl={},Object.keys(Ul).forEach(function(e){Wl.indexOf(e)===-1&&delete Ul[e]}),Vl.forEach(function(e){var t=e.mixout?e.mixout():{};if(Object.keys(t).forEach(function(e){typeof t[e]==`function`&&(n[e]=t[e]),ho(t[e])===`object`&&Object.keys(t[e]).forEach(function(r){n[e]||(n[e]={}),n[e][r]=t[e][r]})}),e.hooks){var r=e.hooks();Object.keys(r).forEach(function(e){Hl[e]||(Hl[e]=[]),Hl[e].push(r[e])})}e.provides&&e.provides(Ul)}),n}function Kl(e,t){var n=[...arguments].slice(2);return(Hl[e]||[]).forEach(function(e){t=e.apply(null,[t].concat(n))}),t}function ql(e){var t=[...arguments].slice(1);(Hl[e]||[]).forEach(function(e){e.apply(null,t)})}function Jl(){var e=arguments[0],t=Array.prototype.slice.call(arguments,1);return Ul[e]?Ul[e].apply(null,t):void 0}function Yl(e){e.prefix===`fa`&&(e.prefix=`fas`);var t=e.iconName,n=e.prefix||Ol();if(t)return t=Tl(n,t)||t,il(Xl.definitions,n,t)||il(Qc.styles,n,t)}var Xl=new Bl,Zl={noAuto:function(){Z.autoReplaceSvg=!1,Z.observeMutations=!1,ql(`noAuto`)},config:Z,dom:{i2svg:function(){var e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{};return Do?(ql(`beforeI2svg`,e),Jl(`pseudoElements2svg`,e),Jl(`i2svg`,e)):Promise.reject(Error(`Operation requires a DOM of some kind.`))},watch:function(){var e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{},t=e.autoReplaceSvgRoot;Z.autoReplaceSvg===!1&&(Z.autoReplaceSvg=!0),Z.observeMutations=!0,nl(function(){Ql({autoReplaceSvgRoot:t}),ql(`watch`,e)})}},parse:{icon:function(e){if(e===null)return null;if(ho(e)===`object`&&e.prefix&&e.iconName)return{prefix:e.prefix,iconName:Tl(e.prefix,e.iconName)||e.iconName};if(Array.isArray(e)&&e.length===2){var t=e[1].indexOf(`fa-`)===0?e[1].slice(3):e[1],n=jl(e[0]);return{prefix:n,iconName:Tl(n,t)||t}}if(typeof e==`string`&&(e.indexOf(`${Z.cssPrefix}-`)>-1||e.match(bc))){var r=Fl(e.split(` `),{skipLookups:!0});return{prefix:r.prefix||Ol(),iconName:Tl(r.prefix,r.iconName)||r.iconName}}if(typeof e==`string`){var i=Ol();return{prefix:i,iconName:Tl(i,e)||e}}}},library:Xl,findIconDefinition:Yl,toHtml:rl},Ql=function(){var e=(arguments.length>0&&arguments[0]!==void 0?arguments[0]:{}).autoReplaceSvgRoot,t=e===void 0?Y:e;(Object.keys(Qc.styles).length>0||Z.autoFetchSvg)&&Do&&Z.autoReplaceSvg&&Zl.dom.i2svg({node:t})};function $l(e,t){return Object.defineProperty(e,"abstract",{get:t}),Object.defineProperty(e,"html",{get:function(){return e.abstract.map(function(e){return rl(e)})}}),Object.defineProperty(e,"node",{get:function(){if(Do){var t=Y.createElement(`div`);return t.innerHTML=e.html,t.children}}}),e}function eu(e){var t=e.children,n=e.main,r=e.mask,i=e.attributes,a=e.styles,o=e.transform;if(Uc(o)&&n.found&&!r.found){var s={x:n.width/n.height/2,y:.5};i.style=Hc(J(J({},a),{},{"transform-origin":`${s.x+o.x/16}em ${s.y+o.y/16}em`}))}return[{tag:`svg`,attributes:i,children:t}]}function tu(e){var t=e.prefix,n=e.iconName,r=e.children,i=e.attributes,a=e.symbol,o=a===!0?`${t}-${Z.cssPrefix}-${n}`:a;return[{tag:`svg`,attributes:{style:`display: none;`},children:[{tag:`symbol`,attributes:J(J({},i),{},{id:o}),children:r}]}]}function nu(e){return[`aria-label`,`aria-labelledby`,`title`,`role`].some(function(t){return t in e})}function ru(e){var t=e.icons,n=t.main,r=t.mask,i=e.prefix,a=e.iconName,o=e.transform,s=e.symbol,c=e.maskId,l=e.extra,u=e.watchable,d=u!==void 0&&u,f=r.found?r:n,p=f.width,m=f.height,h=[Z.replacementClass,a?`${Z.cssPrefix}-${a}`:``].filter(function(e){return l.classes.indexOf(e)===-1}).filter(function(e){return e!==``||!!e}).concat(l.classes).join(` `),g={children:[],attributes:J(J({},l.attributes),{},{"data-prefix":i,"data-icon":a,class:h,role:l.attributes.role||`img`,viewBox:`0 0 ${p} ${m}`})};!nu(l.attributes)&&!l.attributes[`aria-hidden`]&&(g.attributes[`aria-hidden`]=`true`),d&&(g.attributes[nc]=``);var _=J(J({},g),{},{prefix:i,iconName:a,main:n,mask:r,maskId:c,transform:o,symbol:s,styles:J({},l.styles)}),v=r.found&&n.found?Jl(`generateAbstractMask`,_)||{children:[],attributes:{}}:Jl(`generateAbstractIcon`,_)||{children:[],attributes:{}},y=v.children,b=v.attributes;return _.children=y,_.attributes=b,s?tu(_):eu(_)}function iu(e){var t=e.content,n=e.width,r=e.height,i=e.transform,a=e.extra,o=e.watchable,s=o!==void 0&&o,c=J(J({},a.attributes),{},{class:a.classes.join(` `)});s&&(c[nc]=``);var l=J({},a.styles);Uc(i)&&(l.transform=Gc({transform:i,startCentered:!0,width:n,height:r}),l[`-webkit-transform`]=l.transform);var u=Hc(l);u.length>0&&(c.style=u);var d=[];return d.push({tag:`span`,attributes:c,children:[t]}),d}function au(e){var t=e.content,n=e.extra,r=J(J({},n.attributes),{},{class:n.classes.join(` `)}),i=Hc(n.styles);i.length>0&&(r.style=i);var a=[];return a.push({tag:`span`,attributes:r,children:[t]}),a}var ou=Qc.styles;function su(e){var t=e[0],n=e[1],r=uo(e.slice(4),1)[0],i=null;return i=Array.isArray(r)?{tag:`g`,attributes:{class:`${Z.cssPrefix}-${wc.GROUP}`},children:[{tag:`path`,attributes:{class:`${Z.cssPrefix}-${wc.SECONDARY}`,fill:`currentColor`,d:r[0]}},{tag:`path`,attributes:{class:`${Z.cssPrefix}-${wc.PRIMARY}`,fill:`currentColor`,d:r[1]}}]}:{tag:`path`,attributes:{fill:`currentColor`,d:r}},{found:!0,width:t,height:n,icon:i}}var cu={found:!1,width:512,height:512};function lu(e,t){!dc&&!Z.showMissingIcons&&e&&console.error(`Icon with name "${e}" and prefix "${t}" is missing.`)}function uu(e,t){var n=t;return t===`fa`&&Z.styleDefault!==null&&(t=Ol()),new Promise(function(r,i){if(n===`fa`){var a=El(e)||{};e=a.iconName||e,t=a.prefix||t}if(e&&t&&ou[t]&&ou[t][e]){var o=ou[t][e];return r(su(o))}lu(e,t),r(J(J({},cu),{},{icon:Z.showMissingIcons&&e&&Jl(`missingIconAbstract`)||{}}))})}var du=function(){},fu=Z.measurePerformance&&Eo&&Eo.mark&&Eo.measure?Eo:{mark:du,measure:du},pu=`FA "7.3.1"`,mu=function(e){return fu.mark(`${pu} ${e} begins`),function(){return hu(e)}},hu=function(e){fu.mark(`${pu} ${e} ends`),fu.measure(`${pu} ${e}`,`${pu} ${e} begins`,`${pu} ${e} ends`)},gu={begin:mu,end:hu},_u=function(){};function vu(e){return typeof(e.getAttribute?e.getAttribute(nc):null)==`string`}function yu(e){var t=e.getAttribute?e.getAttribute(ac):null,n=e.getAttribute?e.getAttribute(oc):null;return t&&n}function bu(e){return e&&e.classList&&e.classList.contains&&e.classList.contains(Z.replacementClass)}function xu(){return Z.autoReplaceSvg===!0?Eu.replace:Eu[Z.autoReplaceSvg]||Eu.replace}function Su(e){return Y.createElementNS(`http://www.w3.org/2000/svg`,e)}function Cu(e){return Y.createElement(e)}function wu(e){var t=(arguments.length>1&&arguments[1]!==void 0?arguments[1]:{}).ceFn,n=t===void 0?e.tag===`svg`?Su:Cu:t;if(typeof e==`string`)return Y.createTextNode(e);var r=n(e.tag);return Object.keys(e.attributes||[]).forEach(function(t){r.setAttribute(t,e.attributes[t])}),(e.children||[]).forEach(function(e){r.appendChild(wu(e,{ceFn:n}))}),r}function Tu(e){var t=` ${e.outerHTML} `;return t=`${t}Font Awesome fontawesome.com `,t}var Eu={replace:function(e){var t=e[0];if(t.parentNode){if(e[1].forEach(function(e){t.parentNode.insertBefore(wu(e),t)}),t.getAttribute(nc)===null&&Z.keepOriginalSource){var n=Y.createComment(Tu(t));t.parentNode.replaceChild(n,t)}else t.remove()}},nest:function(e){var t=e[0],n=e[1];if(~zc(t).indexOf(Z.replacementClass))return Eu.replace(e);var r=RegExp(`${Z.cssPrefix}-.*`);if(delete n[0].attributes.id,n[0].attributes.class){var i=n[0].attributes.class.split(` `).reduce(function(e,t){return t===Z.replacementClass||t.match(r)?e.toSvg.push(t):e.toNode.push(t),e},{toNode:[],toSvg:[]});n[0].attributes.class=i.toSvg.join(` `),i.toNode.length===0?t.removeAttribute(`class`):t.setAttribute(`class`,i.toNode.join(` `))}var a=n.map(function(e){return rl(e)}).join(`
`);t.setAttribute(nc,``),t.innerHTML=a}};function Du(e){e()}function Ou(e,t){var n=typeof t==`function`?t:_u;if(e.length===0)n();else{var r=Du;Z.mutateApproach===cc&&(r=wo.requestAnimationFrame||Du),r(function(){var t=xu(),r=gu.begin(`mutate`);e.map(t),r(),n()})}}var ku=!1;function Au(){ku=!0}function ju(){ku=!1}var Mu=null;function Nu(e){if(To&&Z.observeMutations){var t=e.treeCallback,n=t===void 0?_u:t,r=e.nodeCallback,i=r===void 0?_u:r,a=e.pseudoElementsCallback,o=a===void 0?_u:a,s=e.observeMutationsRoot,c=s===void 0?Y:s;Mu=new To(function(e){if(!ku){var t=Ol();Rc(e).forEach(function(e){if(e.type===`childList`&&e.addedNodes.length>0&&!vu(e.addedNodes[0])&&(Z.searchPseudoElements&&o(e.target),n(e.target)),e.type===`attributes`&&e.target.parentNode&&Z.searchPseudoElements&&o([e.target],!0),e.type===`attributes`&&vu(e.target)&&~Cc.indexOf(e.attributeName)){if(e.attributeName===`class`&&yu(e.target)){var r=Fl(zc(e.target)),a=r.prefix,s=r.iconName;e.target.setAttribute(ac,a||t),s&&e.target.setAttribute(oc,s)}else bu(e.target)&&i(e.target)}})}}),Do&&Mu.observe(c,{childList:!0,attributes:!0,characterData:!0,subtree:!0})}}function Pu(){Mu&&Mu.disconnect()}function Fu(e){var t=e.getAttribute(`style`),n=[];return t&&(n=t.split(`;`).reduce(function(e,t){var n=t.split(`:`),r=n[0],i=n.slice(1);return r&&i.length>0&&(e[r]=i.join(`:`).trim()),e},{})),n}function Iu(e){var t=e.getAttribute(`data-prefix`),n=e.getAttribute(`data-icon`),r=e.innerText===void 0?``:e.innerText.trim(),i=Fl(zc(e));return i.prefix||=Ol(),t&&n&&(i.prefix=t,i.iconName=n),i.iconName&&i.prefix||(i.prefix&&r.length>0&&(i.iconName=wl(i.prefix,e.innerText)||Cl(i.prefix,sl(e.innerText))),!i.iconName&&Z.autoFetchSvg&&e.firstChild&&e.firstChild.nodeType===Node.TEXT_NODE&&(i.iconName=e.firstChild.data)),i}function Lu(e){return Rc(e.attributes).reduce(function(e,t){return e.name!==`class`&&e.name!==`style`&&(e[t.name]=t.value),e},{})}function Ru(){return{iconName:null,prefix:null,transform:Pc,symbol:!1,mask:{iconName:null,prefix:null,rest:[]},maskId:null,extra:{classes:[],styles:{},attributes:{}}}}function zu(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{styleParser:!0},n=Iu(e),r=n.iconName,i=n.prefix,a=n.rest,o=Lu(e),s=Kl(`parseNodeAttributes`,{},e);return J({iconName:r,prefix:i,transform:Pc,mask:{iconName:null,prefix:null,rest:[]},maskId:null,symbol:!1,extra:{classes:a,styles:t.styleParser?Fu(e):[],attributes:o}},s)}var Bu=Qc.styles;function Vu(e){var t=Z.autoReplaceSvg===`nest`?zu(e,{styleParser:!1}):zu(e);return~t.extra.classes.indexOf(xc)?Jl(`generateLayersText`,e,t):Jl(`generateSvgReplacementMutation`,e,t)}function Hu(){return[].concat(fo(Ns),fo(Ks))}function Uu(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:null;if(!Do)return Promise.resolve();var n=Y.documentElement.classList,r=function(e){return n.add(`${sc}-${e}`)},i=function(e){return n.remove(`${sc}-${e}`)},a=Z.autoFetchSvg?Hu():Po.concat(Object.keys(Bu));a.includes(`fa`)||a.push(`fa`);var o=[`.${xc}:not([${nc}])`].concat(a.map(function(e){return`.${e}:not([${nc}])`})).join(`, `);if(o.length===0)return Promise.resolve();var s=[];try{s=Rc(e.querySelectorAll(o))}catch{}if(s.length>0)r(`pending`),i(`complete`);else return Promise.resolve();var c=gu.begin(`onTree`),l=s.reduce(function(e,t){try{var n=Vu(t);n&&e.push(n)}catch(e){dc||e.name===`MissingIcon`&&console.error(e)}return e},[]);return new Promise(function(e,n){Promise.all(l).then(function(n){Ou(n,function(){r(`active`),r(`complete`),i(`pending`),typeof t==`function`&&t(),c(),e()})}).catch(function(e){c(),n(e)})})}function Wu(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:null;Vu(e).then(function(e){e&&Ou([e],t)})}function Gu(e){return function(t){var n=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},r=(t||{}).icon?t:Yl(t||{}),i=n.mask;return i&&=(i||{}).icon?i:Yl(i||{}),e(r,J(J({},n),{},{mask:i}))}}var Ku=function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.transform,r=n===void 0?Pc:n,i=t.symbol,a=i!==void 0&&i,o=t.mask,s=o===void 0?null:o,c=t.maskId,l=c===void 0?null:c,u=t.classes,d=u===void 0?[]:u,f=t.attributes,p=f===void 0?{}:f,m=t.styles,h=m===void 0?{}:m;if(e){var g=e.prefix,_=e.iconName,v=e.icon;return $l(J({type:`icon`},e),function(){return ql(`beforeDOMElementCreation`,{iconDefinition:e,params:t}),ru({icons:{main:su(v),mask:s?su(s.icon):{found:!1,width:null,height:null,icon:{}}},prefix:g,iconName:_,transform:J(J({},Pc),r),symbol:a,maskId:l,extra:{attributes:p,styles:h,classes:d}})})}},qu={mixout:function(){return{icon:Gu(Ku)}},hooks:function(){return{mutationObserverCallbacks:function(e){return e.treeCallback=Uu,e.nodeCallback=Wu,e}}},provides:function(e){e.i2svg=function(e){var t=e.node,n=t===void 0?Y:t,r=e.callback;return Uu(n,r===void 0?function(){}:r)},e.generateSvgReplacementMutation=function(e,t){var n=t.iconName,r=t.prefix,i=t.transform,a=t.symbol,o=t.mask,s=t.maskId,c=t.extra;return new Promise(function(t,l){Promise.all([uu(n,r),o.iconName?uu(o.iconName,o.prefix):Promise.resolve({found:!1,width:512,height:512,icon:{}})]).then(function(o){var l=uo(o,2),u=l[0],d=l[1];t([e,ru({icons:{main:u,mask:d},prefix:r,iconName:n,transform:i,symbol:a,maskId:s,extra:c,watchable:!0})])}).catch(l)})},e.generateAbstractIcon=function(e){var t=e.children,n=e.attributes,r=e.main,i=e.transform,a=e.styles,o=Hc(a);o.length>0&&(n.style=o);var s;return Uc(i)&&(s=Jl(`generateAbstractTransformGrouping`,{main:r,transform:i,containerWidth:r.width,iconWidth:r.width})),t.push(s||r.icon),{children:t,attributes:n}}}},Ju={mixout:function(){return{layer:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.classes,r=n===void 0?[]:n;return $l({type:`layer`},function(){ql(`beforeDOMElementCreation`,{assembler:e,params:t});var n=[];return e(function(e){Array.isArray(e)?e.map(function(e){n=n.concat(e.abstract)}):n=n.concat(e.abstract)}),[{tag:`span`,attributes:{class:[`${Z.cssPrefix}-layers`].concat(fo(r)).join(` `)},children:n}]})}}}},Yu={mixout:function(){return{counter:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.title,r=n===void 0?null:n,i=t.classes,a=i===void 0?[]:i,o=t.attributes,s=o===void 0?{}:o,c=t.styles,l=c===void 0?{}:c;return $l({type:`counter`,content:e},function(){return ql(`beforeDOMElementCreation`,{content:e,params:t}),au({content:e.toString(),title:r,extra:{attributes:s,styles:l,classes:[`${Z.cssPrefix}-layers-counter`].concat(fo(a))}})})}}}},Xu={mixout:function(){return{text:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.transform,r=n===void 0?Pc:n,i=t.classes,a=i===void 0?[]:i,o=t.attributes,s=o===void 0?{}:o,c=t.styles,l=c===void 0?{}:c;return $l({type:`text`,content:e},function(){return ql(`beforeDOMElementCreation`,{content:e,params:t}),iu({content:e,transform:J(J({},Pc),r),extra:{attributes:s,styles:l,classes:[`${Z.cssPrefix}-layers-text`].concat(fo(a))}})})}}},provides:function(e){e.generateLayersText=function(e,t){var n=t.transform,r=t.extra,i=null,a=null;if(Oo){var o=parseInt(getComputedStyle(e).fontSize,10),s=e.getBoundingClientRect();i=s.width/o,a=s.height/o}return Promise.resolve([e,iu({content:e.innerHTML,width:i,height:a,transform:n,extra:r,watchable:!0})])}}},Zu=RegExp(`"`,`ug`),Qu=[1105920,1112319],$u=J(J(J(J({},{FontAwesome:{normal:`fas`,400:`fas`}}),As),Zs),Ls),ed=Object.keys($u).reduce(function(e,t){return e[t.toLowerCase()]=$u[t],e},{}),td=Object.keys(ed).reduce(function(e,t){var n=ed[t];return e[t]=n[900]||fo(Object.entries(n))[0][1],e},{});function nd(e){return sl(fo(e.replace(Zu,``))[0]||``)}function rd(e){var t=e.getPropertyValue(`font-feature-settings`).includes(`ss01`),n=e.getPropertyValue(`content`).replace(Zu,``),r=n.codePointAt(0),i=r>=Qu[0]&&r<=Qu[1],a=n.length===2&&n[0]===n[1];return i||a||t}function id(e,t){var n=e.replace(/^['"]|['"]$/g,``).toLowerCase(),r=parseInt(t),i=isNaN(r)?`normal`:r;return(ed[n]||{})[i]||td[n]}function ad(e,t){var n=`${ic}${t.replace(`:`,`-`)}`;return new Promise(function(r,i){if(e.getAttribute(n)!==null)return r();var a=Rc(e.children).filter(function(e){return e.getAttribute(rc)===t})[0],o=wo.getComputedStyle(e,t),s=o.getPropertyValue(`font-family`),c=s.match(Sc),l=o.getPropertyValue(`font-weight`),u=o.getPropertyValue(`content`);if(a&&!c)return e.removeChild(a),r();if(c&&u!==`none`&&u!==``){var d=o.getPropertyValue(`content`),f=id(s,l),p=nd(d),m=c[0].startsWith(`FontAwesome`),h=rd(o),g=Cl(f,p),_=g;if(m){var v=Dl(p);v.iconName&&v.prefix&&(g=v.iconName,f=v.prefix)}if(g&&!h&&(!a||a.getAttribute(ac)!==f||a.getAttribute(oc)!==_)){e.setAttribute(n,_),a&&e.removeChild(a);var y=Ru(),b=y.extra;b.attributes[rc]=t,uu(g,f).then(function(i){var a=ru(J(J({},y),{},{icons:{main:i,mask:kl()},prefix:f,iconName:_,extra:b,watchable:!0})),o=Y.createElementNS(`http://www.w3.org/2000/svg`,`svg`);t===`::before`?e.insertBefore(o,e.firstChild):e.appendChild(o),o.outerHTML=a.map(function(e){return rl(e)}).join(`
`),e.removeAttribute(n),r()}).catch(i)}else r()}else r()})}function od(e){return Promise.all([ad(e,`::before`),ad(e,`::after`)])}function sd(e){return e.parentNode!==document.head&&!~lc.indexOf(e.tagName.toUpperCase())&&!e.getAttribute(rc)&&(!e.parentNode||e.parentNode.tagName!==`svg`)}var cd=function(e){return!!e&&uc.some(function(t){return e.includes(t)})},ld=function(e){if(!e)return[];var t=new Set,n=e.split(/,(?![^()]*\))/).map(function(e){return e.trim()});n=n.flatMap(function(e){return e.includes(`(`)?e:e.split(`,`).map(function(e){return e.trim()})});var r=io(n),i;try{for(r.s();!(i=r.n()).done;){var a=i.value;if(cd(a)){var o=uc.reduce(function(e,t){return e.replace(t,``)},a);o!==``&&o!==`*`&&t.add(o)}}}catch(e){r.e(e)}finally{r.f()}return t};function ud(e){var t=arguments.length>1&&arguments[1]!==void 0&&arguments[1];if(Do){var n;if(t)n=e;else if(Z.searchPseudoElementsFullScan)n=e.querySelectorAll(`*`);else{var r=new Set,i=io(document.styleSheets),a;try{for(i.s();!(a=i.n()).done;){var o=a.value;try{var s=io(o.cssRules),c;try{for(s.s();!(c=s.n()).done;){var l=c.value,u=io(ld(l.selectorText)),d;try{for(u.s();!(d=u.n()).done;){var f=d.value;r.add(f)}}catch(e){u.e(e)}finally{u.f()}}}catch(e){s.e(e)}finally{s.f()}}catch(e){Z.searchPseudoElementsWarnings&&console.warn(`Font Awesome: cannot parse stylesheet: ${o.href} (${e.message})
If it declares any Font Awesome CSS pseudo-elements, they will not be rendered as SVG icons. Add crossorigin="anonymous" to the <link>, enable searchPseudoElementsFullScan for slower but more thorough DOM parsing, or suppress this warning by setting searchPseudoElementsWarnings to false.`)}}}catch(e){i.e(e)}finally{i.f()}if(!r.size)return;var p=Array.from(r).join(`, `);try{n=e.querySelectorAll(p)}catch{}}return new Promise(function(e,t){var r=Rc(n).filter(sd).map(od),i=gu.begin(`searchPseudoElements`);Au(),Promise.all(r).then(function(){i(),ju(),e()}).catch(function(){i(),ju(),t()})})}}var dd={hooks:function(){return{mutationObserverCallbacks:function(e){return e.pseudoElementsCallback=ud,e}}},provides:function(e){e.pseudoElements2svg=function(e){var t=e.node,n=t===void 0?Y:t;Z.searchPseudoElements&&ud(n)}}},fd=!1,pd={mixout:function(){return{dom:{unwatch:function(){Au(),fd=!0}}}},hooks:function(){return{bootstrap:function(){Nu(Kl(`mutationObserverCallbacks`,{}))},noAuto:function(){Pu()},watch:function(e){var t=e.observeMutationsRoot;fd?ju():Nu(Kl(`mutationObserverCallbacks`,{observeMutationsRoot:t}))}}}},md=function(e){return e.toLowerCase().split(` `).reduce(function(e,t){var n=t.toLowerCase().split(`-`),r=n[0],i=n.slice(1).join(`-`);if(r&&i===`h`)return e.flipX=!0,e;if(r&&i===`v`)return e.flipY=!0,e;if(i=parseFloat(i),isNaN(i))return e;switch(r){case`grow`:e.size+=i;break;case`shrink`:e.size-=i;break;case`left`:e.x-=i;break;case`right`:e.x+=i;break;case`up`:e.y-=i;break;case`down`:e.y+=i;break;case`rotate`:e.rotate+=i}return e},{size:16,x:0,y:0,flipX:!1,flipY:!1,rotate:0})},hd={mixout:function(){return{parse:{transform:function(e){return md(e)}}}},hooks:function(){return{parseNodeAttributes:function(e,t){var n=t.getAttribute(`data-fa-transform`);return n&&(e.transform=md(n)),e}}},provides:function(e){e.generateAbstractTransformGrouping=function(e){var t=e.main,n=e.transform,r=e.containerWidth,i=e.iconWidth,a={outer:{transform:`translate(${r/2} 256)`},inner:{transform:`${`translate(${n.x*32}, ${n.y*32}) `} ${`scale(${n.size/16*(n.flipX?-1:1)}, ${n.size/16*(n.flipY?-1:1)}) `} ${`rotate(${n.rotate} 0 0)`}`},path:{transform:`translate(${i/2*-1} -256)`}};return{tag:`g`,attributes:J({},a.outer),children:[{tag:`g`,attributes:J({},a.inner),children:[{tag:t.icon.tag,children:t.icon.children,attributes:J(J({},t.icon.attributes),a.path)}]}]}}}},gd={x:0,y:0,width:`100%`,height:`100%`};function _d(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:!0;return e.attributes&&(e.attributes.fill||t)&&(e.attributes.fill=`black`),e}function vd(e){return e.tag===`g`?e.children:[e]}Gl([Xc,qu,Ju,Yu,Xu,dd,pd,hd,{hooks:function(){return{parseNodeAttributes:function(e,t){var n=t.getAttribute(`data-fa-mask`),r=n?Fl(n.split(` `).map(function(e){return e.trim()})):kl();return r.prefix||=Ol(),e.mask=r,e.maskId=t.getAttribute(`data-fa-mask-id`),e}}},provides:function(e){e.generateAbstractMask=function(e){var t=e.children,n=e.attributes,r=e.main,i=e.mask,a=e.maskId,o=e.transform,s=r.width,c=r.icon,l=i.width,u=i.icon,d=Wc({transform:o,containerWidth:l,iconWidth:s}),f={tag:`rect`,attributes:J(J({},gd),{},{fill:`white`})},p=c.children?{children:c.children.map(_d)}:{},m={tag:`g`,attributes:J({},d.inner),children:[_d(J({tag:c.tag,attributes:J(J({},c.attributes),d.path)},p))]},h={tag:`g`,attributes:J({},d.outer),children:[m]},g=`mask-${a||Lc()}`,_=`clip-${a||Lc()}`,v={tag:`mask`,attributes:J(J({},gd),{},{id:g,maskUnits:`userSpaceOnUse`,maskContentUnits:`userSpaceOnUse`}),children:[f,h]},y={tag:`defs`,children:[{tag:`clipPath`,attributes:{id:_},children:vd(u)},v]};return t.push(y,{tag:`rect`,attributes:J({fill:`currentColor`,"clip-path":`url(#${_})`,mask:`url(#${g})`},gd)}),{children:t,attributes:n}}}},{provides:function(e){var t=!1;wo.matchMedia&&(t=wo.matchMedia(`(prefers-reduced-motion: reduce)`).matches),e.missingIconAbstract=function(){var e=[],n={fill:`currentColor`},r={attributeType:`XML`,repeatCount:`indefinite`,dur:`2s`};e.push({tag:`path`,attributes:J(J({},n),{},{d:`M156.5,447.7l-12.6,29.5c-18.7-9.5-35.9-21.2-51.5-34.9l22.7-22.7C127.6,430.5,141.5,440,156.5,447.7z M40.6,272H8.5 c1.4,21.2,5.4,41.7,11.7,61.1L50,321.2C45.1,305.5,41.8,289,40.6,272z M40.6,240c1.4-18.8,5.2-37,11.1-54.1l-29.5-12.6 C14.7,194.3,10,216.7,8.5,240H40.6z M64.3,156.5c7.8-14.9,17.2-28.8,28.1-41.5L69.7,92.3c-13.7,15.6-25.5,32.8-34.9,51.5 L64.3,156.5z M397,419.6c-13.9,12-29.4,22.3-46.1,30.4l11.9,29.8c20.7-9.9,39.8-22.6,56.9-37.6L397,419.6z M115,92.4 c13.9-12,29.4-22.3,46.1-30.4l-11.9-29.8c-20.7,9.9-39.8,22.6-56.8,37.6L115,92.4z M447.7,355.5c-7.8,14.9-17.2,28.8-28.1,41.5 l22.7,22.7c13.7-15.6,25.5-32.9,34.9-51.5L447.7,355.5z M471.4,272c-1.4,18.8-5.2,37-11.1,54.1l29.5,12.6 c7.5-21.1,12.2-43.5,13.6-66.8H471.4z M321.2,462c-15.7,5-32.2,8.2-49.2,9.4v32.1c21.2-1.4,41.7-5.4,61.1-11.7L321.2,462z M240,471.4c-18.8-1.4-37-5.2-54.1-11.1l-12.6,29.5c21.1,7.5,43.5,12.2,66.8,13.6V471.4z M462,190.8c5,15.7,8.2,32.2,9.4,49.2h32.1 c-1.4-21.2-5.4-41.7-11.7-61.1L462,190.8z M92.4,397c-12-13.9-22.3-29.4-30.4-46.1l-29.8,11.9c9.9,20.7,22.6,39.8,37.6,56.9 L92.4,397z M272,40.6c18.8,1.4,36.9,5.2,54.1,11.1l12.6-29.5C317.7,14.7,295.3,10,272,8.5V40.6z M190.8,50 c15.7-5,32.2-8.2,49.2-9.4V8.5c-21.2,1.4-41.7,5.4-61.1,11.7L190.8,50z M442.3,92.3L419.6,115c12,13.9,22.3,29.4,30.5,46.1 l29.8-11.9C470,128.5,457.3,109.4,442.3,92.3z M397,92.4l22.7-22.7c-15.6-13.7-32.8-25.5-51.5-34.9l-12.6,29.5 C370.4,72.1,384.4,81.5,397,92.4z`})});var i=J(J({},r),{},{attributeName:`opacity`}),a={tag:`circle`,attributes:J(J({},n),{},{cx:`256`,cy:`364`,r:`28`}),children:[]};return t||a.children.push({tag:`animate`,attributes:J(J({},r),{},{attributeName:`r`,values:`28;14;28;28;14;28;`})},{tag:`animate`,attributes:J(J({},i),{},{values:`1;0;1;1;0;1;`})}),e.push(a),e.push({tag:`path`,attributes:J(J({},n),{},{opacity:`1`,d:`M263.7,312h-16c-6.6,0-12-5.4-12-12c0-71,77.4-63.9,77.4-107.8c0-20-17.8-40.2-57.4-40.2c-29.1,0-44.3,9.6-59.2,28.7 c-3.9,5-11.1,6-16.2,2.4l-13.1-9.2c-5.6-3.9-6.9-11.8-2.6-17.2c21.2-27.2,46.4-44.7,91.2-44.7c52.3,0,97.4,29.8,97.4,80.2 c0,67.6-77.4,63.5-77.4,107.8C275.7,306.6,270.3,312,263.7,312z`}),children:t?[]:[{tag:`animate`,attributes:J(J({},i),{},{values:`1;0;0;0;0;1;`})}]}),t||e.push({tag:`path`,attributes:J(J({},n),{},{opacity:`0`,d:`M232.5,134.5l7,168c0.3,6.4,5.6,11.5,12,11.5h9c6.4,0,11.7-5.1,12-11.5l7-168c0.3-6.8-5.2-12.5-12-12.5h-23 C237.7,122,232.2,127.7,232.5,134.5z`}),children:[{tag:`animate`,attributes:J(J({},i),{},{values:`0;0;1;1;0;0;`})}]}),{tag:`g`,attributes:{class:`missing`},children:e}}}},{hooks:function(){return{parseNodeAttributes:function(e,t){var n=t.getAttribute(`data-fa-symbol`);return e.symbol=n===null?!1:n===``||n,e}}}}],{mixoutsTo:Zl}),Zl.noAuto;var yd=Zl.config,bd=Zl.library;Zl.dom;var xd=Zl.parse;Zl.findIconDefinition,Zl.toHtml;var Sd=Zl.icon;Zl.layer;var Cd=Zl.text;Zl.counter;var wd={prefix:`fas`,iconName:`caret-right`,icon:[256,512,[],`f0da`,`M249.3 235.8c10.2 12.6 9.5 31.1-2.2 42.8l-128 128c-9.2 9.2-22.9 11.9-34.9 6.9S64.5 396.9 64.5 384l0-256c0-12.9 7.8-24.6 19.8-29.6s25.7-2.2 34.9 6.9l128 128 2.2 2.4z`]},Td={prefix:`fas`,iconName:`ear-deaf`,icon:[512,512,[`deaf`,`deafness`,`hard-of-hearing`],`f2a4`,`M502.6 54.6l-40 40c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3l40-40c12.5-12.5 32.8-12.5 45.3 0s12.5 32.8 0 45.3zm-320 320l-128 128c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3l128-128c12.5-12.5 32.8-12.5 45.3 0s12.5 32.8 0 45.3zM240 128c-57.6 0-105.1 43.6-111.3 99.5-1.9 17.6-17.8 30.2-35.3 28.3s-30.2-17.8-28.3-35.3c9.7-88 84.3-156.5 174.9-156.5 97.2 0 176 78.8 176 176 0 46-17.7 87.9-46.6 119.3-12 13-17.4 24.8-17.4 34.7l0 6.1c0 61.9-50.1 112-112 112-17.7 0-32-14.3-32-32s14.3-32 32-32c26.5 0 48-21.5 48-48l0-6.1c0-32.9 17.4-59.6 34.4-78 18.4-20 29.6-46.6 29.6-75.9 0-61.9-50.1-112-112-112zm0 80c-17.7 0-32 14.3-32 32 0 13.3-10.7 24-24 24s-24-10.7-24-24c0-44.2 35.8-80 80-80s80 35.8 80 80c0 13.3-10.7 24-24 24s-24-10.7-24-24c0-17.7-14.3-32-32-32z`]},Ed={prefix:`fas`,iconName:`magnifying-glass`,icon:[512,512,[128269,`search`],`f002`,`M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376C296.3 401.1 253.9 416 208 416 93.1 416 0 322.9 0 208S93.1 0 208 0 416 93.1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 1 0 0 288z`]},Dd={prefix:`fas`,iconName:`floppy-disk`,icon:[448,512,[128190,128426,`save`],`f0c7`,`M64 32C28.7 32 0 60.7 0 96L0 416c0 35.3 28.7 64 64 64l320 0c35.3 0 64-28.7 64-64l0-242.7c0-17-6.7-33.3-18.7-45.3L352 50.7C340 38.7 323.7 32 306.7 32L64 32zm32 96c0-17.7 14.3-32 32-32l160 0c17.7 0 32 14.3 32 32l0 64c0 17.7-14.3 32-32 32l-160 0c-17.7 0-32-14.3-32-32l0-64zM224 288a64 64 0 1 1 0 128 64 64 0 1 1 0-128z`]},Od={prefix:`fas`,iconName:`angle-left`,icon:[256,512,[8249],`f104`,`M9.4 233.4c-12.5 12.5-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L77.3 256 214.6 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-160 160z`]},kd={prefix:`fas`,iconName:`circle-half-stroke`,icon:[512,512,[9680,`adjust`],`f042`,`M448 256c0-106-86-192-192-192l0 384c106 0 192-86 192-192zM0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0z`]},Ad={prefix:`fas`,iconName:`heart`,icon:[512,512,[128153,128154,128155,128156,128420,129293,129294,129505,9829,10084,61578],`f004`,`M241 87.1l15 20.7 15-20.7C296 52.5 336.2 32 378.9 32 452.4 32 512 91.6 512 165.1l0 2.6c0 112.2-139.9 242.5-212.9 298.2-12.4 9.4-27.6 14.1-43.1 14.1s-30.8-4.6-43.1-14.1C139.9 410.2 0 279.9 0 167.7l0-2.6C0 91.6 59.6 32 133.1 32 175.8 32 216 52.5 241 87.1z`]},jd={prefix:`fas`,iconName:`chevron-right`,icon:[320,512,[9002],`f054`,`M311.1 233.4c12.5 12.5 12.5 32.8 0 45.3l-192 192c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L243.2 256 73.9 86.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l192 192z`]},Md={prefix:`fas`,iconName:`file-import`,icon:[384,512,[`arrow-right-to-file`],`f56f`,`M64 0C28.7 0 0 28.7 0 64l0 240 182.1 0-31-31c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l72 72c9.4 9.4 9.4 24.6 0 33.9l-72 72c-9.4 9.4-24.6 9.4-33.9 0s-9.4-24.6 0-33.9l31-31-182.1 0 0 96c0 35.3 28.7 64 64 64l256 0c35.3 0 64-28.7 64-64l0-277.5c0-17-6.7-33.3-18.7-45.3L258.7 18.7C246.7 6.7 230.5 0 213.5 0L64 0zM325.5 176L232 176c-13.3 0-24-10.7-24-24L208 58.5 325.5 176z`]},Nd={prefix:`fas`,iconName:`microphone`,icon:[384,512,[],`f130`,`M192 0C139 0 96 43 96 96l0 128c0 53 43 96 96 96s96-43 96-96l0-128c0-53-43-96-96-96zM48 184c0-13.3-10.7-24-24-24S0 170.7 0 184l0 40c0 97.9 73.3 178.7 168 190.5l0 49.5-48 0c-13.3 0-24 10.7-24 24s10.7 24 24 24l144 0c13.3 0 24-10.7 24-24s-10.7-24-24-24l-48 0 0-49.5c94.7-11.8 168-92.6 168-190.5l0-40c0-13.3-10.7-24-24-24s-24 10.7-24 24l0 40c0 79.5-64.5 144-144 144S48 303.5 48 224l0-40z`]},Pd={prefix:`fas`,iconName:`sun`,icon:[576,512,[9728],`f185`,`M288-32c8.4 0 16.3 4.4 20.6 11.7L364.1 72.3 468.9 46c8.2-2 16.9 .4 22.8 6.3S500 67 498 75.1l-26.3 104.7 92.7 55.5c7.2 4.3 11.7 12.2 11.7 20.6s-4.4 16.3-11.7 20.6L471.7 332.1 498 436.8c2 8.2-.4 16.9-6.3 22.8S477 468 468.9 466l-104.7-26.3-55.5 92.7c-4.3 7.2-12.2 11.7-20.6 11.7s-16.3-4.4-20.6-11.7L211.9 439.7 107.2 466c-8.2 2-16.8-.4-22.8-6.3S76 445 78 436.8l26.2-104.7-92.6-55.5C4.4 272.2 0 264.4 0 256s4.4-16.3 11.7-20.6L104.3 179.9 78 75.1c-2-8.2 .3-16.8 6.3-22.8S99 44 107.2 46l104.7 26.2 55.5-92.6 1.8-2.6c4.5-5.7 11.4-9.1 18.8-9.1zm0 144a144 144 0 1 0 0 288 144 144 0 1 0 0-288zm0 240a96 96 0 1 1 0-192 96 96 0 1 1 0 192z`]},Fd={prefix:`fas`,iconName:`angle-right`,icon:[256,512,[8250],`f105`,`M247.1 233.4c12.5 12.5 12.5 32.8 0 45.3l-160 160c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L179.2 256 41.9 118.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l160 160z`]},Id={prefix:`fas`,iconName:`thumbtack`,icon:[384,512,[128204,128392,`thumb-tack`],`f08d`,`M32 32C32 14.3 46.3 0 64 0L320 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-29.5 0 10.3 134.1c37.1 21.2 65.8 56.4 78.2 99.7l3.8 13.4c2.8 9.7 .8 20-5.2 28.1S362 352 352 352L32 352c-10 0-19.5-4.7-25.5-12.7s-8-18.4-5.2-28.1L5 297.8c12.4-43.3 41-78.5 78.2-99.7L93.5 64 64 64C46.3 64 32 49.7 32 32zM160 400l64 0 0 112c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-112z`]},Ld={prefix:`fas`,iconName:`folder`,icon:[512,512,[128193,128447,61716,`folder-blank`],`f07b`,`M64 448l384 0c35.3 0 64-28.7 64-64l0-240c0-35.3-28.7-64-64-64L298.7 80c-6.9 0-13.7-2.2-19.2-6.4L241.1 44.8C230 36.5 216.5 32 202.7 32L64 32C28.7 32 0 60.7 0 96L0 384c0 35.3 28.7 64 64 64z`]},Rd={prefix:`fas`,iconName:`circle`,icon:[512,512,[128308,128309,128992,128993,128994,128995,128996,9679,9898,9899,11044,61708,61915],`f111`,`M0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0z`]},zd={prefix:`fas`,iconName:`arrow-turn-up`,icon:[384,512,[`level-up`],`f148`,`M32 448c-17.7 0-32 14.3-32 32s14.3 32 32 32l96 0c53 0 96-43 96-96l0-306.7 73.4 73.4c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-128-128c-12.5-12.5-32.8-12.5-45.3 0l-128 128c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 109.3 160 416c0 17.7-14.3 32-32 32l-96 0z`]},Bd={prefix:`fas`,iconName:`right-from-bracket`,icon:[512,512,[`sign-out-alt`],`f2f5`,`M505 273c9.4-9.4 9.4-24.6 0-33.9L361 95c-6.9-6.9-17.2-8.9-26.2-5.2S320 102.3 320 112l0 80-112 0c-26.5 0-48 21.5-48 48l0 32c0 26.5 21.5 48 48 48l112 0 0 80c0 9.7 5.8 18.5 14.8 22.2s19.3 1.7 26.2-5.2L505 273zM160 96c17.7 0 32-14.3 32-32s-14.3-32-32-32L96 32C43 32 0 75 0 128L0 384c0 53 43 96 96 96l64 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-64 0c-17.7 0-32-14.3-32-32l0-256c0-17.7 14.3-32 32-32l64 0z`]},Vd={prefix:`fas`,iconName:`play`,icon:[448,512,[9654],`f04b`,`M91.2 36.9c-12.4-6.8-27.4-6.5-39.6 .7S32 57.9 32 72l0 368c0 14.1 7.5 27.2 19.6 34.4s27.2 7.5 39.6 .7l336-184c12.8-7 20.8-20.5 20.8-35.1s-8-28.1-20.8-35.1l-336-184z`]},Hd={prefix:`fas`,iconName:`trash-can`,icon:[448,512,[61460,`trash-alt`],`f2ed`,`M136.7 5.9C141.1-7.2 153.3-16 167.1-16l113.9 0c13.8 0 26 8.8 30.4 21.9L320 32 416 32c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 96C14.3 96 0 81.7 0 64S14.3 32 32 32l96 0 8.7-26.1zM32 144l384 0 0 304c0 35.3-28.7 64-64 64L96 512c-35.3 0-64-28.7-64-64l0-304zm88 64c-13.3 0-24 10.7-24 24l0 192c0 13.3 10.7 24 24 24s24-10.7 24-24l0-192c0-13.3-10.7-24-24-24zm104 0c-13.3 0-24 10.7-24 24l0 192c0 13.3 10.7 24 24 24s24-10.7 24-24l0-192c0-13.3-10.7-24-24-24zm104 0c-13.3 0-24 10.7-24 24l0 192c0 13.3 10.7 24 24 24s24-10.7 24-24l0-192c0-13.3-10.7-24-24-24z`]},Ud={prefix:`fas`,iconName:`check`,icon:[448,512,[10003,10004],`f00c`,`M434.8 70.1c14.3 10.4 17.5 30.4 7.1 44.7l-256 352c-5.5 7.6-14 12.3-23.4 13.1s-18.5-2.7-25.1-9.3l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l101.5 101.5 234-321.7c10.4-14.3 30.4-17.5 44.7-7.1z`]},Wd={prefix:`fas`,iconName:`forward-step`,icon:[384,512,[`step-forward`],`f051`,`M21 36.8c12.9-7 28.7-6.3 41 1.8L320 208.1 320 64c0-17.7 14.3-32 32-32s32 14.3 32 32l0 384c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-144.1-258 169.6c-12.3 8.1-28 8.8-41 1.8S0 454.7 0 440L0 72C0 57.3 8.1 43.8 21 36.8z`]},Gd={prefix:`fas`,iconName:`server`,icon:[448,512,[],`f233`,`M64 32C28.7 32 0 60.7 0 96l0 64c0 35.3 28.7 64 64 64l320 0c35.3 0 64-28.7 64-64l0-64c0-35.3-28.7-64-64-64L64 32zm216 72a24 24 0 1 1 0 48 24 24 0 1 1 0-48zm56 24a24 24 0 1 1 48 0 24 24 0 1 1 -48 0zM64 288c-35.3 0-64 28.7-64 64l0 64c0 35.3 28.7 64 64 64l320 0c35.3 0 64-28.7 64-64l0-64c0-35.3-28.7-64-64-64L64 288zm216 72a24 24 0 1 1 0 48 24 24 0 1 1 0-48zm56 24a24 24 0 1 1 48 0 24 24 0 1 1 -48 0z`]},Kd={prefix:`fas`,iconName:`user`,icon:[448,512,[128100,62144,62470,`user-alt`,`user-large`],`f007`,`M224 248a120 120 0 1 0 0-240 120 120 0 1 0 0 240zm-29.7 56C95.8 304 16 383.8 16 482.3 16 498.7 29.3 512 45.7 512l356.6 0c16.4 0 29.7-13.3 29.7-29.7 0-98.5-79.8-178.3-178.3-178.3l-59.4 0z`]},qd={prefix:`fas`,iconName:`volume-xmark`,icon:[576,512,[`volume-mute`,`volume-times`],`f6a9`,`M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM367 175c-9.4 9.4-9.4 24.6 0 33.9l47 47-47 47c-9.4 9.4-9.4 24.6 0 33.9s24.6 9.4 33.9 0l47-47 47 47c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-47-47 47-47c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-47 47-47-47c-9.4-9.4-24.6-9.4-33.9 0z`]},Jd={prefix:`fas`,iconName:`xmark`,icon:[384,512,[128473,10005,10006,10060,215,`close`,`multiply`,`remove`,`times`],`f00d`,`M55.1 73.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L147.2 256 9.9 393.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L192.5 301.3 329.9 438.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L237.8 256 375.1 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L192.5 210.7 55.1 73.4z`]},Yd={prefix:`fas`,iconName:`moon`,icon:[512,512,[127769,9214],`f186`,`M256 0C114.6 0 0 114.6 0 256S114.6 512 256 512c68.8 0 131.3-27.2 177.3-71.4 7.3-7 9.4-17.9 5.3-27.1s-13.7-14.9-23.8-14.1c-4.9 .4-9.8 .6-14.8 .6-101.6 0-184-82.4-184-184 0-72.1 41.5-134.6 102.1-164.8 9.1-4.5 14.3-14.3 13.1-24.4S322.6 8.5 312.7 6.3C294.4 2.2 275.4 0 256 0z`]},Xd={prefix:`fas`,iconName:`pen`,icon:[512,512,[128394],`f304`,`M352.9 21.2L308 66.1 445.9 204 490.8 159.1C504.4 145.6 512 127.2 512 108s-7.6-37.6-21.2-51.1L455.1 21.2C441.6 7.6 423.2 0 404 0s-37.6 7.6-51.1 21.2zM274.1 100L58.9 315.1c-10.7 10.7-18.5 24.1-22.6 38.7L.9 481.6c-2.3 8.3 0 17.3 6.2 23.4s15.1 8.5 23.4 6.2l127.8-35.5c14.6-4.1 27.9-11.8 38.7-22.6L412 237.9 274.1 100z`]},Zd={prefix:`fas`,iconName:`volume-low`,icon:[448,512,[128264,`volume-down`],`f027`,`M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM380.6 181.5c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C361.1 227.6 368 241 368 256s-6.9 28.4-17.7 37.3c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5C402.1 312.9 416 286.1 416 256s-13.9-56.9-35.5-74.5z`]},Qd={prefix:`fas`,iconName:`headphones`,icon:[448,512,[127911,62863,`headphones-alt`,`headphones-simple`],`f025`,`M64 224c0-88.4 71.6-160 160-160s160 71.6 160 160l0 37.5c-10-3.5-20.8-5.5-32-5.5l-16 0c-26.5 0-48 21.5-48 48l0 128c0 26.5 21.5 48 48 48l16 0c53 0 96-43 96-96l0-160C448 100.3 347.7 0 224 0S0 100.3 0 224L0 384c0 53 43 96 96 96l16 0c26.5 0 48-21.5 48-48l0-128c0-26.5-21.5-48-48-48l-16 0c-11.2 0-22 1.9-32 5.5L64 224z`]},$d={prefix:`fas`,iconName:`chevron-down`,icon:[448,512,[],`f078`,`M201.4 406.6c12.5 12.5 32.8 12.5 45.3 0l192-192c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 338.7 54.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l192 192z`]},ef={prefix:`fas`,iconName:`grip-vertical`,icon:[320,512,[`grid-vertical`],`f58e`,`M128 40c0-22.1-17.9-40-40-40L40 0C17.9 0 0 17.9 0 40L0 88c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zm0 192c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zM0 424l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40zM320 40c0-22.1-17.9-40-40-40L232 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zM192 232l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40zM320 424c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48z`]},tf={prefix:`fas`,iconName:`star`,icon:[576,512,[11088,61446],`f005`,`M309.5-18.9c-4.1-8-12.4-13.1-21.4-13.1s-17.3 5.1-21.4 13.1L193.1 125.3 33.2 150.7c-8.9 1.4-16.3 7.7-19.1 16.3s-.5 18 5.8 24.4l114.4 114.5-25.2 159.9c-1.4 8.9 2.3 17.9 9.6 23.2s16.9 6.1 25 2L288.1 417.6 432.4 491c8 4.1 17.7 3.3 25-2s11-14.2 9.6-23.2L441.7 305.9 556.1 191.4c6.4-6.4 8.6-15.8 5.8-24.4s-10.1-14.9-19.1-16.3L383 125.3 309.5-18.9z`]},nf={prefix:`fas`,iconName:`triangle-exclamation`,icon:[512,512,[9888,`exclamation-triangle`,`warning`],`f071`,`M256 0c14.7 0 28.2 8.1 35.2 21l216 400c6.7 12.4 6.4 27.4-.8 39.5S486.1 480 472 480L40 480c-14.1 0-27.2-7.4-34.4-19.5s-7.5-27.1-.8-39.5l216-400c7-12.9 20.5-21 35.2-21zm0 352a32 32 0 1 0 0 64 32 32 0 1 0 0-64zm0-192c-18.2 0-32.7 15.5-31.4 33.7l7.4 104c.9 12.5 11.4 22.3 23.9 22.3 12.6 0 23-9.7 23.9-22.3l7.4-104c1.3-18.2-13.1-33.7-31.4-33.7z`]},rf={prefix:`fas`,iconName:`lock`,icon:[384,512,[128274],`f023`,`M128 96l0 64 128 0 0-64c0-35.3-28.7-64-64-64s-64 28.7-64 64zM64 160l0-64C64 25.3 121.3-32 192-32S320 25.3 320 96l0 64c35.3 0 64 28.7 64 64l0 224c0 35.3-28.7 64-64 64L64 512c-35.3 0-64-28.7-64-64L0 224c0-35.3 28.7-64 64-64z`]},af={prefix:`fas`,iconName:`volume-high`,icon:[640,512,[128266,`volume-up`],`f028`,`M533.6 32.5c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C557.5 113.8 592 180.8 592 256s-34.5 142.2-88.7 186.3c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5C598.5 426.7 640 346.2 640 256S598.5 85.2 533.6 32.5zM473.1 107c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C475.3 170.7 496 210.9 496 256s-20.7 85.3-53.2 111.8c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5c43.2-35.2 70.9-88.9 70.9-149s-27.7-113.8-70.9-149zm-60.5 74.5c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C393.1 227.6 400 241 400 256s-6.9 28.4-17.7 37.3c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5C434.1 312.9 448 286.1 448 256s-13.9-56.9-35.4-74.5zM80 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L128 160 80 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48z`]},of={prefix:`fas`,iconName:`download`,icon:[448,512,[],`f019`,`M256 32c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 210.7-41.4-41.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l96 96c12.5 12.5 32.8 12.5 45.3 0l96-96c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L256 242.7 256 32zM64 320c-35.3 0-64 28.7-64 64l0 32c0 35.3 28.7 64 64 64l320 0c35.3 0 64-28.7 64-64l0-32c0-35.3-28.7-64-64-64l-46.9 0-56.6 56.6c-31.2 31.2-81.9 31.2-113.1 0L110.9 320 64 320zm304 56a24 24 0 1 1 0 48 24 24 0 1 1 0-48z`]},sf={prefix:`fas`,iconName:`globe`,icon:[512,512,[127760],`f0ac`,`M351.9 280l-190.9 0c2.9 64.5 17.2 123.9 37.5 167.4 11.4 24.5 23.7 41.8 35.1 52.4 11.2 10.5 18.9 12.2 22.9 12.2s11.7-1.7 22.9-12.2c11.4-10.6 23.7-28 35.1-52.4 20.3-43.5 34.6-102.9 37.5-167.4zM160.9 232l190.9 0C349 167.5 334.7 108.1 314.4 64.6 303 40.2 290.7 22.8 279.3 12.2 268.1 1.7 260.4 0 256.4 0s-11.7 1.7-22.9 12.2c-11.4 10.6-23.7 28-35.1 52.4-20.3 43.5-34.6 102.9-37.5 167.4zm-48 0C116.4 146.4 138.5 66.9 170.8 14.7 78.7 47.3 10.9 131.2 1.5 232l111.4 0zM1.5 280c9.4 100.8 77.2 184.7 169.3 217.3-32.3-52.2-54.4-131.7-57.9-217.3L1.5 280zm398.4 0c-3.5 85.6-25.6 165.1-57.9 217.3 92.1-32.7 159.9-116.5 169.3-217.3l-111.4 0zm111.4-48C501.9 131.2 434.1 47.3 342 14.7 374.3 66.9 396.4 146.4 399.9 232l111.4 0z`]},cf={prefix:`fas`,iconName:`upload`,icon:[448,512,[],`f093`,`M256 109.3L256 320c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-210.7-41.4 41.4c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3l96-96c12.5-12.5 32.8-12.5 45.3 0l96 96c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L256 109.3zM224 400c44.2 0 80-35.8 80-80l80 0c35.3 0 64 28.7 64 64l0 32c0 35.3-28.7 64-64 64L64 480c-35.3 0-64-28.7-64-64l0-32c0-35.3 28.7-64 64-64l80 0c0 44.2 35.8 80 80 80zm144 24a24 24 0 1 0 0-48 24 24 0 1 0 0 48z`]},lf={prefix:`fas`,iconName:`music`,icon:[512,512,[127925],`f001`,`M468 7c7.6 6.1 12 15.3 12 25l0 304c0 44.2-43 80-96 80s-96-35.8-96-80 43-80 96-80c11.2 0 22 1.6 32 4.6l0-116.7-224 49.8 0 206.3c0 44.2-43 80-96 80s-96-35.8-96-80 43-80 96-80c11.2 0 22 1.6 32 4.6L128 96c0-15 10.4-28 25.1-31.2l288-64c9.5-2.1 19.4 .2 27 6.3z`]},uf={prefix:`fas`,iconName:`shuffle`,icon:[512,512,[128256,`random`],`f074`,`M403.8 34.4c12-5 25.7-2.2 34.9 6.9l64 64c6 6 9.4 14.1 9.4 22.6s-3.4 16.6-9.4 22.6l-64 64c-9.2 9.2-22.9 11.9-34.9 6.9S384 204.9 384 192l0-32-32 0c-10.1 0-19.6 4.7-25.6 12.8l-32.4 43.2-40-53.3 21.2-28.3C293.3 110.2 321.8 96 352 96l32 0 0-32c0-12.9 7.8-24.6 19.8-29.6zM154 296l40 53.3-21.2 28.3C154.7 401.8 126.2 416 96 416l-64 0c-17.7 0-32-14.3-32-32s14.3-32 32-32l64 0c10.1 0 19.6-4.7 25.6-12.8L154 296zM438.6 470.6c-9.2 9.2-22.9 11.9-34.9 6.9S384 460.9 384 448l0-32-32 0c-30.2 0-58.7-14.2-76.8-38.4L121.6 172.8c-6-8.1-15.5-12.8-25.6-12.8l-64 0c-17.7 0-32-14.3-32-32S14.3 96 32 96l64 0c30.2 0 58.7 14.2 76.8 38.4L326.4 339.2c6 8.1 15.5 12.8 25.6 12.8l32 0 0-32c0-12.9 7.8-24.6 19.8-29.6s25.7-2.2 34.9 6.9l64 64c6 6 9.4 14.1 9.4 22.6s-3.4 16.6-9.4 22.6l-64 64z`]},df={prefix:`fas`,iconName:`robot`,icon:[640,512,[129302],`f544`,`M352 0c0-17.7-14.3-32-32-32S288-17.7 288 0l0 64-96 0c-53 0-96 43-96 96l0 224c0 53 43 96 96 96l256 0c53 0 96-43 96-96l0-224c0-53-43-96-96-96l-96 0 0-64zM160 368c0-13.3 10.7-24 24-24l32 0c13.3 0 24 10.7 24 24s-10.7 24-24 24l-32 0c-13.3 0-24-10.7-24-24zm120 0c0-13.3 10.7-24 24-24l32 0c13.3 0 24 10.7 24 24s-10.7 24-24 24l-32 0c-13.3 0-24-10.7-24-24zm120 0c0-13.3 10.7-24 24-24l32 0c13.3 0 24 10.7 24 24s-10.7 24-24 24l-32 0c-13.3 0-24-10.7-24-24zM224 176a48 48 0 1 1 0 96 48 48 0 1 1 0-96zm144 48a48 48 0 1 1 96 0 48 48 0 1 1 -96 0zM64 224c0-17.7-14.3-32-32-32S0 206.3 0 224l0 96c0 17.7 14.3 32 32 32s32-14.3 32-32l0-96zm544-32c-17.7 0-32 14.3-32 32l0 96c0 17.7 14.3 32 32 32s32-14.3 32-32l0-96c0-17.7-14.3-32-32-32z`]},ff={prefix:`fas`,iconName:`plus`,icon:[448,512,[10133,61543,`add`],`2b`,`M256 64c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 160-160 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l160 0 0 160c0 17.7 14.3 32 32 32s32-14.3 32-32l0-160 160 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-160 0 0-160z`]},pf={prefix:`fas`,iconName:`copy`,icon:[448,512,[],`f0c5`,`M192 0c-35.3 0-64 28.7-64 64l0 256c0 35.3 28.7 64 64 64l192 0c35.3 0 64-28.7 64-64l0-200.6c0-17.4-7.1-34.1-19.7-46.2L370.6 17.8C358.7 6.4 342.8 0 326.3 0L192 0zM64 128c-35.3 0-64 28.7-64 64L0 448c0 35.3 28.7 64 64 64l192 0c35.3 0 64-28.7 64-64l0-16-64 0 0 16-192 0 0-256 16 0 0-64-16 0z`]},mf={prefix:`fas`,iconName:`pause`,icon:[384,512,[9208],`f04c`,`M48 32C21.5 32 0 53.5 0 80L0 432c0 26.5 21.5 48 48 48l64 0c26.5 0 48-21.5 48-48l0-352c0-26.5-21.5-48-48-48L48 32zm224 0c-26.5 0-48 21.5-48 48l0 352c0 26.5 21.5 48 48 48l64 0c26.5 0 48-21.5 48-48l0-352c0-26.5-21.5-48-48-48l-64 0z`]},hf={prefix:`fas`,iconName:`hashtag`,icon:[512,512,[62098],`23`,`M214.7 .7c17.3 3.7 28.3 20.7 24.6 38l-19.1 89.3 126.5 0 22-102.7C372.4 8 389.4-3 406.7 .7s28.3 20.7 24.6 38L412.2 128 480 128c17.7 0 32 14.3 32 32s-14.3 32-32 32l-81.6 0-27.4 128 67.8 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-81.6 0-22 102.7c-3.7 17.3-20.7 28.3-38 24.6s-28.3-20.7-24.6-38l19.1-89.3-126.5 0-22 102.7c-3.7 17.3-20.7 28.3-38 24.6s-28.3-20.7-24.6-38L99.8 384 32 384c-17.7 0-32-14.3-32-32s14.3-32 32-32l81.6 0 27.4-128-67.8 0c-17.7 0-32-14.3-32-32s14.3-32 32-32l81.6 0 22-102.7C180.4 8 197.4-3 214.7 .7zM206.4 192l-27.4 128 126.5 0 27.4-128-126.5 0z`]},gf={prefix:`fas`,iconName:`list-ul`,icon:[512,512,[`list-dots`],`f0ca`,`M48 144a48 48 0 1 0 0-96 48 48 0 1 0 0 96zM192 64c-17.7 0-32 14.3-32 32s14.3 32 32 32l288 0c17.7 0 32-14.3 32-32s-14.3-32-32-32L192 64zm0 160c-17.7 0-32 14.3-32 32s14.3 32 32 32l288 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-288 0zm0 160c-17.7 0-32 14.3-32 32s14.3 32 32 32l288 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-288 0zM48 464a48 48 0 1 0 0-96 48 48 0 1 0 0 96zM96 256a48 48 0 1 0 -96 0 48 48 0 1 0 96 0z`]},_f={prefix:`far`,iconName:`heart`,icon:[512,512,[128153,128154,128155,128156,128420,129293,129294,129505,9829,10084,61578],`f004`,`M378.9 80c-27.3 0-53 13.1-69 35.2l-34.4 47.6c-4.5 6.2-11.7 9.9-19.4 9.9s-14.9-3.7-19.4-9.9l-34.4-47.6c-16-22.1-41.7-35.2-69-35.2-47 0-85.1 38.1-85.1 85.1 0 49.9 32 98.4 68.1 142.3 41.1 50 91.4 94 125.9 120.3 3.2 2.4 7.9 4.2 14 4.2s10.8-1.8 14-4.2c34.5-26.3 84.8-70.4 125.9-120.3 36.2-43.9 68.1-92.4 68.1-142.3 0-47-38.1-85.1-85.1-85.1zM271 87.1c25-34.6 65.2-55.1 107.9-55.1 73.5 0 133.1 59.6 133.1 133.1 0 68.6-42.9 128.9-79.1 172.8-44.1 53.6-97.3 100.1-133.8 127.9-12.3 9.4-27.5 14.1-43.1 14.1s-30.8-4.7-43.1-14.1C176.4 438 123.2 391.5 79.1 338 42.9 294.1 0 233.7 0 165.1 0 91.6 59.6 32 133.1 32 175.8 32 216 52.5 241 87.1l15 20.7 15-20.7z`]},vf={prefix:`far`,iconName:`star`,icon:[576,512,[11088,61446],`f005`,`M288.1-32c9 0 17.3 5.1 21.4 13.1L383 125.3 542.9 150.7c8.9 1.4 16.3 7.7 19.1 16.3s.5 18-5.8 24.4L441.7 305.9 467 465.8c1.4 8.9-2.3 17.9-9.6 23.2s-17 6.1-25 2L288.1 417.6 143.8 491c-8 4.1-17.7 3.3-25-2s-11-14.2-9.6-23.2L134.4 305.9 20 191.4c-6.4-6.4-8.6-15.8-5.8-24.4s10.1-14.9 19.1-16.3l159.9-25.4 73.6-144.2c4.1-8 12.4-13.1 21.4-13.1zm0 76.8L230.3 158c-3.5 6.8-10 11.6-17.6 12.8l-125.5 20 89.8 89.9c5.4 5.4 7.9 13.1 6.7 20.7l-19.8 125.5 113.3-57.6c6.8-3.5 14.9-3.5 21.8 0l113.3 57.6-19.8-125.5c-1.2-7.6 1.3-15.3 6.7-20.7l89.8-89.9-125.5-20c-7.6-1.2-14.1-6-17.6-12.8L288.1 44.8z`]};function yf(e,t){(t==null||t>e.length)&&(t=e.length);for(var n=0,r=Array(t);n<t;n++)r[n]=e[n];return r}function bf(e){if(Array.isArray(e))return yf(e)}function Q(e,t,n){return(t=Of(t))in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}function xf(e){if(typeof Symbol<`u`&&e[Symbol.iterator]!=null||e[`@@iterator`]!=null)return Array.from(e)}function Sf(){throw TypeError(`Invalid attempt to spread non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function Cf(e,t){var n=Object.keys(e);if(Object.getOwnPropertySymbols){var r=Object.getOwnPropertySymbols(e);t&&(r=r.filter(function(t){return Object.getOwnPropertyDescriptor(e,t).enumerable})),n.push.apply(n,r)}return n}function $(e){for(var t=1;t<arguments.length;t++){var n=arguments[t]==null?{}:arguments[t];t%2?Cf(Object(n),!0).forEach(function(t){Q(e,t,n[t])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(n)):Cf(Object(n)).forEach(function(t){Object.defineProperty(e,t,Object.getOwnPropertyDescriptor(n,t))})}return e}function wf(e,t){if(e==null)return{};var n,r,i=Tf(e,t);if(Object.getOwnPropertySymbols){var a=Object.getOwnPropertySymbols(e);for(r=0;r<a.length;r++)n=a[r],t.indexOf(n)===-1&&{}.propertyIsEnumerable.call(e,n)&&(i[n]=e[n])}return i}function Tf(e,t){if(e==null)return{};var n={};for(var r in e)if({}.hasOwnProperty.call(e,r)){if(t.indexOf(r)!==-1)continue;n[r]=e[r]}return n}function Ef(e){return bf(e)||xf(e)||Af(e)||Sf()}function Df(e,t){if(typeof e!=`object`||!e)return e;var n=e[Symbol.toPrimitive];if(n!==void 0){var r=n.call(e,t||`default`);if(typeof r!=`object`)return r;throw TypeError(`@@toPrimitive must return a primitive value.`)}return(t===`string`?String:Number)(e)}function Of(e){var t=Df(e,`string`);return typeof t==`symbol`?t:t+``}function kf(e){"@babel/helpers - typeof";return kf=typeof Symbol==`function`&&typeof Symbol.iterator==`symbol`?function(e){return typeof e}:function(e){return e&&typeof Symbol==`function`&&e.constructor===Symbol&&e!==Symbol.prototype?`symbol`:typeof e},kf(e)}function Af(e,t){if(e){if(typeof e==`string`)return yf(e,t);var n={}.toString.call(e).slice(8,-1);return n===`Object`&&e.constructor&&(n=e.constructor.name),n===`Map`||n===`Set`?Array.from(e):n===`Arguments`||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)?yf(e,t):void 0}}function jf(e,t){return Array.isArray(t)&&t.length>0||!Array.isArray(t)&&t?Q({},e,t):{}}function Mf(e){var t={"fa-spin":e.spin,"fa-pulse":e.pulse,"fa-fw":e.fixedWidth,"fa-border":e.border,"fa-li":e.listItem,"fa-inverse":e.inverse,"fa-flip":e.flip===!0,"fa-flip-horizontal":e.flip===`horizontal`||e.flip===`both`,"fa-flip-vertical":e.flip===`vertical`||e.flip===`both`},n=(Q(Q(Q(Q(Q(Q(Q(Q(Q(Q(t,`fa-${e.size}`,e.size!==null),`fa-rotate-${e.rotation}`,e.rotation!==null),`fa-rotate-by`,e.rotateBy),`fa-pull-${e.pull}`,e.pull!==null),`fa-swap-opacity`,e.swapOpacity),`fa-bounce`,e.bounce),`fa-shake`,e.shake),`fa-beat`,e.beat),`fa-fade`,e.fade),`fa-beat-fade`,e.beatFade),Q(Q(Q(Q(Q(Q(Q(Q(Q(Q(t,`fa-flash`,e.flash),`fa-spin-pulse`,e.spinPulse),`fa-spin-reverse`,e.spinReverse),`fa-width-auto`,e.widthAuto),`fa-canvas-square`,e.canvasSquare),`fa-canvas-roomy`,e.canvasRoomy),`fa-flip-360`,e.flip360),`fa-buzz`,e.buzz),`fa-float`,e.float),`fa-jello`,e.jello),Q(Q(Q(Q(Q(t,`fa-spin-snap`,e.spinSnap),`fa-spin-snap-4`,e.spinSnap4),`fa-spin-snap-8`,e.spinSnap8),`fa-swing`,e.swing),`fa-wag`,e.wag));return Object.keys(n).map(function(e){return n[e]?e:null}).filter(function(e){return e})}var Nf=typeof globalThis<`u`?globalThis:typeof window<`u`?window:typeof global<`u`?global:typeof self<`u`?self:{},Pf={exports:{}};(function(e){(function(t){var n=function(e,t,r){if(!l(t)||d(t)||f(t)||p(t)||c(t))return t;var i,a=0,o=0;if(u(t))for(i=[],o=t.length;a<o;a++)i.push(n(e,t[a],r));else for(var s in i={},t)Object.prototype.hasOwnProperty.call(t,s)&&(i[e(s,r)]=n(e,t[s],r));return i},r=function(e,t){t||={};var n=t.separator||`_`,r=t.split||/(?=[A-Z])/;return e.split(r).join(n)},i=function(e){return m(e)?e:(e=e.replace(/[\-_\s]+(.)?/g,function(e,t){return t?t.toUpperCase():``}),e.substr(0,1).toLowerCase()+e.substr(1))},a=function(e){var t=i(e);return t.substr(0,1).toUpperCase()+t.substr(1)},o=function(e,t){return r(e,t).toLowerCase()},s=Object.prototype.toString,c=function(e){return typeof e==`function`},l=function(e){return e===Object(e)},u=function(e){return s.call(e)==`[object Array]`},d=function(e){return s.call(e)==`[object Date]`},f=function(e){return s.call(e)==`[object RegExp]`},p=function(e){return s.call(e)==`[object Boolean]`},m=function(e){return e-=0,e===e},h=function(e,t){var n=t&&`process`in t?t.process:t;return typeof n==`function`?function(t,r){return n(t,e,r)}:e},g={camelize:i,decamelize:o,pascalize:a,depascalize:o,camelizeKeys:function(e,t){return n(h(i,t),e)},decamelizeKeys:function(e,t){return n(h(o,t),e,t)},pascalizeKeys:function(e,t){return n(h(a,t),e)},depascalizeKeys:function(){return this.decamelizeKeys.apply(this,arguments)}};e.exports?e.exports=g:t.humps=g})(Nf)})(Pf);var Ff=Pf.exports,If=[`gradientFill`],Lf=[`class`,`style`],Rf=[`type`,`stops`,`id`];function zf(e){return e.split(`;`).map(function(e){return e.trim()}).filter(function(e){return e}).reduce(function(e,t){var n=t.indexOf(`:`),r=Ff.camelize(t.slice(0,n));return e[r]=t.slice(n+1).trim(),e},{})}function Bf(e){return e.split(/\s+/).reduce(function(e,t){return e[t]=!0,e},{})}function Vf(e,t){return s(`stop`,$({key:`${t}-${e.offset}`,offset:e.offset,"stop-color":e.color},e.opacity!==void 0&&{"stop-opacity":e.opacity}))}function Hf(e){if(typeof e==`string`)return e;var t=(e.children||[]).map(Hf);return e.tag===`path`&&e.attributes&&`fill`in e.attributes?$($({},e),{},{attributes:$($({},e.attributes),{},{fill:void 0}),children:t}):$($({},e),{},{children:t})}function Uf(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=arguments.length>2&&arguments[2]!==void 0?arguments[2]:{};if(typeof e==`string`)return e;var r=t.gradientFill,i=r===void 0?null:r,a=wf(t,If),o=i||`fill`in n?Hf(e):e,c=(o.children||[]).map(function(e){return Uf(e,{},{})}),l=Object.keys(o.attributes||{}).reduce(function(e,t){var n=o.attributes[t];switch(t){case`class`:e.class=Bf(n);break;case`style`:e.style=zf(n);break;default:e.attrs[t]=n}return e},{attrs:{},class:{},style:{}});n.class;var u=n.style,d=u===void 0?{}:u,f=wf(n,Lf);if(i&&i.id&&(i.type===`linear`||i.type===`radial`)){var p=i.type,m=i.stops,h=m===void 0?[]:m,g=i.id,_=wf(i,Rf),v=s(p===`linear`?`linearGradient`:`radialGradient`,$($({},_),{},{id:g}),h.map(Vf));return s(o.tag,$($($($({},a),{},{class:l.class,style:$($({},l.style),d)},l.attrs),f),{},{fill:`url(#${g})`}),[v].concat(Ef(c)))}return s(e.tag,$($($({},a),{},{class:l.class,style:$($({},l.style),d)},l.attrs),f),c)}var Wf=!1;try{Wf=!0}catch{}function Gf(){if(!Wf&&console&&typeof console.error==`function`){var e;(e=console).error.apply(e,arguments)}}function Kf(e){if(e&&kf(e)===`object`&&e.prefix&&e.iconName&&e.icon)return e;if(xd.icon)return xd.icon(e);if(e===null)return null;if(kf(e)===`object`&&e.prefix&&e.iconName)return e;if(Array.isArray(e)&&e.length===2)return{prefix:e[0],iconName:e[1]};if(typeof e==`string`)return{prefix:`fas`,iconName:e}}var qf=b({name:`FontAwesomeIcon`,props:{border:{type:Boolean,default:!1},fixedWidth:{type:Boolean,default:!1},flip:{type:[Boolean,String],default:!1,validator:function(e){return[!0,!1,`horizontal`,`vertical`,`both`].indexOf(e)>-1}},icon:{type:[Object,Array,String],required:!0},mask:{type:[Object,Array,String],default:null},maskId:{type:String,default:null},listItem:{type:Boolean,default:!1},pull:{type:String,default:null,validator:function(e){return[`right`,`left`].indexOf(e)>-1}},pulse:{type:Boolean,default:!1},rotation:{type:[String,Number],default:null,validator:function(e){return[90,180,270].indexOf(Number.parseInt(e,10))>-1}},rotateBy:{type:Boolean,default:!1},swapOpacity:{type:Boolean,default:!1},size:{type:String,default:null,validator:function(e){return[`2xs`,`xs`,`sm`,`lg`,`xl`,`2xl`,`1x`,`2x`,`3x`,`4x`,`5x`,`6x`,`7x`,`8x`,`9x`,`10x`].indexOf(e)>-1}},spin:{type:Boolean,default:!1},transform:{type:[String,Object],default:null},symbol:{type:[Boolean,String],default:!1},title:{type:String,default:null},titleId:{type:String,default:null},inverse:{type:Boolean,default:!1},bounce:{type:Boolean,default:!1},shake:{type:Boolean,default:!1},beat:{type:Boolean,default:!1},fade:{type:Boolean,default:!1},beatFade:{type:Boolean,default:!1},flash:{type:Boolean,default:!1},spinPulse:{type:Boolean,default:!1},spinReverse:{type:Boolean,default:!1},widthAuto:{type:Boolean,default:!1},canvasSquare:{type:Boolean,default:!1},canvasRoomy:{type:Boolean,default:!1},gradientFill:{type:Object,default:null,validator:function(e){return typeof e.id!=`string`||!e.id?(console.warn(`FontAwesomeIcon: gradientFill.id must be a non-empty string`),!1):e.type!==`linear`&&e.type!==`radial`?(console.warn(`FontAwesomeIcon: gradientFill.type must be "linear" or "radial"`),!1):!0}},flip360:{type:Boolean,default:!1},buzz:{type:Boolean,default:!1},float:{type:Boolean,default:!1},jello:{type:Boolean,default:!1},spinSnap:{type:Boolean,default:!1},spinSnap4:{type:Boolean,default:!1},spinSnap8:{type:Boolean,default:!1},swing:{type:Boolean,default:!1},wag:{type:Boolean,default:!1}},setup:function(e,t){var n=t.attrs,r=o(function(){return Kf(e.icon)}),i=o(function(){return jf(`classes`,Mf(e))}),a=o(function(){return jf(`transform`,typeof e.transform==`string`?xd.transform(e.transform):e.transform)}),s=o(function(){return jf(`mask`,Kf(e.mask))}),c=o(function(){var t=$($($($({},i.value),a.value),s.value),{},{symbol:e.symbol,maskId:e.maskId});return t.title=e.title,t.titleId=e.titleId,Sd(r.value,t)});A(c,function(e){if(!e)return Gf(`Could not find one or more icon(s)`,r.value,s.value)},{immediate:!0}),e.gradientFill&&e.symbol&&Gf(`gradientFill is not supported when symbol is true and will be ignored`);var l=o(function(){return c.value?Uf(c.value.abstract[0],{gradientFill:e.symbol?null:e.gradientFill},n):null});return function(){return l.value}}});b({name:`FontAwesomeLayers`,props:{fixedWidth:{type:Boolean,default:!1}},setup:function(e,t){var n=t.slots,r=yd.familyPrefix,i=o(function(){return[`${r}-layers`].concat(Ef(e.fixedWidth?[`${r}-fw`]:[]))});return function(){return s(`div`,{class:i.value},n.default?n.default():[])}}}),b({name:`FontAwesomeLayersText`,props:{value:{type:[String,Number],default:``},transform:{type:[String,Object],default:null},counter:{type:Boolean,default:!1},position:{type:String,default:null,validator:function(e){return[`bottom-left`,`bottom-right`,`top-left`,`top-right`].indexOf(e)>-1}}},setup:function(e,t){var n=t.attrs,r=yd.familyPrefix,i=o(function(){return jf(`classes`,[].concat(Ef(e.counter?[`${r}-layers-counter`]:[]),Ef(e.position?[`${r}-layers-${e.position}`]:[])))}),a=o(function(){return jf(`transform`,typeof e.transform==`string`?xd.transform(e.transform):e.transform)}),s=o(function(){var t=Cd(e.value.toString(),$($({},a.value),i.value)).abstract;return e.counter&&(t[0].attributes.class=t[0].attributes.class.replace(`fa-layers-text`,``)),t[0]}),c=o(function(){return Uf(s.value,{},n)});return function(){return c.value}}}),yd.autoAddCss=!1,bd.add(Od,Fd,zd,wd,Ud,$d,jd,Rd,kd,pf,of,Td,hf,Gd,Md,Dd,Wd,sf,ef,Ed,cf,Qd,Ad,gf,rf,Yd,lf,mf,Xd,Vd,ff,uf,tf,Pd,Id,Hd,Kd,Zd,qd,Jd,Ld,af,Bd,df,Nd,nf,_f,vf),_e&&document.documentElement.classList.add(`embedded`),Vt();var Jf=ke({render:()=>[s(Ga),s(Za)]});Jf.component(`Icon`,qf),Jf.config.errorHandler=(e,t,n)=>{console.error(e);let r=e instanceof Error?e:Error(String(e));we(`${r.name}: ${r.message} (vue: ${n})`,r.stack)},window.addEventListener(`error`,e=>{e.error instanceof Error?we(`${e.error.name}: ${e.error.message}`,e.error.stack):e.message&&we(e.message,`${e.filename}:${e.lineno}`)}),window.addEventListener(`unhandledrejection`,e=>{let t=e.reason;we(`Unhandled rejection: ${t instanceof Error?`${t.name}: ${t.message}`:String(t)}`,t instanceof Error?t.stack:void 0)});var Yf=2500;Promise.race([de,new Promise(e=>setTimeout(e,Yf))]).then(()=>{Jf.mount(`#app`),requestAnimationFrame(()=>requestAnimationFrame(()=>document.documentElement.classList.add(`theme-ready`)))});export{on as a,wt as c,tt as d,et as f,ln as i,vt as l,Si as n,Wt as o,kr as r,jt as s,Ni as t,ft as u};