import json
import pandas as pd
import csv
from src_backend.local_readers import Readers

def extract():
	# region setup
	
	with open('_config.json') as fl:
		config = json.load(fl)
	
	# LNG = config['setup']['LNG']
	
	flnames_jp = config['inputs']['jp']['missions']
	flnames_en = config['inputs']['en']['missions']
	fl_out = config['outputs']['missions']
	# endregion
	
	with open("extras/Missions.tsv", encoding='utf-8', newline='') as csvfile:
		mission_templates = pd.read_csv(csvfile, delimiter='\t', index_col=0)
	
	# TODO: generate combodata table myself
	
	def getCat(ID: int) -> str:
		if (ID == -1): return "any cat"
		return Readers.getCat(ID, 0)
	
	def getStageCat(catID: int) -> str:
		cats = ["SoL", "XP Reward", "Catfruit", "Cat Ticket", "Unknown", "Unknown", "Dojo"]
		try:
			return cats[catID]
		except IndexError:
			return "Unknown"
		
	def getCombo(ID: int) -> str:
		if (ID == -1): return "any"
		return Readers.getCombo(ID)
	
	def getStageOrMap(ID: int) -> str:
		temp = Readers.getStageOrMap(ID)
		if temp == "Unknown":
			return str(ID)
		else:
			return temp
	
	def getItem(cat: int, ID: int) -> str:
		if cat == 0:
			return Readers.getItem(ID)
		elif cat == 1:
			return Readers.getCat(ID, 0)
		else:
			return Readers.getCat(ID, 2)
	
	def unique(sample: list):
		seen = {}
		torep = ["'", '"', "‘", "’", " "]
		toret = []
		for s in sample:
			i = s
			for x in torep:
				i = i.replace(x, "")
			if i not in seen:
				toret.append(s)
				seen.setdefault(i, i)
		
		return toret
	
	def readCondition(text: str) -> dict:
		toret = {}
		for row in text.split("\n")[1:]:
			if (row == ""): continue
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
	
	def times_check(func):
		def wrap(data: dict) -> str | None:
			temp = func(data)
			if temp is None:
				return temp
			else:
				return func(data).replace("1 times", "1 time")
		return wrap
	
	@times_check
	def parseMission(data: dict) -> str | None:
		# generates text for mission, returns None if not possible / supported
		cat = data["category"]
		template = mission_templates["template"][cat]
		match cat:
			case 0:  # one stage N times
				stages = unique([Readers.getStageOrMap(x) for x in data["condition"]])
				if (len(stages) == 1):
					cat += 1000
					template = mission_templates["template"][cat]
				if (data["condition"][0] < 100000):
					cat += 10000
					template = mission_templates["template"][cat]
				return template.format(data["quantity"], ", ".join(stages))
			
			case 1:  # M stages N times
				stages = unique([getStageOrMap(x) for x in data["condition"]])
				if (len(stages) == 1 and len(data["condition"]) < 4):  # I hate this so much please help
					cat += 1000
					template = mission_templates["template"][cat]
				if (data["quantity"] > len(stages)):
					cat += 2000
					template = mission_templates["template"][cat]
				if (data["condition"][0] < 100000):
					cat += 10000
					template = mission_templates["template"][cat]
				return template.format(data["quantity"], ", ".join(stages))
			
			case 2:  # get N cats
				return template.format(",".join([getCat(t1) for t1 in data["condition"]]))
			case 3:  # clear all level N SoL
				return template.format(data["condition"][0])
			case 5 | 10 | 16 | 19 | 26:
				return template
			case 6:  # clear all of the following missions
				if len(data["condition"]) == data["quantity"]:
					template = template.replace("any", "all")
				return template.format(data["quantity"], ", ".join([str(x) for x in data["condition"]]))
			case 7:  # complete N Gamatoto expeditions
				return template.format(data["quantity"])
			case 8:  # level up M cat to level N
				return template.format(getCat(data["condition"][0]), data["quantity"] + 1)
			case 9:  # finish a stage in the category N
				if (data["quantity"] > 1):
					return mission_templates["template"][cat + 1000].format(data["quantity"], getStageCat(data["condition"][0]))
				return template.format(getStageCat(data["condition"][0]))
			case 11:  # activate treasures in all N stages
				return template.format(", ".join([str(x) for x in data["condition"]]))
			case 15:  # clear a stage with the N combo
				return template.format(getCombo(data["condition"][0]))
			case 17:  # get a user rank of N
				return template.format(data["quantity"])
			case 18:  # score M or higher on N timed stage [deprecated]
				return None
			# return template.format(data["quantity"], ", ".join([getStage(x) for x in data["condition"]]))
			case 20:  # clear an N stage [weeklies only]
				return template.format(data["quantity"], ", ".join([getStageCat(x) for x in data["condition"]]))
			case 21:  # score M or higher on N dojo
				return template.format(data["quantity"], ", ".join([getStageOrMap(x) for x in data["condition"]]))
			case 22:  # defeat M enemy in N category
				stages = unique([getStageOrMap(x) for x in data["condition"][1:]])
				if data["condition"][1] < 5:
					return mission_templates["template"][1000 + cat].format(data["quantity"] + 1,
					                                                        Readers.getEnemy(data["condition"][0]))
				elif (4000 > data["condition"][1] >= 3000):
					return mission_templates["template"][2000 + cat].format(Readers.getEnemy(data["condition"][0]), stages[0])
				elif len(stages) == 1:
					return mission_templates["template"][3000 + cat].format(Readers.getEnemy(data["condition"][0]), stages[0])
				return template.format(Readers.getEnemy(data["condition"][0]), ", ".join(stages))
			case 23:  # clear all N monthly missions
				return template.format(data["quantity"])
			case 24:  # clear M stage with N restriction
				return None
			case 25:  # get all treasures in chapter N
				return template.format(getStageOrMap(data["condition"][0]))
			case 26:  # quiz mission
				return template
			case 27:  # beat all quiz missions
				return template.format(data["condition"][0])
			case 28:
				return template.format(data["quantity"])

		return None
		
	print("Started extracting missions")
	decoded = {}  # dict with all read missions
	
	text_jp = pd.read_csv(flnames_jp['text'], sep=',', header=None, usecols=[0, 1],
												index_col=0, encoding="utf-8").dropna().to_dict("index")
	prize_jp = pd.read_csv(flnames_jp['prize'], sep=',', header=0, usecols=[0, 4, 5, 6],
												 index_col=0, encoding="utf-8").dropna().to_dict("index")
	
	with open(flnames_jp['fill'], 'r') as fl1:
		txt = fl1.read()
		fill_jp = readCondition(txt)
	
	text_en = pd.read_csv(flnames_en['text'], sep='|', header=None, usecols=[0, 1],
												index_col=0, encoding="utf-8").dropna().to_dict("index")
	
	for t in text_en.keys():
		if (text_en[t][1] in ["<br>", "|"]):
			continue
		# fancy shit that somehow works, only tested for en text
		
		name = parseMission(fill_jp[t])
		
		if (name is None):  # do some shitty hard-coded processing
			lines = text_en[t][1].split("<br>")
			if fill_jp[t]["category"] == 24:  # process restricted challenge missions separately
				lines = ["Clear"+text_en[t][1].partition("Clear")[2].replace("<br>", " ").split("(")[0]]
			elif len(lines) > 1 and "%d" in lines[1]:
				lines.pop(1)
			lines[0] = lines[0].replace("%d", str(fill_jp[t]["quantity"]))
			name = '|'.join(lines)
		
		prize = getItem(prize_jp[t]['item_category'], prize_jp[t]['item'])
		count = prize_jp[t]['item_count']
		count = " X %d" % count if count > 0 else ""
		
		decoded[t] = f"{name} -> {prize}{count}"
	
	# does the same thing for jp-unique entries only
	for t in (prize_jp.keys() & text_jp.keys() & fill_jp.keys()) - text_en.keys():
		name = parseMission(fill_jp[t])
		
		if (name is None):  # process with some hard-coded rules
			lines = text_jp[t][1].split("<br>")
			if len(lines) > 1 and "%d" in lines[1]:
				lines.pop(1)
			lines[0] = lines[0].replace("%d", str(fill_jp[t]["quantity"]))
			name = '|'.join(lines)
		
		prize = getItem(prize_jp[t]['item_category'], prize_jp[t]['item'])
		count = prize_jp[t]['item_count']
		count = " X %d" % count if count > 0 else ""
		
		decoded[t] = f"{name} -> {prize}{count}"
	
	with open(fl_out, encoding='utf-8', mode='w', newline='') as fl1:
		writer = csv.DictWriter(fl1, fieldnames=["ID", "mission_text"], delimiter='\t', quoting=csv.QUOTE_NONE,
														quotechar='', escapechar='\\')
		writer.writeheader()
		for row in decoded:
			writer.writerow({"ID": row, "mission_text": decoded[row]})
	print("Finished extracting missions")
