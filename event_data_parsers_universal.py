import json
import pandas as pd
import datetime
from local_readers import Readers
from z_downloaders import Downloaders
import string

with open('_config.json') as fl:
	config = json.load(fl)

class UniversalParsers:
	with open(config['outputs']['stages'], encoding='utf-8', newline='') as csvfile:
		autoEventNames = pd.read_csv(csvfile, delimiter='\t', index_col='ID')
	
	with open("extras\\events.tsv", encoding='utf-8', newline='') as csvfile:
		manualEventNames = pd.read_csv(csvfile, delimiter='\t', index_col='ID')
		allEventNames = autoEventNames.append(manualEventNames)
	
	@staticmethod
	def fancyDate(datesall: list[datetime.datetime]) -> str:
		toret = "- "
		for dates in zip(datesall[0::2], datesall[1::2]):
			dates = list(dates)
			if dates[1].hour == 0:
				dates[1] -= datetime.timedelta(minutes=1)
			
			if (dates[1] - dates[0]).days > 365:  # Forever Events
				toret += f"{dates[0].strftime('%d %b').lstrip('0')}~..."
			elif dates[0].month == dates[1].month:  # Events that don't cross months
				if dates[0].day == dates[1].day:
					# Events that only last one day or less
					toret += dates[0].strftime('%d %b').lstrip('0')
				else:
					toret += '~'.join([dates[0].strftime('%d').lstrip('0'), dates[1].strftime('%d %b').lstrip('0')])
			
			else:  # Events that cross months
				toret += '~'.join([x.strftime('%d %b').lstrip('0') for x in dates])
			
			toret += ', '
		
		return toret[:-2] + ": "
	
	@staticmethod
	def fancyTimes(timesall: list[dict[str, datetime.datetime]]) -> str:
		toret = ""
		if len(timesall) == 0:
			return "All Day"
		for time in timesall:
			if (time['end'].hour == 23 and time['start'].hour == 0):
				return "All Day"
			toret += f"{time['start'].strftime('%I%p').lstrip('0')}~{time['end'].strftime('%I%p').lstrip('0')}"
			toret += ', '
		
		return toret[:-2]
	
	@staticmethod
	def areValidDates(dates: list[datetime.datetime], filters: list[str],
	                  date0: datetime.datetime = datetime.datetime.today()) -> bool:
		if len(filters) > 0:
			if 'N' in filters:  # if event lasts longer than a month or starts after today
				if ((dates[1] - dates[0]).days > 31 and not (dates[0] - date0).days >= 1):
					return False
			elif 'M' in filters:
				if (dates[1] - dates[0]).days > 31:  # If event lasts longer than a month
					return False
			if 'Y' in filters:
				if (date0 - dates[0]).days > -1:  # If event started today or earlier
					return False
		if (date0 - dates[1]).days > 365:  # Default Filter - Ignore (most) discontinued events
			return False
		return True
	
	@classmethod
	def getdates(cls, data: list[str]) -> list[datetime.datetime, datetime.datetime]:
		return [cls.formatDate(data[0] + data[1]), cls.formatDate(data[2] + data[3])]
	
	@staticmethod
	def getversions(data: list[str]) -> tuple[str, str]:
		return (data[4], data[5])
	
	@staticmethod
	def formatDate(s: str) -> datetime.datetime:
		return datetime.datetime.strptime(s, '%Y%m%d%H%M')
	
	@classmethod
	def getEventName(cls, ID: int) -> str:
		# not used by gatya
		if (18000 <= ID < 18100):
			if (ID == 18000):
				return "Anniversary Slots"
			return "Slots"
		elif (18100 <= ID < 18200):
			return "Scratch Cards Event"
		elif (9000 <= ID < 10000):
			return Readers.getMission(ID)
		
		try:
			name = cls.allEventNames.loc[ID, "name"]
			eng = len([0 for x in name if x in string.ascii_letters])
			full = len([0 for x in name if x.isalpha()])
			if(full < 2*eng):
				if (25000 > ID > 24000 or 28000 > ID > 27000):
					name += ' (Baron)'
				return name
		except KeyError:
			pass
		
		name = Downloaders.requestStage(ID, 'en')
		if name != 'Unknown':
			# updates name
			cls.autoEventNames.loc[ID, "name"] = name
		return name
	
	@classmethod
	def updateEventNames(cls):
		with open(config['outputs']['stages'], 'w', encoding='utf-8', newline='') as fil:
			cls.autoEventNames.to_csv(fil, sep='\t', index=True)
