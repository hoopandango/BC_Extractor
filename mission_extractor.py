import json
import pandas as pd
import csv

# region setup
with open('_config.json') as fl:
	config = json.load(fl)

LNG = config['setup']['LNG']

flnames_jp = config['inputs']['jp']['missions']
flnames_en = config['inputs']['en']['missions']
fl_out = config['outputs']['missions']
# endregion

with open(config['outputs']['items'], encoding='utf-8', newline='') as csvfile:
	itemdata = pd.read_csv(csvfile, delimiter='\t', index_col='ID')

def getItem(ID: int):
	try:
		return itemdata.loc[ID, "name"]
	except KeyError:
		return 'Unknown'
	
def updateItems():
	text_jp = pd.read_csv(flnames_jp['text'], sep=',', header=None, usecols=[0, 1],
												index_col=0, encoding="utf-8").dropna().to_dict("index")
	prize_jp = pd.read_csv(flnames_jp['prize'], sep=',', header=0, usecols=[0, 5, 6],
	                      index_col=0, encoding="utf-8").dropna().to_dict("index")
	fill_jp = pd.read_csv(flnames_jp['fill'], sep=',', header=0, usecols=[0, 3],
	                      index_col=0, encoding="utf-8").dropna().to_dict("index")
	text_en = pd.read_csv(flnames_en['text'], sep='|', header=None, usecols=[0, 1],
	                      index_col=0, encoding="utf-8").dropna().to_dict("index")
	prize_en = pd.read_csv(flnames_en['prize'], sep=',', header=0, usecols=[0, 5, 6],
	                      index_col=0, encoding="utf-8").dropna().to_dict("index")
	fill_en = pd.read_csv(flnames_en['fill'], sep=',', header=0, usecols=[0, 3],
	                      index_col=0, encoding="utf-8").dropna().to_dict("index")
	
	decoded = {}
	for t in prize_en.keys() & text_en.keys() & fill_en.keys():
		lines = text_en[t][1].split("<br>")
		if len(lines) > 1 and "%d" in lines[1]:
			lines.pop(1)
		lines[0] = lines[0].replace("%d", str(fill_en[t]["progress_count"]))
		print(f"{t}: {'|'.join(lines)} -> {getItem(prize_en[t]['item'])} X {prize_en[t]['item_count']}")
		decoded[t] = f"{'|'.join(lines)} -> {getItem(prize_en[t]['item'])} X {prize_en[t]['item_count']}"
	
	for t in (prize_jp.keys() & text_jp.keys() & fill_jp.keys())-(prize_en.keys() & text_en.keys() & fill_en.keys()):
		lines = text_jp[t][1].split("<br>")
		if len(lines) > 1 and "%d" in lines[1]:
			lines.pop(1)
		lines[0] = lines[0].replace("%d", str(fill_jp[t]["progress_count"]))
		print(f"{t}: {'|'.join(lines)} -> {getItem(prize_jp[t]['item'])} X {prize_jp[t]['item_count']}")
		decoded[t] = f"{'|'.join(lines)} -> {getItem(prize_jp[t]['item'])} X {prize_jp[t]['item_count']}"
	
	with open(fl_out, encoding='utf-8', mode='w', newline='') as fl1:
		writer = csv.DictWriter(fl1, fieldnames=["ID", "mission_text"], delimiter='\t', quoting=csv.QUOTE_NONE,
		                        quotechar='', escapechar='\\')
		writer.writeheader()
		for row in decoded:
			writer.writerow({"ID": row, "mission_text": decoded[row]})
	
updateItems()
