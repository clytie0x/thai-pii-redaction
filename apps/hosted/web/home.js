document.documentElement.classList.add('js');
document.addEventListener('DOMContentLoaded', function(){
    const modeData={
      scan:{
        stage:'PRIVACY SCAN',
        title:'ตรวจพบข้อมูลส่วนบุคคล 3 รายการ',
        badge:'READY TO REVIEW',
        leftLabel:'ข้อความตัวอย่างสังเคราะห์',
        left:'คุณสมชาย · 1-2345-67890-12-3<br>โทร 081-234-5678',
        rightLabel:'สิ่งที่ตรวจพบ',
        right:'<span class="mask">ชื่อบุคคล</span> 1 รายการ<br><span class="mask">เลขบัตรประชาชน</span> 1 รายการ<br><span class="mask">เบอร์โทร</span> 1 รายการ',
        proof:['ตำแหน่ง','ประเภท','จำนวน 03']
      },
      safe:{
        stage:'SAFE AI',
        title:'แสดงหลักฐานหลัง Safe AI ทำงาน',
        badge:'PROVIDER BOUNDARY',
        leftLabel:'ข้อความที่ส่งให้ provider',
        left:'สรุปข้อมูลของ <span class="mask">[ชื่อบุคคล]</span><br>โทร <span class="mask">[เบอร์โทร]</span>',
        rightLabel:'หลักฐานการส่งต่อ',
        right:'ผ่าน outbound policy check<br>ส่งไป thaillm-8b โดยไม่มี fallback',
        proof:['protected input','provider เดียว','mapping ไม่ถูกส่ง']
      },
      report:{
        stage:'PDPA REPORT',
        title:'สรุปสัญญาณความเสี่ยงสำหรับตรวจทาน',
        badge:'HEURISTIC REPORT',
        leftLabel:'ข้อมูลที่วิเคราะห์',
        left:'ประเภทข้อมูล <span class="pii">Identity</span><br>ช่องทางใช้งาน <span class="pii">AI</span>',
        rightLabel:'ผลเชิงสัญญาณ',
        right:'ระดับทบทวน <span class="mask">สูง</span><br>ข้อเสนอแนะ <span class="mask">ตรวจสอบเพิ่ม</span>',
        proof:['คะแนน','เหตุผล','ไม่ใช่คำรับรอง']
      }
    };

    const featureButtons=Array.from(document.querySelectorAll('.feature-btn'));
    const featureStage=document.querySelector('#featurePanel');
    const modeCard=document.querySelector('#modeCard');
    const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
    let workflowSwapTimer=0;
    let workflowEndTimer=0;

    document.querySelector('#skipLink').addEventListener('click',function(event){
      event.preventDefault();
      const main=document.querySelector('#main-content');
      location.hash='main-content';
      setTimeout(function(){main.focus()},0);
    });

    function renderMode(button){
      const data=modeData[button.dataset.mode];
      featureButtons.forEach(function(item){
        const selected=item===button;
        item.classList.toggle('active',selected);
        item.setAttribute('aria-selected',String(selected));
        item.tabIndex=selected?0:-1;
      });
      featureStage.setAttribute('aria-labelledby',button.id);
      clearTimeout(workflowSwapTimer);
      clearTimeout(workflowEndTimer);
      featureStage.classList.remove('changing');
      modeCard.classList.remove('switching');

      const update=function(){
        document.querySelector('#stageMode').textContent=data.stage;
        document.querySelector('#modeTitle').textContent=data.title;
        document.querySelector('#modeBadge').textContent=data.badge;
        document.querySelector('#leftLabel').textContent=data.leftLabel;
        document.querySelector('#leftCopy').innerHTML=data.left;
        document.querySelector('#rightLabel').textContent=data.rightLabel;
        document.querySelector('#rightCopy').innerHTML=data.right;
        document.querySelector('#modeProof').innerHTML=data.proof.map(function(item){return '<span>'+item+'</span>'}).join('');
        modeCard.classList.remove('switching');
      };

      if(reduceMotion){update();return}
      void featureStage.offsetWidth;
      featureStage.classList.add('changing');
      modeCard.classList.add('switching');
      workflowSwapTimer=setTimeout(update,230);
      workflowEndTimer=setTimeout(function(){featureStage.classList.remove('changing')},520);
    }
    featureButtons.forEach(function(button,index){
      button.addEventListener('click',function(){renderMode(button)});
      button.addEventListener('keydown',function(event){
        let target=index;
        if(event.key==='ArrowDown' || event.key==='ArrowRight') target=(index+1)%featureButtons.length;
        else if(event.key==='ArrowUp' || event.key==='ArrowLeft') target=(index-1+featureButtons.length)%featureButtons.length;
        else if(event.key==='Home') target=0;
        else if(event.key==='End') target=featureButtons.length-1;
        else return;
        event.preventDefault();
        featureButtons[target].focus();
        renderMode(featureButtons[target]);
      });
    });

    const revealItems=document.querySelectorAll('.reveal');
    if('IntersectionObserver' in window && !reduceMotion){
      const observer=new IntersectionObserver(function(entries){
        entries.forEach(function(entry){
          if(entry.isIntersecting){
            entry.target.classList.add('in');
            observer.unobserve(entry.target);
          }
        });
      },{threshold:.1});
      revealItems.forEach(function(item){observer.observe(item)});
    }else{
      revealItems.forEach(function(item){item.classList.add('in')});
    }

    const heroPoster=document.querySelector('#heroPoster');
    const heroPosterState=document.querySelector('#heroPosterState');
    const replayButton=document.querySelector('#heroReplay');
    const rawViewButton=document.querySelector('#rawViewButton');
    const protectedViewButton=document.querySelector('#protectedViewButton');
    const rawPanel=document.querySelector('#rawPanel');
    const protectedPanel=document.querySelector('#protectedPanel');
    const heroFindingCount=document.querySelector('#heroFindingCount');
    const rawReceipt=document.querySelector('#rawReceipt');
    const visual=document.querySelector('.visual');
    const mobileHeroLayout=matchMedia('(max-width: 680px)');
    let heroTimers=[];
    let heroRunning=false;

    function syncHeroPanelAccess(){
      const ready=heroPoster.dataset.phase==='review';
      const view=heroPoster.dataset.mobileView;
      if(mobileHeroLayout.matches){
        rawPanel.setAttribute('aria-hidden',String(view!=='raw'));
        protectedPanel.setAttribute('aria-hidden',String(view!=='protected' || !ready));
      }else{
        rawPanel.setAttribute('aria-hidden','false');
        protectedPanel.setAttribute('aria-hidden',String(!ready));
      }
    }
    function setMobileView(view){
      if(view==='protected' && heroPoster.dataset.phase!=='review') return;
      heroPoster.dataset.mobileView=view;
      rawViewButton.setAttribute('aria-selected',String(view==='raw'));
      protectedViewButton.setAttribute('aria-selected',String(view==='protected'));
      rawViewButton.tabIndex=view==='raw'?0:-1;
      protectedViewButton.tabIndex=view==='protected'?0:-1;
      syncHeroPanelAccess();
    }
    rawViewButton.addEventListener('click',function(){setMobileView('raw')});
    protectedViewButton.addEventListener('click',function(){setMobileView('protected')});
    [rawViewButton,protectedViewButton].forEach(function(button){
      button.addEventListener('keydown',function(event){
        if(event.key!=='ArrowLeft' && event.key!=='ArrowRight' && event.key!=='Home' && event.key!=='End') return;
        event.preventDefault();
        let target=button===rawViewButton?protectedViewButton:rawViewButton;
        if(event.key==='Home') target=rawViewButton;
        if(event.key==='End') target=protectedViewButton;
        if(!target.disabled){target.focus();setMobileView(target===rawViewButton?'raw':'protected')}
      });
    });

    function clearHeroTimers(){
      heroTimers.forEach(function(timer){clearTimeout(timer)});
      heroTimers=[];
    }
    function resetHeroSequence(){
      clearHeroTimers();
      heroPoster.classList.add('resetting');
      heroPoster.dataset.phase='raw';
      heroPoster.dataset.mobileView='raw';
      heroFindingCount.textContent='—';
      rawReceipt.setAttribute('aria-hidden','true');
      rawViewButton.setAttribute('aria-selected','true');
      protectedViewButton.setAttribute('aria-selected','false');
      rawViewButton.tabIndex=0;
      protectedViewButton.tabIndex=-1;
      protectedViewButton.disabled=true;
      heroPosterState.textContent='ตัวอย่างข้อมูลสังเคราะห์';
      syncHeroPanelAccess();
      void heroPoster.offsetWidth;
      heroPoster.classList.remove('resetting');
    }
    function finishHeroSequence(){
      heroPoster.dataset.phase='review';
      heroFindingCount.textContent='03';
      rawReceipt.setAttribute('aria-hidden','false');
      heroPosterState.textContent='พบ 3 รายการ · พร้อมตรวจทาน';
      protectedViewButton.disabled=false;
      syncHeroPanelAccess();
      heroRunning=false;
      replayButton.setAttribute('aria-disabled','false');
    }
    function runHeroSequence(){
      if(heroRunning) return;
      resetHeroSequence();
      heroRunning=true;
      replayButton.setAttribute('aria-disabled','true');
      if(reduceMotion){
        finishHeroSequence();
        return;
      }
      heroTimers.push(setTimeout(function(){
        heroPoster.dataset.phase='scanning';
        heroPosterState.textContent='กำลังตรวจจับ';
      },650));
      heroTimers.push(setTimeout(function(){
        finishHeroSequence();
      },2050));
    }
    replayButton.addEventListener('click',function(){if(!heroRunning) runHeroSequence()});
    mobileHeroLayout.addEventListener('change',syncHeroPanelAccess);
    resetHeroSequence();
    if(reduceMotion){
      finishHeroSequence();
    }else if('IntersectionObserver' in window){
      const heroObserver=new IntersectionObserver(function(entries){
        if(entries.some(function(entry){return entry.isIntersecting})){
          heroObserver.disconnect();
          runHeroSequence();
        }
      },{threshold:.28});
      heroObserver.observe(visual);
    }else{
      runHeroSequence();
    }

    if(!reduceMotion){
      let pointerFrame=0;
      let pointerX=0;
      let pointerY=0;
      visual.addEventListener('pointermove',function(event){
        const rect=visual.getBoundingClientRect();
        pointerX=(event.clientX-rect.left)/rect.width-.5;
        pointerY=(event.clientY-rect.top)/rect.height-.5;
        if(pointerFrame) return;
        pointerFrame=requestAnimationFrame(function(){
          heroPoster.style.setProperty('--tilt-y',(pointerX*2.2)+'deg');
          heroPoster.style.setProperty('--tilt-x',(-pointerY*1.6)+'deg');
          pointerFrame=0;
        });
      });
      visual.addEventListener('pointerleave',function(){
        if(pointerFrame){cancelAnimationFrame(pointerFrame);pointerFrame=0}
        pointerX=0;
        pointerY=0;
        heroPoster.style.setProperty('--tilt-y','0deg');
        heroPoster.style.setProperty('--tilt-x','0deg');
      });
    }
});
