import csv
import datetime
import json
from itertools import groupby

import pandas as pd

from .containers import Gatya, Event, Stage, EventGroup, Mission, Sale, RawEventGroup, Item, Colourer
from .event_data_parsers import GatyaParsers, ItemParsers, StageParsers
from .local_readers import Readers

groupable_events: list[str] = ['Seeing Red', 'Tag Arena', 'Dark', 'Duel', '(Baron)', 'Citadel']
weekdays: list[str] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

with open('_config.json') as fl:
	config = json.load(fl)
inm_loc: str = config["outputs"]["eventdata"]

with open(config['outputs']['groups'], encoding='utf-8') as f:
	f = f.read()
	y = json.loads(f)
	event_groups: dict[str, dict[str, str | bool]] = y

class UniversalFetcher:
	ver: str
	filters: list[str]
	clr: Colourer
	date0: datetime.datetime
	
	def __init__(self, d0: datetime.datetime = datetime.datetime.today(),
	             fls: list = ['N'], coloured: Colourer = Colourer()):
		self.filters = fls
		self.clr = coloured
		self.date0 = d0
	
	def groupData(self, waitingqueue: list[RawEventGroup] | list[Event]) -> tuple[list[Event], list[EventGroup],
	                                                                              list[Sale], list[Mission]]:
		# stage, festival, sale, mission
		group_history_2: dict[str, EventGroup] = {}
		ungrouped_history: dict[str, Event] = {}
		finalEvents: list[Event | EventGroup] = []
		finalEventGroups: list[EventGroup] = []
		sales: list[Sale | EventGroup] = []
		missions: list[Mission | EventGroup] = []
		
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
				elif 10000 > e.events[0].ID >= 9000:
					missions.append(e)
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
					
					curr0: Event = Stage(name=eventname, ID=ID, dates=grp0.dates, versions=grp0.versions,
					                     sched=grp0.sched, sched_data=grp0.sched_data, clr=self.clr)
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
	def __init__(self, **kwargs):
		UniversalFetcher.__init__(self, **kwargs)
		self.rawGatya: list[list[str]] = []
		self.refinedGatya: list[Gatya] = []
		self.rejectedGatya: list[Gatya] = []
	
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
			toput.clr = self.clr
			
			if toput.page == "Cat Capsule":
				goto = self.rejectedGatya
			
			if (goto == self.refinedGatya):
				GatyaParsers.appendGatyaLocal(toput)
			
			goto.append(toput)
	
	# OUTPUT TOOLS
	def printGatya(self) -> str:
		toret = ""
		if len(self.refinedGatya) == 0:
			return ""
		toret += (f'```ansi\n{self.clr.clc("Gatya:", 32)}\n\n')
		for event in self.refinedGatya:
			if not isinstance(event, EventGroup):
				if event.rates[3] in (10000, 9500):  # Platinum / Legend Ticket Event
					continue
				if event.page in ('Rare Capsule', 'Event Capsule') and event.ID > 0:
					toret += event.__str__() + "\n"
			else:
				toret += event.__str__() + "\n"
		toret += ('```\n')
		toret += (
			"Legend for Gatya:\nSU = Step-Up, PS = Platinum Shard, L = Lucky Ticket,"
			" N = Neneko and Friends, R = Reinforcement, D = Grandons, + = Double Rate (10% for Ubers, 0.6% for LRs)\n")
		return toret
	
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
	def __init__(self, **kwargs):
		UniversalFetcher.__init__(self, **kwargs)
		self.rawStages = []
		self.refinedStages = []
		self.rejectedStages = []
		self.finalStages = []
		self.festivals = []
		self.sales = []
		self.missions = []
	
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
				return tort.replace(month=(tort.month) % 12 + 1, year=tort.year + (tort.month + 1) // 13)
		
		if len(self.festivals) == 0:
			return ""
		toret = "Festival Data:\n"
		for festival in [X for X in self.festivals if not (X.split or not X.visible)]:
			if not isinstance(festival.events[0], Stage) or festival.events[0].sched is None:
				continue
			
			toret += (f'```ansi\n{self.clr.clc(festival.name, 32)} {StageParsers.fancyDate(festival.dates)}\n\n')
			groups = []
			if (festival.events[0].sched_data is not None):
				obj = groupby(festival.events, lambda x: x.sched_data)
				for k, group in obj:
					groups.append(list(group))
			else:
				obj = groupby(festival.events, lambda x: x.dates)
				for k, group in obj:
					groups.append(list(group))
			
			for event_set in groups:
				# Starts printing here
				toret += self.clr.clc(f'{", ".join(unique([event.name for event in event_set]))}\n', 33)
				rep = event_set[0]  # representative event of the set
				
				if rep.sched == 'permanent':
					toret += self.clr.clc(StageParsers.fancyDate(rep.dates), 34) + \
					         f"{StageParsers.fancyTimes([{'start': rep.dates[0], 'end': rep.dates[1]}])}\n"
				
				elif rep.sched == 'monthly':
					for setting in rep.sched_data:
						parsed = StageParsers.interpretDates(setting['dates'])
						dates = sorted([get_actual(rep.dates, x) for x in setting['dates']])
						E = self.clr.clc(StageParsers.fancyDate([dates[0], dates[-1]]), 34)
						match (parsed[0]):
							case 0:
								E = f'- {", ".join([x.strftime("%d %b").lstrip("0") for x in dates])}'
							case 2:
								E += 'Every Alternate Day'
							case 3:
								E += 'Every Third Day'
							case _:
								E += f"Every {parsed[0]}th Day"
						# wont be above 10 so it's okay
						if len(setting['times']) == 0:
							toret += f"{self.clr.clc(E, 34)} :: All Day\n"
						else:
							toret += f"{self.clr.clc(E, 34)} :: {StageParsers.fancyTimes(setting['times'])}\n"
				
				elif rep.sched == 'daily':
					for setting in rep.sched_data:
						toret += (
							f"{self.clr.clc(StageParsers.fancyDate(rep.dates), 34)} {StageParsers.fancyTimes(setting['times'])}\n")
				
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
						toret += (f"- {self.clr.clc('/'.join(buf), 34)}: {', '.join(day1)}\n")
				
				elif rep.sched == 'yearly':
					toprint = StageParsers.fancyDate([rep.sched_data[0]['times'][0]['start'], rep.sched_data[0]['times'][0]['end']])[:-2]
					toret += f"- {self.clr.clc(toprint, 34)}\n)"
			
			# End printing
			toret += ('```\n')
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
	
	def printStages(self) -> list[str]:
		toret = []
		if len(self.finalStages) == 0:
			return []
		toret.append((f'```ansi\n{self.clr.clc("Events:", 32)}\n\n'))
		for element in self.finalStages:
			toret[-1] += (element).__str__() + "\n"
		toret[-1] += ('```\n')
		
		toret.append((f'```ansi\n{self.clr.clc("Sales:", 32)}\n\n'))
		for element in self.sales:
			toret[-1] += (element).__str__() + "\n"
		toret[-1] += ('```\n')
		
		toret[-1] += (f'```ansi\n{self.clr.clc("Missions:", 32)}\n\n')
		for element in self.missions:
			toret[-1] += (element).__str__() + "\n"
		toret[-1] += ('```\n')
		return toret
	
	def package(self):
		return {
			"stages": [x.package() for x in self.finalStages],
			"sales": [x.package() for x in self.sales],
			"missions": [x.package() for x in self.missions]
		}

class ItemFetcher(UniversalFetcher):
	def __init__(self, **kwargs):
		UniversalFetcher.__init__(self, **kwargs)
		self.rawData: list[list[str]] = []
		self.refinedData: list[RawEventGroup] = []
		self.finalItems: list[Item] = []
	
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
				i.clr = self.clr
				
				if 11000 <= i.ID < 12000:  # ponos has dumb syndrome and puts ranked dojo stage and reward in different files
					continue
				
				if 900 <= i.ID < 1000:  # Login Stamp
					i.name = i.text
					if 'Stamp' not in i.text:
						i.name += ' (Login Stamp)'
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
		if len(self.finalItems) == 0:
			return ""
		self.finalItems.sort(key=lambda x: x.dates[0])
		toret += (f'```ansi\n{self.clr.clc("Items:", 32)}\n\n')
		for item in self.finalItems:
			toret += (item).__str__() + "\n"
		toret += ('```\n')
		return toret
	
	def package(self) -> list[dict[str, any]]:
		return [X.package() for X in self.finalItems]
