import csv
import datetime
import json
import sqlite3
from itertools import groupby

import pandas as pd

from containers import Gatya, Event, Stage, EventGroup, Mission, Sale, RawEventGroup, Item
from event_data_parsers import GatyaParsers, ItemParsers, StageParsers
from local_readers import Readers

groupable_events: list[str] = ['Seeing Red', 'Tag Arena', 'Dark', 'Duel', '(Baron)', 'Citadel']
weekdays: list[str] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

with open('_config.json') as fl:
	config = json.load(fl)
inm_loc: str = config["outputs"]["eventdata"]

with open('../extras/EventGroups.json', encoding='utf-8') as f:
	f = f.read()
	y = json.loads(f)
	event_groups: dict[str, dict[str, str | bool]] = y

class UniversalFetcher:
	ver: str
	filters: list[str]
	
	def __init__(self, fls: list):
		self.filters = fls
	
	@staticmethod
	def groupData(waitingqueue: list[RawEventGroup] | list[Event]) -> tuple[list[Event], list[EventGroup],
	                                                                        list[Sale], list[Mission]]:
		# stage, festival, sale, mission
		group_history_2: dict[str, EventGroup] = {}
		ungrouped_history: dict[str, Event] = {}
		finalEvents: list[Event | EventGroup] = []
		finalEventGroups: list[EventGroup] = []
		sales: list[Sale | EventGroup] = []
		missions: list[Mission] = []
		
		flatqueue: list[Event] = []
		
		def presentInGroup(grp: dict[str, str | bool], curr: Event) -> bool:
			match (grp["compare_mode"]):
				case 1:
					for stage in grp["stages"]:
						if stage in curr.name:
							return True
					return False
				
				case 2:
					if not (curr.dates[0].day == grp["date"]):
						return False
					for stage in grp["stages"]:
						if stage == curr.name:
							return True
					return False
				
				case _:
					for stage in grp["stages"]:
						if stage == curr.name:
							return True
					return False
		
		def pushEventOrSale(e: Event | EventGroup):
			if (isinstance(e, EventGroup)):
				finalEventGroups.append(e)
				
				if 900 > e.events[0].ID > 799 or e.events[0].ID < 0:
					sales.append(e)
				else:
					finalEvents.append(e)
				return
			
			try:
				if not isinstance(e, Gatya) and not isinstance(e, Item) and (900 > e.ID > 799 or e.ID < 100):
					sales.append(Sale.fromEvent(e))
					return
				if 10000 > e.ID >= 9000:
					missions.append(Mission.fromEvent(e))
					return
			except KeyError:
				pass
			finalEvents.append(e)
		
		def flushGroup(grp: str):
			grp_obj = group_history_2[grp]
			if not grp_obj.visible:
				return
			pushEventOrSale(grp_obj)
			# finalEventGroups.append(grp_obj)
			group_history_2.pop(grp)
		
		def needsReset(groupname: str, event: Event) -> bool:
			group = group_history_2[groupname]
			if event.name not in group.events:
				return False
			if (event.dates[0] - group.dates[1]).days > 3:
				return True
			return False
		
		def addGroup(group_name: str, event: Event):
			group_history_2[group_name] = EventGroup(**{'name': group_name, 'events': [event],
			                                            'visible': event_groups[group_name]["visible"],
			                                            'dates': event.dates.copy(),
			                                            'split': event_groups[group_name]["split"]})
		
		def extendGroup(groupname: str, event: Event):
			group = group_history_2[groupname]
			group.events.append(event)
			group.dates[1] = max(group.dates[1], event.dates[1])
			group.dates[0] = min(group.dates[0], event.dates[0])
		
		def processForGrouping(curr: Event):
			grouped = False
			for groupname, group in event_groups.items():
				if presentInGroup(group, curr):
					grouped = True
					if groupname in group_history_2:
						if needsReset(groupname, curr):
							flushGroup(groupname)
							addGroup(groupname, curr)
						else:
							extendGroup(groupname, curr)
					else:
						addGroup(groupname, curr)
			
			toadd: Event
			
			if (toadd := ungrouped_history.get(curr.name)) is not None:
				grouped = True
				if toadd.ID == curr.ID and not isinstance(curr, Gatya):  # do not "hot-merge" gatya events
					toadd.dates.extend(curr.dates)
				else:
					ungrouped_history.pop(curr.name)
					group_history_2[curr.name] = EventGroup(events=[toadd, curr], dates=toadd.dates, name=curr.name,
					                                        split=True, visible=True)
			if not grouped:
				ungrouped_history[curr.name] = curr
		
		def groupEvents():
			for event in flatqueue:
				processForGrouping(event)
			for groupname in group_history_2.copy():
				flushGroup(groupname)
			for e in ungrouped_history.values():
				pushEventOrSale(e)
		
		def flatten(toflatten: list[RawEventGroup]) -> list[Event]:
			# flatten RawEventGroup if that's how the data was given
			newqueue = []
			grp0: RawEventGroup
			while len(toflatten) > 0:
				grp0 = toflatten.pop(0)
				for ID in grp0.IDs:
					eventname = StageParsers.getEventName(ID)
					if eventname == 'Unknown':
						continue
					
					curr0: Event = Stage(name=eventname, ID=ID, dates=grp0.dates, versions=grp0.versions, sched=grp0.sched,
					                     sched_data=grp0.sched_data)
					newqueue.append(curr0)
			return newqueue
	
		flatqueue = waitingqueue
		if len(waitingqueue) > 0:
			if (isinstance(waitingqueue[0], RawEventGroup)):
				flatqueue = flatten(waitingqueue)
		groupEvents()
		return (finalEvents, finalEventGroups, sales, missions)

class GatyaFetcher(UniversalFetcher):
	# SETUP
	def __init__(self, fls=['M'], d0=datetime.datetime.today()):
		UniversalFetcher.__init__(self, fls)
		self.rawGatya: list[list[str]] = []
		self.refinedGatya: list[Gatya] = []
		self.rejectedGatya: list[Gatya] = []
		self.date0 = d0
	
	# ACQUISITION TOOLS
	def fetchRawData(self, data: str):
		lines = data.split('\n')
		cr = csv.reader(lines, delimiter="\t")
		for row in cr:
			if len(row) > 1:
				self.rawGatya.append(row)
				row[1], row[3] = (row[1] + '000')[0:3], (row[3] + '000')[0:3]
	
	# PROCESSING TOOLS
	def readRawData(self):
		for banner in self.rawGatya:
			dates: list[datetime.datetime] = GatyaParsers.getdates(banner)
			if GatyaParsers.areValidDates(dates, self.filters, self.date0):
				goto = self.refinedGatya
			else:
				goto = self.rejectedGatya
			
			ID: int = -1
			try:
				ID = int(GatyaParsers.getValueAtOffset(banner, 10))
			except ValueError:
				pass
			toput = Gatya()
			toput.dates = dates
			toput.versions = GatyaParsers.getversions(banner)
			toput.page = GatyaParsers.getCategory(banner)
			toput.slot = banner[9]
			toput.ID = ID
			toput.rates = GatyaParsers.getGatyaRates(banner)
			toput.guarantee = GatyaParsers.getGuarantees(banner)
			toput.text = GatyaParsers.getValueAtOffset(banner, 24)
			toput.extras = GatyaParsers.getExtras(banner)
			
			if toput.page == "Cat Capsule":
				goto = self.rejectedGatya
			
			if (goto == self.refinedGatya):
				GatyaParsers.appendGatyaLocal(toput)
			
			goto.append(toput)
	
	# OUTPUT TOOLS
	def printGatya(self)->str:
		toret = ""
		toret +=('```ansi\n[0m[32mGatya[0m\n')
		for event in self.refinedGatya:
			if not isinstance(event, EventGroup):
				if event.rates[3] in (10000, 9500):  # Platinum / Legend Ticket Event
					continue
				if event.page in ('Rare Capsule', 'Event Capsule') and event.ID > 0:
					toret += event.__str__()+"\n"
			else:
				toret += event.__str__()+"\n"
		toret +=('```\n')
		toret +=(
			"Legend for Gatya:\nSU = Step-Up, PS = Platinum Shard, L = Lucky Ticket,"
			" N = Neneko and Friends, R = Reinforcement, D = Grandons\n")
		return toret
	
	"""
	def printGatyaHTML(self):
		toret +=('<h4>Gatya:</h4><ul>')
		for event in self.refinedGatya:
			if event.rates[3] in ('10000', '9500'):  # Platinum / Legend Ticket Event
				continue
			if event.page in ('Rare Capsule', 'Event Capsule') and event.ID > 0:
				toret +=('<li><b>%s</b>%s</li>' % GatyaParsers.getString(event))
		toret +=('</ul>')
	
	def storeGatyaUncut(self) -> None:
		buf = ""
		for event in self.refinedGatya:
			if event.ID > 0:
				buf += '%s%s\n' % GatyaParsers.getString(event)
		
		buf += '\n'
		
		for event in self.rejectedGatya:
			if event.ID > 0:
				buf += '%s%s\n' % GatyaParsers.getString(event)
		
		with open(inm_loc + "gatya_final.txt", "w", encoding='utf-8') as text_file:
			text_file.write(buf)
	
	def exportGatya(self) -> None:
		# 1) save uncut final data
		self.storeGatyaUncut()
		
		# 2) save raw data in json for potential debugging
		with open(inm_loc + 'gatya_raw.json', 'w', encoding='utf-8') as raw:
			json.dump(self.rawGatya, raw, default=str)
		
		# 3) save it in db format for transcribers
		df_ref = pd.DataFrame(self.refinedGatya)
		df_rej = pd.DataFrame(self.rejectedGatya)
		
		try:
			conn = sqlite3.connect(inm_loc + 'gatya_processed.db')
		except sqlite3.OperationalError:
			toret +=('Database for gatya not found')
			return
		
		def process(df: pd.DataFrame):
			df["dates"] = df["dates"].apply(lambda x: [d.strftime('%Y/%m/%d') for d in x])
			df.insert(1, "start", df["dates"].str[0])
			df.insert(2, "end", df["dates"].str[1])
			df.drop(["dates", "versions", "slot"], axis=1, inplace=True)
		
		if len(df_ref) != 0:
			process(df_ref)
		if len(df_rej) != 0:
			process(df_rej)
		
		df_ref.astype(str).to_sql('refined', conn, if_exists='replace')
		df_rej.astype(str).to_sql('rejected', conn, if_exists='replace')
	"""
	def package(self):
		return [X.package() for X in self.refinedGatya]

class StageFetcher(UniversalFetcher):
	rawStages: list[list[str]]
	refinedStages: list[RawEventGroup]
	rejectedStages: list[RawEventGroup]
	finalStages: list[Stage | EventGroup]
	festivals: list[EventGroup]
	sales: list[Sale]
	missions: list[Mission]
	date0: datetime.datetime
	
	# SETUP
	def __init__(self, fls=None, d0=datetime.datetime.today()):
		UniversalFetcher.__init__(self, fls)
		self.rawStages = []
		self.refinedStages = []
		self.rejectedStages = []
		self.finalStages = []
		self.festivals = []
		self.sales = []
		self.missions = []
		self.date0 = d0
	
	# ACQUISITION TOOLS
	def fetchRawData(self, data: str) -> None:
		lines = data.split('\n')
		cr = csv.reader(lines, delimiter="\t")
		for row in cr:
			if len(row) > 1:
				self.rawStages.append(row)
				row[1], row[3] = (row[1] + '000')[0:4], (row[3] + '000')[0:4]
	
	# PROCESSING TOOLS
	def readRawData(self, storeRejects: bool = False) -> None:
		for data in self.rawStages:
			goto = self.refinedStages
			if not StageParsers.areValidDates(StageParsers.getdates(data), self.filters, self.date0):
				if not storeRejects:
					continue
				else:
					goto = self.rejectedStages
			
			toadd = {
				"dates": StageParsers.getdates(data),
				"versions": StageParsers.getversions(data)
			}
			
			# permanent - just ID - all day
			if data[7] == '0':
				toadd |= {"sched": "permanent", "IDs": [int(x) for x in data[9:9 + int(data[8])]]}
			# Yearly repeat XY - starts and ends at a date+time
			elif data[8] != '0':
				ydata, yIDs = StageParsers.yearly(data)
				toadd |= {"sched": "yearly", "sched_data": ydata, "IDs": yIDs}
			# Monthly repeat X0Y - list of days of month, may have time range
			elif data[9] != '0':
				mdata, mIDs = StageParsers.monthly(data)
				toadd |= {"sched": "monthly", "sched_data": mdata, "IDs": mIDs}
			# Weekly repeat X00Y - list of weekdays, may have time ranges
			elif data[10] != '0':
				wdata, wIDs = StageParsers.weekly(data)
				toadd |= {"sched": "weekly", "sched_data": wdata, "IDs": wIDs}
			# Daily repeat X000Y - list of time ranges every day in interval
			elif data[11] != '0':
				ddata, dIDs = StageParsers.daily(data)
				toadd |= {"sched": "daily", "sched_data": ddata, "IDs": dIDs}
			
			goto.append(RawEventGroup(**toadd))
	
	def sortAll(self) -> None:
		for x in [self.finalStages, self.sales, self.missions]:
			x.sort(key=lambda elem: elem.dates[0])
	
	# OUTPUT TOOLS
	# noinspection PyUnresolvedReferences
	def printFestivalData(self) -> str:
		def unique(sample: list):
			seen = set()
			tort = []
			for s in sample:
				if s not in seen:
					tort.append(s)
					seen.add(s)
		
			return tort
		
		def get_actual(check: list[datetime.datetime], d: int) -> datetime.datetime:
			tort = check[0].replace(day=d)
			if (check[0] <= tort < check[1]):
				return tort
			else:
				return tort.replace(month=(tort.month + 1) % 12, year=tort.year + (tort.month + 1) // 12)
		
		for festival in [X for X in self.festivals if not (X.split or not X.visible)]:
			toret = ""
			if not isinstance(festival.events[0], Stage) or festival.events[0].sched is None:
				continue
			
			toret +=(f'```ansi\n[0m[32m{festival.name}[0m {StageParsers.fancyDate(festival.dates)}\n\n')
			groups = []
			if(festival.events[0].sched_data is not None):
				obj = groupby(festival.events, lambda x: x.sched_data)
				for k, group in obj:
					groups.append(list(group))
			else:
				obj = groupby(festival.events, lambda x: x.dates)
				for k, group in obj:
					groups.append(list(group))
			
			for event_set in groups:
				# Starts printing here
				toret +=(f'[0m[33m{", ".join(unique([event.name for event in event_set]))}[0m\n')
				rep = event_set[0]  # representative event of the set
				mstart = rep.dates[0].strftime("%b")
				mend = rep.dates[-1].strftime("%b")
				
				if rep.sched == 'permanent':
					toret +=(f"[0m[34m- {rep.dates[0].day} {mstart}:[0m "
					      f"{StageParsers.fancyTimes([{'start': rep.dates[0], 'end': rep.dates[1]}])}\n")
				
				elif rep.sched == 'monthly':
					for setting in rep.sched_data:
						parsed = StageParsers.interpretDates(setting['dates'])
						
						match (parsed[0]):
							case 0:
								dates = sorted([get_actual(rep.dates, x) for x in setting['dates']])
								E = f'- {", ".join([x.strftime("%d %b").lstrip("0") for x in dates])}'
							case 2:
								E = f'[0m[34m- {parsed[1]} {mstart}~{parsed[2]} {mend}[0m: Every Alternate Day'
							case 3:
								E = f'[0m[34m- {parsed[1]} {mstart}~{parsed[2]} {mend}[0m: Every Third Day'
							case _:
								E = f'[0m[34m- {parsed[1]} {mstart}~{parsed[2]} {mend}[0m: Every {parsed[0]}th Day'
						# wont be above 10 so it's okay
						if len(setting['times']) == 0:
							toret +=(E)+"\n"
						else:
							toret +=(f"[0m[34m{E}[0m: {StageParsers.fancyTimes(setting['times'])}+\n")
				
				elif rep.sched == 'daily':
					for setting in rep.sched_data:
						toret +=(f"[0m[34m{StageParsers.fancyDate(rep.dates)}[0m{StageParsers.fancyTimes(setting['times'])}\n")
				
				elif rep.sched == 'weekly':
					dayscheds = [[], [], [], [], [], [], []]
					for setting in rep.sched_data:
						for i, val in enumerate(setting['weekdays']):
							if val: dayscheds[i].append(StageParsers.fancyTimes(setting['times']))
					ignored: list[int] = []
					for i, day1 in enumerate(dayscheds):
						buf = []
						if (i in ignored or day1 == []): continue
						buf.append(weekdays[i])
						day2 = j = None
						for j, day2 in enumerate(dayscheds[i + 1:]):
							if (i + j + 1 in ignored): continue
						if (set(day1) == set(day2)):
							ignored.append(i + j + 1)
						buf.append(weekdays[i + j + 1])
						toret +=(f"[0m[34m{'/'.join(buf)}:[0m {', '.join(day1)}\n")
				
				elif rep.sched == 'yearly':
					toret +=("[0m[34m"+StageParsers.fancyDate([rep.sched_data[0]['times'][0]['start']+"[0m"+
					                              rep.sched_data[0]['times'][0]['end']])[:-2]+"\n")
				
				# End printing
			toret +=('```\n')
			return toret
	
	def schedulingTable(self):
		hashmap = {'yearly': 'Yearly', 'monthly': 'Monthly', 'weekly': 'Weekly', 'daily': 'Daily',
		           'permanent': 'Forever'}
		cols = ['Event', 'Yearly', 'Monthly', 'Weekly', 'Daily', 'Forever']
		
		df = pd.DataFrame(columns=cols)
		
		stagedata = self.refinedStages
		stagedata.sort(key=lambda x: x.dates[0])
		for stage in stagedata:
			try:
				s = pd.Series()
				s.name = stage.IDs[0]
				s['Event'] = stage.name
				for k in hashmap:
					if stage.sched == k:
						s[hashmap[k]] = 1
					else:
						s[hashmap[k]] = 0
				df = df.append(s)
			except KeyError:
				pass
		
		df.to_csv('scheduling.tsv', sep='\t')
	
	def printStages(self) -> str:
		toret = ""
		toret +=('```ansi\n[0m[32mEvents[0m\n')
		for element in self.finalStages:
			toret +=(element).__str__()+"\n"
		toret +=('```\n')
		
		toret +=('```ansi\n[0m[32mSales[0m\n')
		for element in self.sales:
			toret +=(element).__str__()+"\n"
		toret +=('```\n')
		
		toret +=('```ansi\n[0m[32mMissions[0m\n')
		for element in self.missions:
			toret +=(element).__str__()+"\n"
		toret +=('```\n')
		return toret
	
	"""
	def printStagesHTML(self, stagedata=None, saledata=None):
		if stagedata is None:
			stagedata = self.finalStages
		if saledata is None:
			saledata = self.sales
		
		toret +=('<h4>Events:</h4><ul>')
		for group in stagedata:
			toret +=(f"<li><b>{StageParsers.fancyDate(group['dates'])[2:]}</b>{group['name']}</li>")
		toret +=('</ul>')
		
		toret +=('<h4>Sales:</h4><ul>')
		for group in saledata:
			toret +=(f"<li><b>{StageParsers.fancyDate(group['dates'])[2:]}</b>{group['name']}</li>")
		toret +=('</ul>')
	"""
	def package(self):
		return [[X.package() for X in Y] for Y in [self.finalStages, self.sales, self.missions]]
	"""
	def exportStages(self):
		grps = ["permanent", "yearly", "monthly", "weekly", "daily"]
		with open(inm_loc + 'stages_raw.json', 'w', encoding='utf-8') as raw:
			json.dump(self.rawStages, raw, default=str)
		
		df_fin = pd.DataFrame(self.finalStages)
		df_ref = pd.DataFrame(self.refinedStages)
		df_rej = pd.DataFrame(self.rejectedStages)
		
		try:
			conn = sqlite3.connect(inm_loc + 'events_processed.db')
		except sqlite3.OperationalError:
			toret +=('Database for events / stages not found')
			return
		
		df_fin["dates"] = df_ref["dates"].apply(lambda x: [d.strftime('%Y/%m/%d') for d in x])
		df_ref["dates"] = df_ref["dates"].apply(lambda x: [d.strftime('%Y/%m/%d') for d in x])
		df_rej["dates"] = df_rej["dates"].apply(lambda x: [d.strftime('%Y/%m/%d') for d in x])
		
		df_fin = df_fin.astype(str)
		df_ref = df_ref.astype(str)
		df_rej = df_rej.astype(str)
		
		ref_grpby = df_ref.groupby(["schedule"])
		rej_grpby = df_rej.groupby(["schedule"])
		
		ref_groups = {x: df_ref.iloc[ref_grpby.groups.get(x, []), :] for x in grps}
		rej_groups = {x: df_rej.iloc[rej_grpby.groups.get(x, []), :] for x in grps}
		
		df_fin.to_sql('final', conn, if_exists='replace')
		df_ref.to_sql('refined', conn, if_exists='replace')
		df_rej.to_sql('rejected', conn, if_exists='replace')
		
		for grp in ref_groups:
			ref_groups[grp].to_sql('ref ' + grp, conn, if_exists='replace')
		for grp in rej_groups:
			rej_groups[grp].to_sql('rej ' + grp, conn, if_exists='replace')
	"""
class ItemFetcher(UniversalFetcher):
	def __init__(self, fls=['M'], d0=datetime.datetime.today()):
		UniversalFetcher.__init__(self, fls)
		self.rawData: list[list[str]] = []
		self.refinedData: list[RawEventGroup] = []
		self.finalItems: list[Item] = []
		self.date0: datetime.datetime = d0
	
	def fetchRawData(self, data: str) -> None:
		lines = data.split('\n')
		cr = csv.reader(lines, delimiter="\t")
		for row in cr:
			if len(row) > 1:
				self.rawData.append(row)
				row[1], row[3] = (row[1] + '000')[0:3], (row[3] + '000')[0:3]
	
	def readRawData(self) -> None:
		for data in self.rawData:
			if not ItemParsers.areValidDates(ItemParsers.getdates(data), self.filters, self.date0):
				continue
			# TODO: why this check
			if data[7] == '0':
				i: Event = Event()
				i.dates = ItemParsers.getdates(data)
				i.versions = ItemParsers.getversions(data)
				i.ID = int(data[9])
				i.text = data[11]
				
				if 900 <= i.ID < 1000:  # Login Stamp
					i.name = i.text + ' (Login Stamp)'
					self.finalItems.append(Item.fromEvent(i))
				elif 800 <= i.ID < 900:
					i.name = Readers.getSaleBySever(i.ID)
					del (i.text)
					self.refinedData.append(RawEventGroup.makeSingleton(i))
				elif x := StageParsers.getEventName(i.ID, lookup=False) != "Unknown":
					i.name = x
					del (i.text)
					self.refinedData.append(RawEventGroup.makeSingleton(i))
				else:
					it = Item.fromEvent(i)
					it.name = Readers.getItemBySever(it.ID)
					it.recurring = bool(int(('0' + data[15])))
					it.qty = int(data[10])
					self.finalItems.append(it)
	
	def getStageData(self) -> list[RawEventGroup]:
		return self.refinedData
	
	def printItemData(self) -> str:
		toret = ""
		self.finalItems.sort(key=lambda x: x.dates[0])
		toret +=('```ansi\n[0m[32mItems[0m\n')
		for item in self.finalItems:
			toret +=(item).__str__()+"\n"
		toret +=('```\n')
		return toret
	
	def package(self) -> list[dict[str, any]]:
		return [X.package() for X in self.finalItems]
