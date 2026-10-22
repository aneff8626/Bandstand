"""MaRs-IB SF1: published 3PL scoring, local responses, explicitly synthetic EEG demo."""
import math, time, uuid, random
import numpy as np
from matrix_items import ITEMS, PRACTICE
VERSION='mars-sf1-2023-eap-v1'
from matrix_original import ITEMS as PILOT_ITEMS, BANK_VERSION, image as pilot_image, item_hash

def percentile(theta):
    return 50*(1+math.erf(float(theta)/math.sqrt(2)))


def estimate(answers):
    if len(answers)!=len(ITEMS) or any(v is not None and (type(v) is not int or v not in range(5)) for v in answers):
        raise ValueError('Invalid matrix answers')
    completed=[(item,value) for item,value in zip(ITEMS,answers) if value is not None]
    if not completed:return dict(score=None,interval=None,answered=0,correct=0,version=VERSION)
    theta=np.linspace(-5,5,2001);logp=-theta**2/2
    for item,value in completed:
        # Authors use alpha*theta-beta, NOT alpha*(theta-beta).
        p=item['gamma']+(1-item['gamma'])/(1+np.exp(-(item['alpha']*theta-item['beta'])))
        logp+=np.log(p if value==1 else 1-p)
    weights=np.exp(logp-logp.max());weights/=weights.sum();cdf=np.cumsum(weights)
    mean=float(weights@theta);interval=np.interp([.025,.975],cdf,theta)
    return dict(score=round(100+15*mean,1),interval=[round(100+15*v,1) for v in interval],
                theta=mean,answered=len(completed),correct=sum(v==1 for _,v in completed),
                reference_percentile=round(percentile(mean),1),percentile_interval=[round(percentile(v),1) for v in interval],version=VERSION,
                reference='US adult online research sample; not representative population IQ norms',
                partial=len(completed)<len(ITEMS))


def eeg_demo(summary):
    """Display plumbing only. Arbitrary fixed projection, no learned IQ association."""
    values=[]
    for channels in summary.get('phases',{}).values():
        for channel in ('AF7','AF8','TP9','TP10'):
            v=channels.get(channel,{})
            if v.get('n',0)>=3 and v.get('db'):
                d=v['db'];values.append(math.tanh((d[1]-d[0]+.3*(d[2]-d[3]))/12))
    return dict(score=round(100+15*float(np.mean(values)),1) if values else None,
                synthetic=True,version='arbitrary-eeg-display-v1',
                label='EEG demo — synthetic mapping, no demonstrated IQ accuracy')


def initialize(record,pilot_count=3):
    rng=random.SystemRandom()
    families=sorted(set(item['family'] for item in PILOT_ITEMS))
    selected=[rng.choice([item for item in PILOT_ITEMS if item['family']==family]) for family in rng.sample(families,pilot_count)]
    # Keep reference-item order fixed; insert pilots into distinct internal gaps.
    gaps=dict(zip(rng.sample(range(1,len(ITEMS)),pilot_count),selected))
    plan=[]
    for index,item in enumerate(ITEMS):
        if index in gaps:plan.append(dict(source='original-pilot',id=gaps[index]['id']))
        plan.append(dict(source='reference',index=index,id=item['id']))
    record.update(answers=[None]*12,matrix_version=VERSION,matrix_state=dict(stage='practice',index=0,token=None),matrix_result=estimate([None]*12),
                  matrix_plan=plan,matrix_pilot_version=BANK_VERSION,matrix_pilot_responses=[],matrix_administration='mixed-pilot-v1' if pilot_count else 'reference-only-v1')


def current_item(record):
    s=record['matrix_state']
    if s['stage']=='practice':return PRACTICE[s['index']],dict(source='practice',index=s['index'])
    plan=record.get('matrix_plan') or [dict(source='reference',index=i,id=item['id']) for i,item in enumerate(ITEMS)]
    if s['index']>=len(plan):raise ValueError('Matrix test is complete')
    entry=plan[s['index']]
    return (next(item for item in PILOT_ITEMS if item['id']==entry['id']) if entry['source']=='original-pilot' else ITEMS[entry['index']]),entry


def open_item(record):
    s=record['matrix_state'];item,entry=current_item(record)
    original=entry['source']=='original-pilot'
    if not s.get('token'):
        s.update(token=uuid.uuid4().hex,shown_at=time.time(),order=random.SystemRandom().sample([1,2,3,4],4))
        record.setdefault('answer_events',[]).append(dict(time=s['shown_at'],index=s['index'],value=None,stage=s['stage'],item_id=item['id'],source=entry['source'],option_order=s['order'][:],
                                                        item_version=BANK_VERSION if original else VERSION))
    return dict(stage=s['stage'],index=s['index'],total=len(record.get('matrix_plan') or ITEMS),token=s['token'],
                stem=pilot_image(item) if original else item['images'][0],
                choices=[dict(value=k,image=pilot_image(item,k) if original else item['images'][k]) for k in s['order']],
                remaining=max(0,30-(time.time()-s['shown_at'])),server_time=time.time())


def answer(record,token,choice):
    s=record['matrix_state']
    if token==record.get('matrix_last_token'):return record['matrix_last_response']
    if not token or token!=s.get('token'):raise ValueError('This puzzle is no longer active')
    if choice is not None and (type(choice) is not int or choice not in (1,2,3,4)):raise ValueError('Choose one of four patterns')
    elapsed=time.time()-s['shown_at'];timeout=elapsed>=30
    if choice is None and not timeout:raise ValueError('Choose a pattern before time runs out')
    value=0 if timeout else choice;correct=value==1;stage=s['stage'];index=s['index'];item,entry=current_item(record)
    event=dict(time=time.time(),index=index,value=value,stage=stage,seconds=elapsed,timeout=timeout,correct=correct,item_id=item['id'],source=entry['source'],option_order=s['order'][:],shown_at=s['shown_at'])
    record.setdefault('answer_events',[]).append(event)
    if stage=='test':
        if entry['source']=='original-pilot':
            record.setdefault('matrix_pilot_responses',[]).append({**event,'version':BANK_VERSION,'family':item['family'],'stimulus_sha256':item_hash(item)})
        else:
            record['answers'][entry['index']]=value;record['matrix_result']=estimate(record['answers'])
        s['index']+=1
    elif correct:
        s['index']+=1
        if s['index']==len(PRACTICE):s.update(stage='test',index=0)
    s['token']=None
    response=dict(practice=stage=='practice',correct=correct if stage=='practice' else None,complete=s['stage']=='test' and s['index']==len(record.get('matrix_plan') or ITEMS),estimate=record['matrix_result'])
    record['matrix_last_token']=token;record['matrix_last_response']=response
    return response
