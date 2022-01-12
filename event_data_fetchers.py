import csv
import datetime
import json
import sqlite3
from operator import itemgetter

import numpy as np
import pandas as pd

from containers import Gatya, Event, Stage, EventGroup, Mission, Sale, RawStageGroup, Item
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
	
	def __init__(self, v: str, fls: list):
		self.ver = v if v != 'jp' else ''
		self.filters = fls
	
	@staticmethod
	def groupData(refinedStages: list[RawStageGroup]) -> tuple[list[Stage], list[Sale], list[Mission]]:
		# stage, festival, sale, mission
		group_history_2: dict[str, EventGroup] = {}
		finalEvents: list[Stage | EventGroup] = []
		finalEventGroups: list[EventGroup] = []
		sales: list[Sale] = []
		missions: list[Mission] = []
		
		def pushEventOrSale(e: Event | EventGroup):
			if (isinstance(e, EventGroup)):
				finalEventGroups.append(e)
				finalEvents.append(e)
				return
			
			if e.dates[1].hour == 0:
				e.dates[1] -= datetime.timedelta(days=1)
			try:
				if 900 > e.ID > 799 or e.ID < 100:
					sales.append(Sale.fromEvent(e))
					return
				if 10000 > e.ID >= 9000:
					missions.append(Mission.fromEvent(e))
					return
			except KeyError:
				pass
			finalEvents.append(Stage.fromEvent(e))
		
		def flushGroup(grp: str):
			if not event_groups[grp]['visible']:
				return
			pushEventOrSale(group_history_2[grp])
			finalEventGroups.append(group_history_2[grp])
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
			                                            'dates': event.dates})
		
		def extendGroup(groupname: str, event: Event):
			group = group_history_2[groupname]
			group.events.append(event)
			group.dates[1] = max(group.dates[1], event.dates[1])
			group.dates[0] = min(group.dates[0], event.dates[0])
		
		def groupEvents():
			# Also flattens ungrouped events by ID
			for event in refinedStages:
				buffer: list[Stage] = []
				for ID in event.IDs:
					eventname = StageParsers.getEventName(ID)
					if eventname == 'Unknown':
						continue
					
					curr: Stage = Stage()
					curr.name = eventname
					curr.ID = ID
					curr.dates = event.dates
					grouped = False
					
					for groupname, group in event_groups.items():
						if curr.name in group['stages']:
							grouped = True
							if groupname in group_history_2:
								if needsReset(groupname, curr):
									flushGroup(groupname)
									addGroup(groupname, curr)
								else:
									extendGroup(groupname, curr)
							else:
								addGroup(groupname, curr)
					if not grouped:
						buffer.append(curr)
				for ev in buffer:
					pushEventOrSale(ev)
			for groupname in group_history_2.copy():
				flushGroup(groupname)
		
		groupEvents()
		return (finalEvents, sales, missions)

class GatyaFetcher(UniversalFetcher):
	# SETUP
	def __init__(self, v='en', fls=['M'], d0=datetime.datetime.today()):
		UniversalFetcher.__init__(self, v, fls)
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
		
			if(goto == self.refinedGatya):
				GatyaParsers.appendGatyaLocal(toput)
			
			goto.append(toput)
	
	# OUTPUT TOOLS
	def printGatya(self):
		print('```\nGatya:')
		for event in self.refinedGatya:
			if event.rates[3] in ('10000', '9500'):  # Platinum / Legend Ticket Event
				continue
			if event.page in ('Rare Capsule', 'Event Capsule') and event.ID > 0:
				print('%s%s' % (GatyaParsers.getString(event)))
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
	refinedStages: list[RawStageGroup]
	rejectedStages: list[RawStageGroup]
	finalStages: list[Stage | EventGroup]
	sales: list[Sale]
	missions: list[Mission]
	date0: datetime.datetime
	
	# SETUP
	def __init__(self, v='en', fls=None, d0=datetime.datetime.today()):
		UniversalFetcher.__init__(self, v, fls)
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
				goto.append(RawStageGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "permanent",
					"IDs": [int(x) for x in data[9:9 + int(data[8])]]
				}))
			# Yearly repeat XY - starts and ends at a date+time
			elif data[8] != '0':
				ydata, yIDs = StageParsers.yearly(data)
				goto.append(RawStageGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "yearly",
					"sched_data": ydata,
					"IDs": yIDs
				}))
			# Monthly repeat X0Y - list of days of month, may have time range
			elif data[9] != '0':
				mdata, mIDs = StageParsers.monthly(data)
				goto.append(RawStageGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "monthly",
					"sched_data": mdata,
					"IDs": mIDs
				}))
			# Weekly repeat X00Y - list of weekdays, may have time ranges
			elif data[10] != '0':
				wdata, wIDs = StageParsers.weekly(data)
				goto.append(RawStageGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "weekly",
					"sched_data": wdata,
					"IDs": wIDs
				}))
			# Daily repeat X000Y - list of time ranges every day in interval
			elif data[11] != '0':
				ddata, dIDs = StageParsers.daily(data)
				goto.append(RawStageGroup(**{
					"dates": StageParsers.getdates(data),
					"versions": StageParsers.getversions(data),
					"sched": "daily",
					"sched_data": ddata,
					"IDs": dIDs
				}))
	
	def getStageData(self)-> tuple[list[Stage | EventGroup], list[Sale]]:
		# use this AFTER grouping and BEFORE printing / export
		return self.finalStages, self.sales
	
	def finalProcessing(self) -> None:
		def miscProcess(sd: list[Stage | EventGroup] | list[Sale]):
			sd.sort(key=lambda x: x.dates[0])
			
			to_del: list[int] = []
			
			for i, event in enumerate(sd):
				if isinstance(event, EventGroup) or i in to_del:
					continue
				# Groups Barons, Duels, Dark Descent, etc.
				if any([x in event.name for x in groupable_events]):
					for j, e in enumerate(sd[i + 1:]):
						# Can't use two words because Duel stages
						if (e.name.split(' ')[0] == event.name.split(' ')[0]
								or e.name.split(' ')[-1] == event.name.split(' ')[-1]):
							# and (e['dates'][1] == event['dates'][1]: # used to check this before, add back if there are errors
							# If they share the same first / last word and end on the same date
							sd.insert(i + 1, sd.pop(i + j + 1))  # Put them together
							break
			
			for i, event in enumerate(sd):
				if(isinstance(event, EventGroup)):
					continue
				# Groups repetetive events [all of which are identical] like catfood discounts and cybear
				if event.name == 'Catfood Discount Reset (30)':
					for j, e in enumerate(sd[i + 1:]):
						if e.name == 'Catfood Discount Reset (750)':
							sd[i].name = 'Catfood Discount Reset (30/750)'
							to_del.append(i + j + 1)
							break
				
				for j, e in enumerate(sd[i + 1:]):
					if(isinstance(e, EventGroup)):
						continue
					try:
						if e.ID == event.ID:
							sd[i].dates.extend(e.dates)
							to_del.append(i + j + 1)
					except KeyError:
						pass  # Ignore events that are already grouped like Festivals, that doesn't have "IDs"
			
			# using [:] to mutate list without resetting pointer
			sd[:] = [elem for i, elem in enumerate(sd) if i not in to_del]
		
		miscProcess(self.finalStages)
		miscProcess(self.sales)
	
	# OUTPUT TOOLS
	def printFestivalData(self):
		permanentLog = []
		for event in self.refinedStages:
			for ID in event.IDs:
				# Checks come here
				
				if event.sched == 'permanent' and (
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
						
						E = f'- {parsed[1]} {mstart}~{parsed[2]} {mend}: Every {parsed[0]}th Day'
						match (parsed[0]):
							case 0: E = '- Date ' + '/'.join(setting['dates'])
							case 2:	E = f'- {parsed[1]} {mstart}~{parsed[2]} {mend}: Every Alternate Day'
							case 3:	E = f'- {parsed[1]} {mstart}~{parsed[2]} {mend}: Every Third Day'
						# wont be above 10 so it's okay
						# TODO: lookup how to put default case
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
	
	"""
	def printFestivalDataHTML(self):
		print('<h4>Festivals:</h4>')
		permanentLog = []
		for event in self.refinedStages:
			for ID in event.IDs:
				# Checks come here
				
				if event['schedule'] == 'permanent' and (
						ID not in (1028, 1059, 1124, 1155, 1078, 1007, 1006) or ID in permanentLog):
					continue
				
				if StageParsers.getEventName(ID) == 'Unknown':
					continue
				
				if event.sched == 'permanent':
					print(f'<h5>{StageParsers.getEventName(ID)}</h5><ul>')
					permanentLog.append(ID)
					# Merges ALL instances of this event!!
					for e in [x for x in self.refinedStages if ID in x.IDs]:
						print(
							f"<li><b>{e.dates[0].strftime('%d')}:</b> {e.dates[0].strftime('%I%p')}~"
							f"{e.dates[1].strftime('%I%p')}</li>")
				
				elif event.sched == 'monthly':
					print(
						f'<h5>{StageParsers.getEventName(ID)} ({StageParsers.fancyDate(event.dates)[2:-2]})</h5><ul>')
					for setting in event.sched_data:
						X = [int(x) for x in setting.dates]
						parsed = StageParsers.interpretDates(np.array(X))
						if parsed[0] == 0:
							E = 'Date ' + '/'.join(setting.dates)
						elif parsed[0] == 2:
							E = f'{parsed[1]} ~ {parsed[2]} - Every Alternate Day'
						elif parsed[0] == 3:
							E = f'{parsed[1]} ~ {parsed[2]} - Every Third Day'
						else:
							E = f'{parsed[1]} ~ {parsed[2]} - Every {parsed[0]}th Day'  # wont be above 10 so it's okay
						
						if len(setting['times']) == 0:
							print(f'<li><b>{E}</b></li>')
						else:
							print(
								'<li><b>' + E + ':</b> ' + f"{setting['times'][0]['start'].strftime('%I%p').lstrip('0')}~"
								                           f"{setting['times'][0]['end'].strftime('%I%p').lstrip('0')}</li>")
				
				elif event.sched == 'daily':
					print(f'<h5>{StageParsers.getEventName(ID)}</h5><ul>')
					for setting in event.sched_data:
						print(
							f"<li><b>{StageParsers.fancyDate(event['dates'])[2:]}</b>"
							f"{StageParsers.fancyTimes(setting['times'])}</li>")
				
				elif event.sched == 'weekly':
					# TODO: carry over improved weekly / monthly event parsing to HTML format
					print(
						f'<h5>{StageParsers.getEventName(ID)} ({StageParsers.fancyDate(event["dates"])[2:-2]})</h5><ul>')
					for setting in event['data']:
						print(
							f"<li><b>{'/'.join([weekdays[i] for i, val in enumerate(setting['weekdays']) if val == 1])}</b>: "
							f"{StageParsers.fancyTimes(setting['times'])}</li>")
				
				elif event.sched == 'yearly':
					duration = [event.sched_data[0]['times'][0]['start'], event.sched_data[0]['times'][0]['end']]
					print(f"<li><b>{StageParsers.fancyDate(duration)[2:-2]}</b></li>")
				
				# End printing
				print('</ul>')
	"""

	def schedulingTable(self):
		hashmap = {'yearly': 'Yearly', 'monthly': 'Monthly', 'weekly': 'Weekly', 'daily': 'Daily',
		           'permanent': 'Forever'}
		cols = ['Event', 'Yearly', 'Monthly', 'Weekly', 'Daily', 'Forever']
		
		df = pd.DataFrame(columns=cols)
		
		stagedata = self.refinedStages
		stagedata.sort(key=itemgetter('dates'))
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
	
	def printStages(self, stagedata: list[Stage | EventGroup] = None, saledata: list[Sale] = None)-> None:
		if stagedata is None:
			stagedata = self.finalStages
		if saledata is None:
			saledata = self.sales
		
		print('```\nEvents:')
		for group in stagedata:
			print(StageParsers.fancyDate(group.dates) + group.name)
		print('```')
		
		print('```\nSales:')
		for sl in saledata:
			print(StageParsers.fancyDate(sl.dates) + sl.name)
		print('```')
		
		print('```\nMissions:')
		for msn in self.missions:
			print(StageParsers.fancyDate(msn.dates) + msn.name)
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
	def __init__(self, v='en', fls=['M'], d0=datetime.datetime.today()):
		UniversalFetcher.__init__(self, v, fls)
		self.rawData: list[list[str]] = []
		self.refinedData: list[Event] = []
		self.refinedStages: list[Stage] = []
		self.finalStages: list[Stage] = []
		self.refinedItems: list[Item] = []
		self.sales: list[Sale] = []
		self.date0: datetime.datetime = d0
	
	def fetchRawData(self, data: str):
		lines = data.split('\n')
		cr = csv.reader(lines, delimiter="\t")
		for row in cr:
			if len(row) > 1:
				self.rawData.append(row)
				row[1], row[3] = (row[1] + '000')[0:3], (row[3] + '000')[0:3]
	
	def readRawData(self):
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
				self.refinedData.append(i)
				
				if 900 <= i.ID < 1000:  # Login Stamp
					i.name = i.text + ' (Login Stamp)'
					self.refinedItems.append(Item.fromEvent(i))
				elif 800 <= i.ID < 900:
					i.name = Readers.getSaleBySever(i.ID)
					self.sales.append(Sale.fromEvent(i))
				elif i.ID > 1000:
					i.name = Readers.getStageOrMap(i.ID)
					self.refinedStages.append(Stage.fromEvent(i))
				else:
					it = Item.fromEvent(i)
					it.name = Readers.getItemBySever(it.ID)
					it.recurring = int('0' + data[15])
					it.qty = int(data[10])
					self.refinedItems.append(it)
	
	def getStageData(self):
		return (self.refinedStages, self.sales)
	
	def printItemData(self):
		print('```\nItems:')
		for pt, item in enumerate(self.refinedItems):
			if item.name in ['Leadership', 'Rare Ticket'] and item.dates[0].day == 22 and item.dates[
				1].day == 22:
				for ps, i in enumerate(self.refinedItems[pt + 1:]):
					if i.name in ['Leadership', 'Rare Ticket'] and item.dates[0].day == 22 and item.dates[
						1].day == 22 and item.name != i.name:
						self.refinedItems.pop(ps + pt + 1)
						self.refinedItems[pt].name += f' + {i.name} (Meow Meow Day)'
						break
			elif item.name == 'Rare Ticket':
				v = item.versions[0][0:2] + '.' + str(int(item.versions[0][2:4]))
				if v in item.text:
					self.refinedItems[pt].name += f' (for {v} Update)'
		
		for item in self.refinedItems:
			qty = (' x ' + str(item.qty)) if int(item.qty) > 1 else ''
			if item.name in ['Cat Food', 'Rare Ticket'] and (item.dates[1] - item.dates[0]).days >= 2:
				qty += ' (Daily)' if item.recurring else ' (Only Once)'
			print(ItemParsers.fancyDate(item.dates) + item.name + qty)
		print('```')
	
	"""
	def printItemDataHTML(self):
		print('<h4>Items:</h4><ul>')
		for pt, item in enumerate(self.refinedItems):
			if item.name in ['Leadership', 'Rare Ticket'] and item.dates[0].day == 22 and item.dates[
				1].day == 22:
				for ps, i in enumerate(self.refinedItems[pt + 1:]):
					if i.name in ['Leadership', 'Rare Ticket'] and item.dates[0].day == 22 and item.dates[
						1].day == 22 and item.name != i.name:
						self.refinedItems.pop(ps + pt + 1)
						self.refinedItems[pt].name += f' + {i["name"]} (Meow Meow Day)'
						break
			elif item.name == 'Rare Ticket':
				v = item['versions'][0][0:2] + '.' + str(int(item['versions'][0][2:4]))
				if v in item['text']:
					self.refinedItems[pt].name += f' (for {v} Update)'
		
		for item in self.refinedItems:
			qty = (' x ' + item.qty) if int(item.qty) > 1 else ''
			if item.name in ['Cat Food', 'Rare Ticket'] and (item.dates[1] - item.dates[0]).days >= 2:
				qty += ' (Daily)' if item['recurring'] else ' (Only Once)'
			print('<li><b>' + ItemParsers.fancyDate(item.dates)[2:] + '</b>' + item.name + qty + '</li>')
		print('</ul>')
	"""
