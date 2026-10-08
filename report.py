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
    story.extend([p('MUSE LAB / SESSION REPORT','Title'),p(session['title'],'Heading1'),p('SIMULATED DATA - NOT A HEADSET RECORDING' if session['source']=='simulation' else 'LIVE MUSE EEG'),p(session['id'],'SmallPrint'),Spacer(1,14)])
    summary=[['Acquisition',f"Muse 2 / 256 Hz / {session['source']}"],['Electrodes',', '.join(session['channels'])],['Reference','FPz hardware; reward task additionally re-referenced to TP9/TP10 mean' if session['protocol']=='reward' else 'FPz hardware reference'],['Measure',f"{session['metric']} / {session['window'][0]*1000:g}-{session['window'][1]*1000:g} ms" if session['mode']=='erp' else f"Band power {session['band']} Hz; {session['window']} seconds"],['State','Recording snapshot' if session['running'] else session.get('end_reason','ended')],['Random seed',str(session['seed'])]]
    table=Table([[p(c,'SmallPrint') for c in row] for row in summary],colWidths=[100,424]); table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#edf3f1')),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8)])); story.append(table)
    story.extend([p('Condition results','Heading2')])
    rows=[['Condition','Usable','Rejected','Mean','SE']]
    for g in analysis.get('groups',[]): rows.append([g['label'],str(g['accepted']),str(g['rejected']),f"{g['mean']:.4g} {analysis['unit']}" if g['mean'] is not None else 'Pending',f"{g['se']:.4g}" if g['se'] is not None else '-'])
    table=Table([[p(c,'SmallPrint') for c in row] for row in rows],colWidths=[164,65,65,115,115]); table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3f1')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8)])); story.append(table)
    stat=analysis.get('stats',{})
    story.append(p(f"Exploratory Welch t({stat['df']:.2f}) = {stat['t']:.4g}; p = {stat['p']:.12g}; {stat['label']}" if stat.get('ready') else stat.get('reason','No trials yet.')))
    story.append(p('Trial-level comparisons within one participant. Repeated testing is uncorrected; trials are not independent participants. Pointwise 95% intervals and SE describe accepted trials, not population uncertainty. Ten usable trials is a display threshold, not a power guarantee.','SmallPrint'))
    if session['mode']=='erp' and analysis.get('times'):
        drawing=Drawing(524,190); drawing.add(Line(40,30,510,30)); drawing.add(Line(40,30,40,175))
        waves=[g['erp']['mean'] for g in analysis['groups'] if g['erp']]; limit=max([10]+[abs(v) for w in waves for v in w]); times=analysis['times']; palette=['#127b6c','#c67a2e']
        for i,g in enumerate(analysis['groups']):
            if not g['erp']: continue
            pts=[]
            for t,v in zip(times,g['erp']['mean']): pts.extend([40+(t+.2)*470,100+v/limit*65])
            drawing.add(PolyLine(pts,strokeColor=colors.HexColor(palette[i]),strokeWidth=1.3)); drawing.add(String(55+i*210,180,g['label'][:35],fontSize=9,fillColor=colors.HexColor(palette[i])))
        drawing.add(String(180,8,'Time relative to stimulus: -200 to 800 ms',fontSize=9)); drawing.add(String(0,158,'uV',fontSize=9)); story.append(drawing)
    story.extend([p('Protocol and controls','Heading2'),p(session['notes']),p('Timing and processing','Heading2'),p(session['timing']),p(session['analysis'])])
    story.append(p('Signal quality is an EEG-derived estimate, not measured impedance. Artifact labels are probable; no dedicated EOG/EMG channels are available. Threshold defaults are tunable heuristics and are not clinically validated Muse cutoffs.','SmallPrint'))
    story.append(p('Thresholds: '+', '.join(f'{k}={v}' for k,v in session['thresholds'].items()),'SmallPrint'))
    story.append(p('Display calibration: '+str(session.get('calibration',{})),'SmallPrint'))
    if session.get('electrode_warning'): story.append(p('Electrode selection differs from the task default. Canonical effect electrodes may be absent on Muse.'))
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
        story.append(p('Rejected trials','Heading2'))
        for r in analysis['rejections']: story.append(p(f"Trial {r['index']+1} / {r['condition']}: {', '.join(r['reasons'])}",'SmallPrint'))
    story.append(p('Sources','Heading2'))
    for key in session.get('source',[]) if isinstance(session.get('source'),list) else session.get('references',[]):
        s=SOURCES[key]; story.append(p(s['title']+' - '+s['url'],'SmallPrint'))
    # Protocol references are retrieved separately because acquisition source is live/simulation.
    from protocols import PROTOCOLS
    proto=next(preset for preset in PROTOCOLS if preset['id']==session['protocol'])
    for key in proto['source']:
        s=SOURCES[key]; story.append(p(s['title']+' - '+s['url'],'SmallPrint'))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8); canvas.setFillColor(colors.grey); canvas.drawString(44,24,'Muse Lab | Exploratory teaching / research session'); canvas.drawRightString(568,24,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    data=output.getvalue(); (directory/'report.pdf').write_bytes(data); return data
