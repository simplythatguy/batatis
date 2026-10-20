"""Decode/reconcile public SCC data-shape results; no technical acceptance inference."""
import json,pathlib,collections,re
OUT=pathlib.Path(__file__).resolve().parent

def decode(path,names):
 raw=json.loads(path.read_text());data=raw['results'][0]['result']['data'];dataset=data['dsr']['DS'][0]
 schema=[];previous=[];rows=[]
 for encoded in dataset['PH'][0]['DM0']:
  schema=encoded.get('S',schema);values=[];cells=iter(encoded.get('C',[]))
  for col_index,column_schema in enumerate(schema):
   if encoded.get('R',0)&(1<<col_index):value=previous[col_index]
   elif encoded.get('Ø',0)&(1<<col_index):value=None
   else:value=next(cells)
   values.append(value)
  previous=values.copy();decoded=[]
  for column_schema,value in zip(schema,values):
   decoded.append(dataset['ValueDicts'][column_schema['DN']][value] if isinstance(value,int) and 'DN' in column_schema else value)
  rows.append(dict(zip(names,decoded)))
 return rows,dataset,data

def main():
 rows,ds,data=decode(OUT/'source-catalog/scc-query-response.json',['discipline','code_edition_raw','article_raw','article_count'])
 grain,gds,gd=decode(OUT/'source-catalog/scc-grain-response.json',['variance_id','discipline','code_edition_raw','article_raw'])
 groups=collections.Counter((r['discipline'],r['code_edition_raw'],r['article_raw']) for r in grain)
 diffs=[{'group':r,'distinct_id_article_count':groups[(r['discipline'],r['code_edition_raw'],r['article_raw'])]} for r in rows if groups[(r['discipline'],r['code_edition_raw'],r['article_raw'])]!=r['article_count']]
 quality={'grouped_rows':len(rows),'article_count_sum':sum(r['article_count'] for r in rows),'distinct_id_article_combinations':len(grain),'distinct_variance_ids_excluding_null':len({r['variance_id'] for r in grain if r['variance_id'] is not None}),'building_unique_variance_ids_excluding_null':len({r['variance_id'] for r in grain if r['discipline']=='Building' and r['variance_id'] is not None}),'nulls_by_grain_field':{k:sum(r[k] is None for r in grain) for k in grain[0]},'groups_disagreeing_with_distinct_id_article_count':len(diffs),'differences':diffs,'powerbi_model_last_refresh':'2026-08-14T19:51:02.753','limitations':['The visible entity/report identifies 2026 Q1. Landing text says publication begins with Q1/Q2 2026, but Q2 coverage is not established by this model.','Article Count is the published measure; it does not necessarily count unique applications.','Some aggregate groups have multiple source rows per variance/article combination. Published totals and unique-ID counts must not be interchanged.','Supporting applications/technical alternative-solution evidence are not included in the SCC publication.']}
 for r in rows:
  m=re.match(r'\s*(\d{1,2}(?:\.\d+){3})',r['article_raw'] or '')
  r['normalized_article']=m[1]+'.' if m else None
 current=[r for r in rows if r['discipline']=='Building' and r['code_edition_raw'] in ['National Building Code - 2023 Alberta Edition','NBC(AE)-2023']]
 roots=collections.Counter()
 for r in current:
  if r['normalized_article']:roots[r['normalized_article']]+=r['article_count']
 result={'source_url':'https://www.safetycodes.ab.ca/data-hub/variance-data/','accessed':'2026-10-18','model_entity':'Variances2026q1','period':'2026 Q1 label in visible model/report; not inferred to include Q2','grain':'Published Article Count grouped by discipline, raw code label, and raw article string.','rows':rows,'current_ae2023_root_frequencies':[{'article':k,'published_article_occurrences':v} for k,v in roots.most_common()],'quality_checks':quality}
 (OUT/'scc-article-counts.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'scc-quality.json').write_text(json.dumps(quality,indent=2)+'\n')
 print('SCC grouped rows',len(rows),'published article occurrences',quality['article_count_sum'],'ID/article combinations',len(grain),'IDs',quality['distinct_variance_ids_excluding_null'],'nulls',quality['nulls_by_grain_field'],'group differences',len(diffs))
 print('Top AE2023 roots',result['current_ae2023_root_frequencies'][:8])
if __name__=='__main__':main()
