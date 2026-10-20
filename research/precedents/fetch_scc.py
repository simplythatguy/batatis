"""Read-only requests to the publicly embedded SCC Power BI report."""
import json,pathlib,subprocess,uuid
OUT=pathlib.Path(__file__).resolve().parent/'source-catalog'
base='https://wabi-canada-central-b-primary-api.analysis.windows.net'
key='3ab0630c-39fe-4212-b3b1-d7820e79d004'
entity='Variances2026q1'
def column(prop):return {'Column':{'Expression':{'SourceRef':{'Source':'v'}},'Property':prop},'Name':entity+'.'+prop}
fields=['Discipline','Code and Standard 2','Article2']
select=[column(f) for f in fields]+[{'Measure':{'Expression':{'SourceRef':{'Source':'v'}},'Property':'Article Count'},'Name':entity+'.Article Count'}]
q={'Version':2,'From':[{'Name':'v','Entity':entity,'Type':0}],'Select':select}
cmd={'SemanticQueryDataShapeCommand':{'Query':q,'Binding':{'DataReduction':{'DataVolume':4,'Primary':{'Window':{'Count':10000}}},'Primary':{'Groupings':[{'Projections':list(range(len(select)))}]},'Version':1},'ExecutionMetricsKind':1}}
body={'version':'1.0.0','queries':[{'Query':{'Commands':[cmd]},'QueryId':'precedent-research-articles'}],'cancelQueries':[],'modelId':4112675}
f=OUT/'scc-query-request.json';f.write_text(json.dumps(body,indent=2)+'\n')
u=base+'/public/reports/querydata?synchronous=true'
r=subprocess.run(['curl','-sSL','--max-time','35','-H','Content-Type: application/json','-H','Accept: application/json','-H','X-PowerBI-ResourceKey: '+key,'-H','ActivityId: '+str(uuid.uuid4()),'--data-binary','@'+str(f),'-o',str(OUT/'scc-query-response.json'),'-w','%{http_code} %{size_download}',u],capture_output=True,text=True)
(OUT/'scc-query-receipt.json').write_text(json.dumps({'url':u,'accessed':'2026-10-18','http_result':r.stdout,'stderr':r.stderr,'public_resource_key':key,'model_id':4112675,'entity':entity,'fields':fields+['Article Count']},indent=2)+'\n');print(r.stdout,r.stderr)
print((OUT/'scc-query-response.json').read_text()[:5000])
