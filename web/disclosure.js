/* Public display only: task markers contain timing/counts, never answer text. */
const disclosureQuestions=[
 ['Your biggest insecurity?','Something you’re afraid people notice?','Your most embarrassing habit?','Something you pretend to understand?','Something you’ve exaggerated to impress?','The very worst part of this class—for the love of God, what must change?','Your best physical feature?','Something about your appearance you’d change?','A guilty pleasure?','A compliment you secretly want?','Something you’re jealous of?','Your most awkward recent moment?','Something you do to fit in?','A criticism that really stings?','A skill you’re embarrassed not to have?','An opinion you hesitate to share?','What do people get wrong about you?','Something you wish you’d said?','Describe yourself, including one insecurity.','What were you most reluctant to answer?'],
 ['Something found in a kitchen?','A musical instrument?','An animal that lives in water?','Two forms of transportation?','A movie genre?','Something powered by a battery?','A type of book?','A tool used for measuring?','Something people recycle?','What does a thermometer measure?','What does a plant need to grow?','A common building material?','A way to store information?','What does a library lend?','One way to organize classroom supplies?','Three parts of a cell?','Three parts of an atom?','How do you make a sandwich?','Describe a cell and its main parts.','How do you wash your hands?']
];
async function disclosureRun(session,id){
 const positions=[0,0];let lastReminder=-Infinity;
 for(const item of session.plan){
  $('stageInstruction').textContent='Rest · relax your jaw';$('stimulus').textContent='Brief break';await delay(item.isi,id);
  let input,prompt,warning,skip,next,questionStart,dirty=false,movingSince=null,hideAt=0;
  const ci=item.condition_index;
  const log=(action)=>marker({kind:'behavior',task:'disclosure',index:item.index,condition_index:ci,question_index:positions[ci],action,characters:input.value.length,rt_ms:(now()-questionStart)*1000}).catch(e=>toast(e.message));
  const advance=async(action)=>{if(!active||id!==runID||skip.disabled)return;skip.disabled=next.disabled=true;await log(action);positions[ci]++;input.value='';dirty=false;showQuestion();};
  const showQuestion=()=>{questionStart=now();prompt.textContent=disclosureQuestions[ci][positions[ci]]||'All questions answered. Rest quietly.';const done=positions[ci]>=disclosureQuestions[ci].length;input.disabled=skip.disabled=next.disabled=done;if(!done)input.focus({preventScroll:true});};
  $('stageInstruction').textContent='LIVE to the audience · Enter: next · Skip anytime';
  const onset=await present(item,session,el=>{el.textContent='';el.style.fontSize='24px';const panel=document.createElement('section');panel.className='disclosure-panel';prompt=document.createElement('h2');input=document.createElement('textarea');input.rows=3;input.maxLength=2000;input.setAttribute('aria-label','Answer — visible live to the audience');input.placeholder='Type your answer — visible live';input.autocomplete='off';skip=document.createElement('button');skip.textContent='Skip';next=document.createElement('button');next.textContent='Next · Enter';warning=document.createElement('p');warning.className='disclosure-reminder';warning.textContent='Keep your head still; keep your gaze on the keyboard or screen';warning.style.visibility='hidden';const buttons=document.createElement('div');buttons.className='button-row';buttons.append(skip,next);panel.append(prompt,input,buttons,warning);el.append(panel);skip.onclick=()=>advance('skipped');next.onclick=()=>advance('answered');input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();advance('answered')}};input.oninput=()=>{dirty=true};showQuestion();});
  try{while(now()-onset<30){const elapsed=now()-onset;$('stageProgress').textContent=`${session.conditions[ci]} · Block ${item.index+1}/4 · ${Math.ceil(30-elapsed)} s`;
   if(state?.motion?.moving){movingSince??=now();if(now()-movingSince>=.6&&now()-lastReminder>=8){lastReminder=now();hideAt=now()+2.5;}}else movingSince=null;
   warning.style.visibility=now()<hideAt?'visible':'hidden';await delay(100,id);
  }if(dirty)await log('block-ended');await marker({kind:'offset',index:item.index});}
  finally{input.value='';input.disabled=true;skip.disabled=next.disabled=true;}
 }
}
