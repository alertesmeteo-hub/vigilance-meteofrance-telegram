import html,json,os,sys
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import requests
API='https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours'
COL={2:('🟡','jaune'),3:('🟠','orange'),4:('🔴','rouge')}
P={'1':'vent violent','2':'pluie-inondation','3':'orages','4':'inondation','5':'neige-verglas','6':'canicule','7':'grand froid','8':'avalanches','9':'vagues-submersion'}
N='Ain,Aisne,Allier,Alpes de Haute Provence,Hautes Alpes,Alpes Maritimes,Ardèche,Ardennes,Ariège,Aube,Aude,Aveyron,Bouches du Rhône,Calvados,Cantal,Charente,Charente Maritime,Cher,Corrèze'.split(',')
N+=['']
N+='Côte d’Or,Côtes d’Armor,Creuse,Dordogne,Doubs,Drôme,Eure,Eure et Loir,Finistère,Gard,Haute Garonne,Gers,Gironde,Hérault,Ille et Vilaine,Indre,Indre et Loire,Isère,Jura,Landes,Loir et Cher,Loire,Haute Loire,Loire Atlantique,Loiret,Lot,Lot et Garonne,Lozère,Maine et Loire,Manche,Marne,Haute Marne,Mayenne,Meurthe et Moselle,Meuse,Morbihan,Moselle,Nièvre,Nord,Oise,Orne,Pas de Calais,Puy de Dôme,Pyrénées Atlantiques,Hautes Pyrénées,Pyrénées Orientales,Bas Rhin,Haut Rhin,Rhône,Haute Saône,Saône et Loire,Sarthe,Savoie,Haute Savoie,Paris,Seine Maritime,Seine et Marne,Yvelines,Deux Sèvres,Somme,Tarn,Tarn et Garonne,Var,Vaucluse,Vendée,Vienne,Haute Vienne,Vosges,Yonne,Territoire de Belfort,Essonne,Hauts de Seine,Seine Saint Denis,Val de Marne,Val d’Oise'.split(',')
D={str(i+1).zfill(2):n for i,n in enumerate(N) if n};D.update({'2A':'Corse du Sud','2B':'Haute Corse'})
def need(k):
 v=os.getenv(k,'').strip()
 if not v: raise RuntimeError('Secret manquant : '+k)
 return v
def main():
 r=requests.get(API,headers={'apikey':need('MF_API_KEY')},timeout=60);r.raise_for_status();data=r.json();product=data['product'];now=datetime.now(ZoneInfo('Europe/Paris'))
 update=datetime.fromisoformat(product['update_time'].replace('Z','+00:00'))
 if not timedelta(0)<=now-update<=timedelta(hours=12): raise RuntimeError('Carte trop ancienne.')
 current=next((x for x in product.get('periods',[]) if datetime.fromisoformat(x['begin_validity_time'].replace('Z','+00:00'))<=now<datetime.fromisoformat(x['end_validity_time'].replace('Z','+00:00'))),None)
 if not current: raise RuntimeError('Aucune période valide.')
 groups={}
 for item in current.get('timelaps',{}).get('domain_ids',[]):
  dep=D.get(str(item.get('domain_id','')).zfill(2))
  if dep:
   for p in item.get('phenomenon_items',[]):
    c=int(p.get('phenomenon_max_color_id',1))
    if c in COL: groups.setdefault((c,P.get(str(p.get('phenomenon_id')),'phénomène météo')),[]).append(dep)
 lines=['<b>• Vigilances en cours :</b>']
 if groups:
  for (c,name),deps in sorted(groups.items(),key=lambda x:(-x[0][0],x[0][1])): lines.append(f'{COL[c][0]} <b>{html.escape(name)} :</b> {html.escape(", ".join(sorted(deps)))}.')
 else: lines.append('🟢 <b>Vigilance verte :</b> aucun département en vigilance jaune, orange ou rouge.')
 text='\n'.join(lines)+'\n\nSource : https://vigilance.meteofrance.fr/fr'
 os.makedirs('output',exist_ok=True);open('output/message.html','w',encoding='utf8').write(text);json.dump(data,open('output/carte.json','w',encoding='utf8'),ensure_ascii=False)
 if os.getenv('DRY_RUN','true').lower()=='true': print(text);return
 q=requests.post('https://api.telegram.org/bot'+need('TELEGRAM_BOT_TOKEN')+'/sendMessage',data={'chat_id':os.getenv('TELEGRAM_CHAT_ID','@Alerte_meteo'),'text':text,'parse_mode':'HTML'},timeout=60);q.raise_for_status()
if __name__=='__main__':
 try: main()
 except Exception as e: print(str(e),file=sys.stderr);sys.exit(1)
