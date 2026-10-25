"""Independent basic timetable checks, not a full implementation of FET constraints."""
from pathlib import Path
import json, hashlib, re, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]
EVIDENCE=Path(__file__).parent

def occupy(table,key,activity):
    if key in table and table[key]!=activity:
        raise AssertionError((key,table[key],activity))
    table[key]=activity

# This check must reject a collision, not merely reproduce the generator's output.
t={};occupy(t,('teacher',1,2),1)
try:
    occupy(t,('teacher',1,2),2)
except AssertionError:
    pass
else:
    raise AssertionError('collision detection self-check failed')

rows=json.loads((EVIDENCE/'benchmark-results.json').read_text())
for row in rows:
    data=ET.parse(ROOT/row['input']).getroot()
    activities={a.findtext('Id'):a for a in data.findall('./Activities_List/Activity') if a.findtext('Active','true')=='true'}
    days=[n.text for n in data.findall('./Days_List/Day/Name')]
    hours=[n.text for n in data.findall('./Hours_List/Hour/Name')]
    sets={}
    def leaves(node):
        children=node.findall('Group')+node.findall('Subgroup')
        result=set().union(*(leaves(c) for c in children)) if children else {node.findtext('Name')}
        sets.setdefault(node.findtext('Name'),set()).update(result)
        return result
    for year in data.findall('./Students_List/Year'):leaves(year)
    virtual={n.findtext('Name') for n in data.findall('./Rooms_List/Room') if n.findtext('Virtual')=='true'}
    banned={};breaks=set()
    for c in data.findall('./Time_Constraints_List/*'):
        if c.findtext('Active','true')!='true' or c.findtext('Weight_Percentage')!='100':continue
        if c.tag=='ConstraintBreakTimes':
            breaks.update((n.findtext('Day'),n.findtext('Hour')) for n in c.findall('Break_Time'))
        elif c.tag=='ConstraintTeacherNotAvailableTimes':
            banned.setdefault(('teacher',c.findtext('Teacher')),set()).update((n.findtext('Day'),n.findtext('Hour')) for n in c.findall('Not_Available_Time'))
        elif c.tag=='ConstraintStudentsSetNotAvailableTimes':
            for subgroup in sets[c.findtext('Students')]:
                banned.setdefault(('student',subgroup),set()).update((n.findtext('Day'),n.findtext('Hour')) for n in c.findall('Not_Available_Time'))
    checked=[]
    for p in sorted((ROOT/row['output']).rglob('*_activities.xml')):
        table={};assigned=[]
        for a in ET.parse(p).getroot().findall('Activity'):
            id=a.findtext('Id');day=a.findtext('Day');hour=a.findtext('Hour')
            if day not in days or hour not in hours:continue
            original=activities[id];start=hours.index(hour);duration=int(original.findtext('Duration'))
            assert start+duration<=len(hours),(id,'day overflow')
            teacher_names={n.text for n in original.findall('Teacher')}
            subgroup_names=set().union(*(sets[n.text] for n in original.findall('Students')))
            room=a.findtext('Room')
            resources=[('teacher',n) for n in teacher_names]+[('student',n) for n in subgroup_names]
            if room and room not in {'unallocated','unspecified'}:
                assert room not in virtual,'virtual-room validation unsupported by this checker'
                resources.append(('room',room))
            for k in range(start,start+duration):
                assert (day,hours[k]) not in breaks,(id,'break')
                for kind,n in resources:
                    assert (day,hours[k]) not in banned.get((kind,n),set()),(id,'availability',kind,n)
                    occupy(table,(kind,n,day,hours[k]),id)
            assigned.append((id,day,hour,room))
        assert len({a[0] for a in assigned})==len(assigned)
        conflicts=list(p.parent.glob('*_soft_conflicts.txt'))
        soft=None;broken=None
        if conflicts:
            text=conflicts[0].read_text(encoding='utf-8-sig')
            m=re.search(r'Total (?:soft )?conflicts: ([0-9.]+)',text);soft=float(m[1]) if m else None
            m=re.search(r'Number of broken (?:soft )?constraints: (\d+)',text);broken=int(m[1]) if m else None
        checked.append({'path':str(p.relative_to(ROOT)),'time_assigned':len(assigned),'total':len(activities),'fitness_total_reported_by_fet':soft,'broken_constraints_reported_by_fet':broken,'basic_checks':'PASS','assignment_sha256':hashlib.sha256(json.dumps(sorted(assigned),ensure_ascii=False).encode()).hexdigest()})
    row['validated_outputs']=checked
    row['placed_reported_by_fet']=re.findall(r'(Successfully finished timetable|Highest stage timetable|Current stage timetable): (\d+) scheduled activities exported', (ROOT/row['output']/'stdout.txt').read_text())
    row['fixed_starting_times']=sum(c.tag=='ConstraintActivityPreferredStartingTime' and c.findtext('Weight_Percentage')=='100' and c.findtext('Active','true')=='true' for c in data.findall('./Time_Constraints_List/*'))
    result=(ROOT/row['output']/'logs/result.txt').read_text(encoding='utf-8-sig')
    row['status']='COMPLETE' if 'Generation successful' in result else 'TIME_LIMIT' if 'Time exceeded' in result else 'FET_IMPOSSIBLE' if 'Impossible' in result else 'OTHER'
    if row['status']=='COMPLETE':assert len(checked)==1 and checked[0]['time_assigned']==len(activities)
(EVIDENCE/'benchmark-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
for row in rows:print(row['label'],row['repeat'],row['status'],[(x['time_assigned'],x['fitness_total_reported_by_fet'],x['basic_checks']) for x in row['validated_outputs']])
