import io, html
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.graphics.shapes import Drawing, Line, String, PolyLine
from protocols import SOURCES

def make_report(session,analysis,events,directory):
    output=io.BytesIO(); styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='SmallPrint',fontSize=8,leading=11))
    doc=SimpleDocTemplate(output,pagesize=(612,792),rightMargin=44,leftMargin=44,topMargin=44,bottomMargin=44)
    story=[]
    def p(text,style='BodyText'): return Paragraph(html.escape(str(text)),styles[style])
    def fp(value):return 'p < .001' if value<.001 else f'p = {value:.3f}'
    presented=sum(1 for e in events if e.get('kind')=='stimulus');planned=session.get('trials_planned')
    story.extend([p('BANDSTAND / SESSION REPORT','Title'),p(session['title'],'Heading1'),p('SIMULATED DATA - NOT A HEADSET RECORDING' if session['source']=='simulation' else 'LIVE MUSE EEG'),p(session['id'],'SmallPrint'),Spacer(1,14)])
    summary=[['Acquisition',f"Muse 2 / 256 Hz / {session['source']}"],['Electrodes',', '.join(session['channels'])],['Reference','FPz hardware; reward task additionally re-referenced to TP9/TP10 mean' if session['protocol']=='reward' else 'FPz hardware reference'],['Measure',f"{session['metric']} / {session['window'][0]*1000:g}-{session['window'][1]*1000:g} ms" if session['mode']=='erp' else f"Band power {session['band'][0]:g}–{session['band'][1]:g} Hz; {session['window'][0]:g}–{session['window'][1]:g} s"],['State','Recording snapshot' if session['running'] else session.get('end_reason','ended')],['Completed',f"{presented} of {planned} planned {'blocks' if session['mode']!='erp' else 'trials'}" if planned else str(presented)],['Random seed',str(session['seed'])]]
    table=Table([[p(c,'SmallPrint') for c in row] for row in summary],colWidths=[100,424]); table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#edf3f1')),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8)])); story.append(table)
    story.extend([p('Condition results','Heading2')])
    rows=[['Condition','Usable','Rejected','Mean','SE']]
    for g in analysis.get('groups',[]): rows.append([g['label'],str(g['accepted']),str(g['rejected']),f"{g['mean']:.4g} {analysis['unit']}" if g['mean'] is not None else 'Pending',f"{g['se']:.4g}" if g['se'] is not None else '-'])
    table=Table([[p(c,'SmallPrint') for c in row] for row in rows],colWidths=[164,65,65,115,115]); table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3f1')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8)])); story.append(table)
    if analysis.get('spectral'):
        story.append(p('Channel-local spectral results','Heading2'))
        story.append(p(f"Reviewed band: {analysis['band'][0]:g}–{analysis['band'][1]:g} Hz. Descriptive mean and SD use non-overlapping clean 2-second segments; inference resamples contiguous chunks within recorded periods. Power in dB re 1 µV².",'SmallPrint'))
        for channel,value in analysis['channels'].items():
            story.append(p(channel,'Heading3'))
            for g in value['groups']:
                score=f"{g.get('descriptive_mean',g['mean']):.3f} dB" if g.get('descriptive_mean',g['mean']) is not None else 'Pending'
                story.append(p(f"{g['label']}: {g['accepted']} usable / {g['rejected']} rejected blocks; {g['clean_seconds']:.1f} clean seconds; mean {score}."))
            stat=value['stats'];story.append(p((f"Exploratory moving-block bootstrap: difference {stat['difference']:.2f} dB, 95% interval {stat['ci95'][0]:.2f} to {stat['ci95'][1]:.2f}, {fp(stat['p'])}" if stat.get('method')=='moving-block bootstrap' else f"Exploratory t = {stat['t']:.2f}, {fp(stat['p'])} ({stat['label']})") if stat.get('ready') else stat['reason']))
    stat=analysis.get('stats',{})
    story.append(p(f"Exploratory Welch t({stat['df']:.1f}) = {stat['t']:.2f}, {fp(stat['p'])} ({stat['label']})" if stat.get('ready') else stat.get('reason','No trials yet.')))
    story.append(p(('Spectral comparisons use clean non-overlapping segments and a moving-block bootstrap within recorded periods. Approximate intervals and p-values assume local stability; they do not separate condition effects from order, drift or contact changes. Repeated looks and band selection are exploratory.' if analysis.get('spectral') else 'Trial-level comparisons within one participant. Repeated testing is uncorrected; trials are not independent participants. Pointwise 95% intervals and SE describe accepted trials, not population uncertainty. Ten usable trials is a display threshold, not a power guarantee.'),'SmallPrint'))
    if session['mode']=='erp' and analysis.get('times'):
        drawing=Drawing(524,190); drawing.add(Line(40,30,510,30)); drawing.add(Line(40,30,40,175))
        waves=[g['erp']['mean'] for g in analysis['groups'] if g['erp']]; limit=max([10]+[abs(v) for w in waves for v in w]); times=analysis['times']; palette=['#127b6c','#c67a2e']
        for i,g in enumerate(analysis['groups']):
            if not g['erp']: continue
            pts=[]
            for t,v in zip(times,g['erp']['mean']): pts.extend([40+(t+.2)*470,100+v/limit*65])
            drawing.add(PolyLine(pts,strokeColor=colors.HexColor(palette[i]),strokeWidth=1.3)); drawing.add(String(55+i*210,180,g['label'][:35],fontSize=9,fillColor=colors.HexColor(palette[i])))
        drawing.add(Line(40,100,510,100,strokeColor=colors.HexColor('#b8c4c0'),strokeDashArray=[2,2]))
        for ms in (-200,0,200,400,600,800):
            x=40+(ms/1000+.2)*470;drawing.add(Line(x,27,x,33));drawing.add(String(x-10,18,f'{ms}',fontSize=7))
        drawing.add(String(150,4,'Time relative to '+('feedback' if session['protocol']=='reward' else 'stimulus')+' (ms)',fontSize=9)); drawing.add(String(0,158,f'±{limit:.0f} µV',fontSize=8)); story.append(drawing)
    story.extend([p('Protocol and controls','Heading2'),p(session['notes']),p('Timing and processing','Heading2'),p(session['timing']),p(session['analysis'])])
    story.append(p('Signal quality is an EEG-derived estimate, not measured impedance. Artifact labels are probable; no dedicated EOG/EMG channels are available. Threshold defaults are tunable heuristics and are not clinically validated Muse cutoffs.','SmallPrint'))
    story.append(p('Thresholds: '+', '.join(f'{k}={v}' for k,v in session['thresholds'].items()),'SmallPrint'))
    story.append(p('Display calibration: '+str(session.get('calibration',{})),'SmallPrint'))
    if session.get('electrode_warning'): story.append(p('Electrode selection differs from the task default. Canonical effect electrodes may be absent on Muse.'))
    behavior=analysis.get('behavior')
    if behavior and behavior.get('kind')=='flanker':
        story.append(p('Task behaviour','Heading2'))
        for c in behavior['conditions']:
            acc=f"{c['accuracy']:.0%}" if c['accuracy'] is not None else '-';rt=f"{c['median_rt_ms']:.0f} ms" if c['median_rt_ms'] is not None else '-'
            story.append(p(f"{c['label']}: {c['presented']} trials; {acc} correct; {c['errors']} errors; {c['missed']} missed; median correct RT {rt}."))
        if behavior.get('congruency_rt_ms') is not None:story.append(p(f"Congruency effect (incongruent − congruent median RT): {behavior['congruency_rt_ms']:.0f} ms."))
        story.append(p(behavior['note'],'SmallPrint'))
    if behavior and behavior.get('kind')=='reward':
        story.append(p('Choice behaviour','Heading2'))
        share=f"{behavior['blue_proportion']:.0%}" if behavior['blue_proportion'] is not None else '-'
        story.append(p(f"{behavior['choices']} choices ({behavior['skipped']} skipped); blue chosen {share}; {behavior['wins']} wins."))
        for r in behavior['by_choice']:
            rate=f"{r['win_rate']:.0%}" if r['win_rate'] is not None else '-';rt=f"; median choice time {r['median_rt_ms']:.0f} ms" if r['median_rt_ms'] is not None else ''
            story.append(p(f"{r['choice'].capitalize()}: chosen {r['n']} times; won {r['wins']} ({rate}){rt}."))
        story.append(p(behavior['note'],'SmallPrint'))
    behaviors=[e for e in events if e.get('kind')=='behavior']
    if behaviors:
        story.append(p('Behavioral performance','Heading2'))
        for phase in ['pre','post']:
            items=[e for e in behaviors if e.get('phase')==phase]
            if items:
                accuracy=sum(bool(e.get('correct')) for e in items)/len(items)
                rt=sum(e.get('rt_ms',0) for e in items)/len(items)
                story.append(p(f'{phase.capitalize()}: {len(items)} problems; {accuracy:.1%} correct; mean response time {rt:.0f} ms.'))
    if session['mode']=='bio':
        import csv, numpy as np
        with open(directory/'bandpower.csv') as f: rows=list(csv.DictReader(f))
        story.append(p('Biological outcome','Heading2'))
        means={}
        for phase in ['baseline','training','postbaseline']:
            values=[float(r['power_uV2']) for r in rows if r['phase']==phase and r['valid']=='True' and r['power_uV2']]
            if values:
                means[phase]=float(np.mean(values)); story.append(p(f'{phase}: mean alpha power {means[phase]:.3f} uV² over {len(values)} valid updates.'))
        if means.get('baseline',0)>0 and 'postbaseline' in means: story.append(p(f"Post-minus-pre power change: {means['postbaseline']-means['baseline']:.3f} uV² ({100*(means['postbaseline']/means['baseline']-1):.1f}%)."))
        story.append(p('Overlapping feedback windows are descriptive and are not counted as independent trials. Pre/post changes are observational.'))
    if analysis.get('rejections'):
        story.append(p('Rejected trials','Heading2'));story.append(p('Trial numbers start at 0, as in the exported files.','SmallPrint'))
        for r in analysis['rejections']: story.append(p(f"{r.get('channel','')} Trial {r['index']} / {r['condition']}: {', '.join(r['reasons'])}",'SmallPrint'))
    story.append(p('Sources','Heading2'))
    for key in session.get('source',[]) if isinstance(session.get('source'),list) else session.get('references',[]):
        s=SOURCES[key]; story.append(p(s['title']+' - '+s['url'],'SmallPrint'))
    # Protocol references are retrieved separately because acquisition source is live/simulation.
    from protocols import PROTOCOLS
    proto=next(preset for preset in PROTOCOLS if preset['id']==session['protocol'])
    for key in proto['source']:
        s=SOURCES[key]; story.append(p(s['title']+' - '+s['url'],'SmallPrint'))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8); canvas.setFillColor(colors.grey); canvas.drawString(44,24,'Bandstand | Exploratory teaching / research session'); canvas.drawRightString(568,24,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    data=output.getvalue(); (directory/'report.pdf').write_bytes(data); return data
