"""MaRs-IB SF1: published 3PL scoring, local responses, explicitly synthetic EEG demo."""
import math, time, uuid, random
import numpy as np
from matrix_items import ITEMS, PRACTICE
VERSION='mars-sf1-2023-eap-v1'


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
                reference_percentile=round(50*(1+math.erf(mean/math.sqrt(2))),1),version=VERSION,
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


def initialize(record):
    record.update(answers=[None]*12,matrix_version=VERSION,matrix_state=dict(stage='practice',index=0,token=None),matrix_result=estimate([None]*12))


def open_item(record):
    s=record['matrix_state'];items=PRACTICE if s['stage']=='practice' else ITEMS
    if s['index']>=len(items):raise ValueError('Matrix test is complete')
    if not s.get('token'):
        s.update(token=uuid.uuid4().hex,shown_at=time.time(),order=random.SystemRandom().sample([1,2,3,4],4))
        record.setdefault('answer_events',[]).append(dict(time=s['shown_at'],index=s['index'],value=None,stage=s['stage'],item_id=items[s['index']]['id']))
    item=items[s['index']]
    return dict(stage=s['stage'],index=s['index'],token=s['token'],stem=item['images'][0],
                choices=[dict(value=k,image=item['images'][k]) for k in s['order']],remaining=max(0,30-(time.time()-s['shown_at'])),server_time=time.time())


def answer(record,token,choice):
    s=record['matrix_state']
    if token==record.get('matrix_last_token'):return record['matrix_last_response']
    if not token or token!=s.get('token'):raise ValueError('This puzzle is no longer active')
    if choice is not None and (type(choice) is not int or choice not in (1,2,3,4)):raise ValueError('Choose one of four patterns')
    elapsed=time.time()-s['shown_at'];timeout=elapsed>=30
    if choice is None and not timeout:raise ValueError('Choose a pattern before time runs out')
    value=0 if timeout else choice;correct=value==1;stage=s['stage'];index=s['index']
    record.setdefault('answer_events',[]).append(dict(time=time.time(),index=index,value=value,stage=stage,seconds=elapsed,timeout=timeout,correct=correct))
    if stage=='test':
        record['answers'][index]=value;record['matrix_result']=estimate(record['answers']);s['index']+=1
    elif correct:
        s['index']+=1
        if s['index']==len(PRACTICE):s.update(stage='test',index=0)
    s['token']=None
    response=dict(practice=stage=='practice',correct=correct if stage=='practice' else None,complete=s['stage']=='test' and s['index']==len(ITEMS),estimate=record['matrix_result'])
    record['matrix_last_token']=token;record['matrix_last_response']=response
    return response
