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

with open("extras/Missions.tsv", encoding='utf-8', newline='') as csvfile:
	mission_templates = pd.read_csv(csvfile, delimiter='\t', index_col=0)
	
with open(config['outputs']['items'], encoding='utf-8', newline='') as csvfile:
	itemdata = pd.read_csv(csvfile, delimiter='\t', index_col='ID')
	

def getItem(ID: int):
	try:
		return itemdata.loc[ID, "name"]
	except KeyError:
		return 'Unknown'
	
def readCondition(text: str)->dict:
	toret = {}
	for row in text.split("\n")[1:]:
		if(row == ""): continue
		cells = row.split(",")
		ID = int(cells[0])
		page = int(cells[1])
		category = int(cells[2])
		
		if category == 22:
			quantity = int(cells[5])
			condition = [int(x) for x in cells[6:]]
		else:
			quantity = int(cells[3])
			condition = [int(x) for x in cells[4:]]
		
		toret[int(ID)] = {"page": page, "category": category, "quantity": quantity, "condition": condition}
	
	return toret


def updateItems():
	decoded = {}
	
	text_jp = pd.read_csv(flnames_jp['text'], sep=',', header=None, usecols=[0, 1],
												index_col=0, encoding="utf-8").dropna().to_dict("index")
	prize_jp = pd.read_csv(flnames_jp['prize'], sep=',', header=0, usecols=[0, 5, 6],
												 index_col=0, encoding="utf-8").dropna().to_dict("index")
	
	with open(flnames_jp['fill'], 'r') as fl1:
		txt = fl1.read()
		fill_jp = readCondition(txt)
		
	text_en = pd.read_csv(flnames_en['text'], sep='|', header=None, usecols=[0, 1],
												index_col=0, encoding="utf-8").dropna().to_dict("index")
	prize_en = pd.read_csv(flnames_en['prize'], sep=',', header=0, usecols=[0, 5, 6],
												 index_col=0, encoding="utf-8").dropna().to_dict("index")
	
	with open(flnames_en['fill'], 'r') as fl1:
		txt = fl1.read()
		fill_en = readCondition(txt)
	
	for t in prize_en.keys() & text_en.keys() & fill_en.keys():
		lines = text_en[t][1].split("<br>")
		if len(lines) > 1 and "%d" in lines[1]:
			lines.pop(1)
		lines[0] = lines[0].replace("%d", str(fill_en[t]["quantity"]))
		print(f"{t}: {parseMission(fill_en[t])} -> {getItem(prize_en[t]['item'])} X {prize_en[t]['item_count']}")
		decoded[t] = f"{'|'.join(lines)} -> {getItem(prize_en[t]['item'])} X {prize_en[t]['item_count']}"
	
	for t in (prize_jp.keys() & text_jp.keys() & fill_jp.keys())-(prize_en.keys() & text_en.keys() & fill_en.keys()):
		lines = text_jp[t][1].split("<br>")
		if len(lines) > 1 and "%d" in lines[1]:
			lines.pop(1)
		lines[0] = lines[0].replace("%d", str(fill_jp[t]["quantity"]))
		print(f"{t}: {'|'.join(lines)} -> {getItem(prize_jp[t]['item'])} X {prize_jp[t]['item_count']}")
		decoded[t] = f"{'|'.join(lines)} -> {getItem(prize_jp[t]['item'])} X {prize_jp[t]['item_count']}"
	
	with open(fl_out, encoding='utf-8', mode='w', newline='') as fl1:
		writer = csv.DictWriter(fl1, fieldnames=["ID", "mission_text"], delimiter='\t', quoting=csv.QUOTE_NONE,
		                        quotechar='', escapechar='\\')
		writer.writeheader()
		for row in decoded:
			writer.writerow({"ID": row, "mission_text": decoded[row]})

def parseMission(data: dict):
	cat = data["category"]
	template = mission_templates["template"][cat]
	match cat:
		case 0 | 1:
			return template.format(data["quantity"], ",".join([str(x) for x in data["condition"]]))
		case 2:
			return template.format(str(data["condition"]))
		case 3:
			return template.format(data["condition"][0])
		case 5:
			return template
		case 6:
			return template.format(",".join([str(x) for x in data["condition"]]))
		case 7:
			return template.format(data["quantity"])
		case 8:
			return template.format(str(data["condition"]), data["quantity"]+1)
		case 9:
			return template.format(str(data["condition"]))
		case 10:
			return template
		case 11:
			return template.format(",".join([str(x) for x in data["condition"]]))
		case 15:
			return template.format(str(data["condition"]))
		case 16:
			return template
		case 17:
			return template.format(data["quantity"])
		case 18:
			return template.format(data["quantity"], ",".join([str(x) for x in data["condition"]]))
		case 19:
			return template
		case 20:
			return template.format(data["quantity"], ",".join([str(x) for x in data["condition"]]))
		case 21:
			return template.format(data["quantity"], ",".join([str(x) for x in data["condition"]]))
		case 22:
			return None
		case 23:
			return template.format(data["quantity"])
		case 24:
			return None
	
	return None
	
updateItems()
