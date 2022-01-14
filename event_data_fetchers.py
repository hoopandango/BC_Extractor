import csv
import datetime
import json
import sqlite3

import numpy as np
import pandas as pd

from containers import Gatya, Event, Stage, EventGroup, Mission, Sale, RawEventGroup, Item
from event_data_parsers import GatyaParsers, ItemParsers, StageParsers
from local_readers import Readers

groupable_events: list[str] = ['Seeing Red', 'Tag Arena', 'Dark', 'Duel', '(Baron)', 'Citadel']
weekdays: list[str] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

with open('_config.json') as fl:
	config = json.load(fl)
inm_loc: str = config["outputs"]["eventdata"]

with open('extras\\EventGroups.json', encoding='utf-8') as f:
	f = f.read()
	y = json.loads(f)
	event_groups: dict[str, dict[str, str | bool]] = y

class UniversalFetcher:
	ver: str
	filters: list[str]
	
	def __init__(self, fls: list):
		self.filters = fls
	
	@staticmethod
	def groupData(waitingqueue: list[RawEventGroup] | list[Event]) -> tuple[list[Event], list[Sale], list[Mission]]:
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
			                                            'dates': event.dates.copy(), 'split': event_groups[group_name]["split"]})
		
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
					
					curr0: Event = Event(name=eventname, ID=ID, dates=grp0.dates)
					newqueue.append(curr0)
			return newqueue
	
		if(isinstance(waitingqueue[0], RawEventGroup)):
			flatqueue = flatten(waitingqueue)
		else:
			flatqueue = waitingqueue
		groupEvents()
		return (finalEvents, sales, missions)

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
				print(f"weirdo at {banner}")
			
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
		
			if(goto == self.refinedGatya):
				GatyaParsers.appendGatyaLocal(toput)
			
			goto.append(toput)
	
	# OUTPUT TOOLS
	def printGatya(self):
		print('```\nGatya:')
		for event in self.refinedGatya:
			if not isinstance(event, EventGroup):
				if event.rates[3] in (10000, 9500):  # Platinum / Legend Ticket Event
					continue
				if event.page in ('Rare Capsule', 'Event Capsule') and event.ID > 0:
					print(event)
			else:
				print(event)
		print('```')
		print(
			"Legend for Gatya:\nG = Guaranteed, SU = Step-Up, PS = Platinum Shard, L = Lucky Ticket,"
			" N = Neneko and Friends, R = Reinforcement, D = Grandons")
	
	def printGatyaHTML(self):
		print('<h4>Gatya:</h4><ul>')
		for event in self.refinedGatya:
			if event.rates[3] in ('10000', '9500'):  # Platinum / Legend Ticket Event
				continue
			if event.page in ('Rare Capsule', 'Event Capsule') and event.ID > 0:
				print('<li><b>%s</b>%s</li>' % GatyaParsers.getString(event))
		print('</ul>')
	
	def storeGatyaUncut(self) -> None:
		buf = ""
		for event in self.refinedGatya:
			if int(event.ID) > 0:
				buf += '%s%s\n' % GatyaParsers.getString(event)
		
		buf += '\n'
		
		for event in self.rejectedGatya:
			if int(event.ID) > 0:
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
			print('Database for gatya not found')
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

class StageFetcher(UniversalFetcher):
	rawStages: list[list[str]]
	refinedStages: list[RawEventGroup]
	rejectedStages: list[RawEventGroup]
	finalStages: list[Stage | EventGroup]
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
			
			# permanent - just ID - all day
			if data[7] == '0':
				goto.append(RawEventGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "permanent",
					"IDs": [int(x) for x in data[9:9 + int(data[8])]]
				}))
			# Yearly repeat XY - starts and ends at a date+time
			elif data[8] != '0':
				ydata, yIDs = StageParsers.yearly(data)
				goto.append(RawEventGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "yearly",
					"sched_data": ydata,
					"IDs": yIDs
				}))
			# Monthly repeat X0Y - list of days of month, may have time range
			elif data[9] != '0':
				mdata, mIDs = StageParsers.monthly(data)
				goto.append(RawEventGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "monthly",
					"sched_data": mdata,
					"IDs": mIDs
				}))
			# Weekly repeat X00Y - list of weekdays, may have time ranges
			elif data[10] != '0':
				wdata, wIDs = StageParsers.weekly(data)
				goto.append(RawEventGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "weekly",
					"sched_data": wdata,
					"IDs": wIDs
				}))
			# Daily repeat X000Y - list of time ranges every day in interval
			elif data[11] != '0':
				ddata, dIDs = StageParsers.daily(data)
				goto.append(RawEventGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "daily",
					"sched_data": ddata,
					"IDs": dIDs
				}))
	
	def sortAll(self) -> None:
		for x in [self.finalStages, self.sales, self.missions]:
			x.sort(key=lambda elem: elem.dates[0])
	
	# OUTPUT TOOLS
	def printFestivalData(self):
		permanentLog = []
		for event in self.refinedStages:
			for ID in event.IDs:
				# Checks come here
				
				if event.sched is None or event.sched == 'permanent' and (
						ID not in (1028, 1059, 1124, 1155, 1078, 1007, 1006) or ID in permanentLog):
					continue
				
				# Starts printing here
				if StageParsers.getEventName(ID) == 'Unknown':
					print(f'```\n{ID}')
				
				else:
					print(f'```\n{StageParsers.getEventName(ID)}')
				
				if event.sched == 'permanent':
					permanentLog.append(ID)
					# Merges ALL instances of this event!!
					for e in [x for x in self.refinedStages if ID in x.IDs]:
						print(
							f"- {e.dates[0].strftime('%d')}: {e.dates[0].strftime('%I%p')}~{e.dates[1].strftime('%I%p')}")
				
				elif event.sched == 'monthly':
					for setting in event.sched_data:
						X = [int(x) for x in setting['dates']]
						parsed = StageParsers.interpretDates(np.array(X))
						mstart = event.dates[0].strftime("%b")
						mend = event.dates[-1].strftime("%b")
						
						match (parsed[0]):
							case 0: E = '- Date ' + '/'.join(setting['dates'])
							case 2:	E = f'- {parsed[1]} {mstart}~{parsed[2]} {mend}: Every Alternate Day'
							case 3:	E = f'- {parsed[1]} {mstart}~{parsed[2]} {mend}: Every Third Day'
							case _: E = f'- {parsed[1]} {mstart}~{parsed[2]} {mend}: Every {parsed[0]}th Day'
						# wont be above 10 so it's okay
						if len(setting['times']) == 0:
							print(E)
						else:
							print(
								f"{E}: {setting['times'][0]['start'].strftime('%I%p').lstrip('0')}~"
								f"{setting['times'][0]['end'].strftime('%I%p').lstrip('0')}")
				
				elif event.sched == 'daily':
					for setting in event.sched_data:
						print(f"{StageParsers.fancyDate(event.dates)}{StageParsers.fancyTimes(setting['times'])}")
				
				elif event.sched == 'weekly':
					dayscheds = [[], [], [], [], [], [], []]
					for setting in event.sched_data:
						for i, val in enumerate(setting['weekdays']):
							if val == 1: dayscheds[i].append(StageParsers.fancyTimes(setting['times']))
					ignored: list[int] = []
					for i, day1 in enumerate(dayscheds):
						buf = []
						if (i in ignored or day1 == []): continue
						buf.append(weekdays[i])
						for j, day2 in enumerate(dayscheds[i + 1:]):
							if (i + j + 1 in ignored): continue
							if (set(day1) == set(day2)):
								ignored.append(i + j + 1)
								buf.append(weekdays[i + j + 1])
						print(f"{'/'.join(buf)}: {', '.join(day1)}")
				
				elif event.sched == 'yearly':
					print(StageParsers.fancyDate([event.sched_data[0]['times'][0]['start'],
																				event.sched_data[0]['times'][0]['end']])[:-2])
				
				# End printing
				print('```')
	
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
	
	def printStages(self)-> None:
		print('```\nEvents:')
		for element in self.finalStages:
			print(element)
		print('```')
		
		print('```\nSales:')
		for element in self.sales:
			print(element)
		print('```')
		
		print('```\nMissions:')
		for element in self.missions:
			print(element)
		print('```')
	
	def printStagesHTML(self, stagedata=None, saledata=None):
		if stagedata is None:
			stagedata = self.finalStages
		if saledata is None:
			saledata = self.sales
		
		print('<h4>Events:</h4><ul>')
		for group in stagedata:
			print(f"<li><b>{StageParsers.fancyDate(group['dates'])[2:]}</b>{group['name']}</li>")
		print('</ul>')
		
		print('<h4>Sales:</h4><ul>')
		for group in saledata:
			print(f"<li><b>{StageParsers.fancyDate(group['dates'])[2:]}</b>{group['name']}</li>")
		print('</ul>')
	
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
			print('Database for events / stages not found')
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
					self.refinedData.append(RawEventGroup.makeSingleton(i))
				elif x := StageParsers.getEventName(i.ID, lookup=False) != "Unknown":
					i.name = x
					self.refinedData.append(RawEventGroup.makeSingleton(i))
				else:
					it = Item.fromEvent(i)
					it.name = Readers.getItemBySever(it.ID)
					it.recurring = int('0' + data[15])
					it.qty = int(data[10])
					self.finalItems.append(it)
	
	def getStageData(self) -> list[RawEventGroup]:
		return self.refinedData
	
	def printItemData(self) -> None:
		self.finalItems.sort(key=lambda x: x.dates[0])
		print('```\nItems:')
		for item in self.finalItems:
			print(item)
		print('```')
	